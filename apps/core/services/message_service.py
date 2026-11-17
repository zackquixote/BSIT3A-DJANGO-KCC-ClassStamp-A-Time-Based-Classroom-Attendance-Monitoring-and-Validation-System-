"""
# // ==============================================================================
# // KCC CLASSSTAMP - INTERNAL MESSAGING SERVICE (tasks 4.8 / 4.9 — Req 8)
# // ==============================================================================
# // One funnel for send, thread retrieval, mark-as-read, and enrollment-based
# // role validation. Student <-> teacher requires an ACTIVE enrollment.
// // Teacher -> admin and admin -> any active user need no enrollment check.
// // Subject/body limits are enforced at the boundary; nothing is truncated
// // silently. In-app (and therefore Web Push) plus email reuse the existing
// // notification services. Every send and read is audited.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.models import AuditEvent, Class, Enrollment, Message, Profile
from apps.core.services.in_app_notification_service import create_notification
from apps.core.services.notification_service import notify_user

User = get_user_model()

MAX_SUBJECT = 200
MAX_BODY = 5000

ROLE_LABELS = {
    Profile.ROLE_ADMIN: 'Administrator',
    Profile.ROLE_TEACHER: 'Instructor',
    Profile.ROLE_STUDENT: 'Student',
}

ROLE_BADGE_CLASSES = {
    Profile.ROLE_ADMIN: 'badge--purple',
    Profile.ROLE_TEACHER: 'badge--warning',
    Profile.ROLE_STUDENT: 'badge--success',
}


class MessageError(ValueError):
    """Raised when a send/mark operation violates a messaging rule."""


def _clean_payload(subject, body):
    """Trim and validate a subject/body pair without truncating either."""
    subject = (subject or '').strip()
    body = (body or '').strip()
    if not subject:
        raise MessageError('A subject is required.')
    if len(subject) > MAX_SUBJECT:
        raise MessageError(
            f'Subject is too long ({len(subject)}/{MAX_SUBJECT} characters).'
        )
    if not body:
        raise MessageError('A message body is required.')
    if len(body) > MAX_BODY:
        raise MessageError(
            f'Message body is too long ({len(body)}/{MAX_BODY} characters).'
        )
    return subject, body


def _is_admin(user) -> bool:
    if user is None:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'classstamp_profile', None)
    return profile is not None and profile.role == Profile.ROLE_ADMIN


def _profile_role(user):
    profile = getattr(user, 'classstamp_profile', None)
    if profile is None:
        return None
    return profile.role


def _has_active_enrollment(student_profile, teacher_profile) -> bool:
    return Enrollment.objects.filter(
        student_profile=student_profile,
        class_obj__teacher_profile=teacher_profile,
        class_obj__academic_year__is_active=True,
        status=Enrollment.STATUS_ACTIVE,
    ).exists()


def display_name(user) -> str:
    """
    // Human-readable name with a role-aware fallback. Accounts that were never
    // given a first/last name (the built-in `admin`) used to fall back to the
    // raw username, so a student's inbox read as if a classmate wrote to them.
    """
    if user is None:
        return 'Unknown user'
    full_name = (user.get_full_name() or '').strip()
    if full_name:
        return full_name
    profile = getattr(user, 'classstamp_profile', None)
    if profile is not None:
        return ROLE_LABELS.get(profile.role, 'User')
    return (user.get_username() or '').strip() or 'User'


def role_key(user) -> str:
    profile = getattr(user, 'classstamp_profile', None)
    return (profile.role or '').lower() if profile is not None else 'user'


def role_label(user) -> str:
    profile = getattr(user, 'classstamp_profile', None)
    if profile is None:
        return 'User'
    return ROLE_LABELS.get(profile.role, profile.get_role_display())


def role_badge_class(user) -> str:
    profile = getattr(user, 'classstamp_profile', None)
    if profile is None:
        return 'badge--muted'
    return ROLE_BADGE_CLASSES.get(profile.role, 'badge--muted')


def contact_meta(user, sections=None) -> str:
    """
    // Short identifier shown beside a name: student number or department,
    // plus the shared section(s) that connect the two people.
    """
    profile = getattr(user, 'classstamp_profile', None)
    if profile is None:
        return ''
    parts = []
    if profile.role == Profile.ROLE_STUDENT:
        if profile.student_number:
            parts.append(profile.student_number)
    elif profile.role == Profile.ROLE_TEACHER:
        department = getattr(profile, 'department', None)
        if department is not None:
            parts.append(getattr(department, 'code', '') or department.name)
    if sections:
        parts.extend(sorted(sections))
    return ' · '.join(part for part in parts if part)


def _contact(user, sections=None) -> dict:
    """One compose-picker row with everything the template needs."""
    return {
        'user': user,
        'name': display_name(user),
        'role': role_label(user),
        'role_key': role_key(user),
        'role_badge': role_badge_class(user),
        'meta': contact_meta(user, sections),
    }


def _contact_group(key, label, contacts, empty_hint='') -> dict:
    return {
        'key': key,
        'label': label,
        'contacts': sorted(contacts, key=lambda row: row['name'].casefold()),
        'empty_hint': empty_hint,
    }


def _enrollment_sections(queryset, user_id_field, section_field, code_field,
                         subject_field=None):
    """
    // Map user id -> set of section/subject labels from an enrollment queryset.
    // The subject code makes the compose picker read "ITE 107 · BSIT-3A" so the
    // recipient is tied to the subject the two people actually share.
    """
    labels = {}
    fields = [user_id_field, section_field, code_field]
    if subject_field:
        fields.append(subject_field)
    for row in queryset.values_list(*fields):
        user_id, section, code = row[:3]
        label = (section or code or '').strip()
        if label:
            labels.setdefault(user_id, set()).add(label)
        if subject_field:
            subject = (row[3] or '').strip()
            if subject:
                labels.setdefault(user_id, set()).add(subject)
    return labels


class MessageService:
    """Enrollment-aware internal messaging."""

    @staticmethod
    def can_contact(sender, recipient) -> bool:
        if sender is None or recipient is None or sender.pk == recipient.pk:
            return False
        if not recipient.is_active or not sender.is_active:
            return False

        sender_role = _profile_role(sender)
        recipient_role = _profile_role(recipient)
        sender_profile = getattr(sender, 'classstamp_profile', None)
        recipient_profile = getattr(recipient, 'classstamp_profile', None)

        def has_history() -> bool:
            return Message.objects.filter(
                Q(sender=sender, recipient=recipient)
                | Q(sender=recipient, recipient=sender)
            ).exists()

        # Students talk to instructors only. An administrator is never a valid
        # recipient for a student, even when an old admin thread exists — the
        # student side of that conversation stays read-only.
        if sender_role == Profile.ROLE_STUDENT:
            if recipient_role != Profile.ROLE_TEACHER:
                return False
            if sender_profile and recipient_profile and _has_active_enrollment(
                sender_profile, recipient_profile
            ):
                return True
            return has_history()

        if _is_admin(sender):
            return True

        # Existing conversations stay replyable for teacher/admin pairs.
        if has_history():
            return True

        if sender_role == Profile.ROLE_TEACHER and _is_admin(recipient):
            return True
        if sender_role == Profile.ROLE_TEACHER and recipient_role == Profile.ROLE_STUDENT:
            return bool(
                sender_profile and recipient_profile
                and _has_active_enrollment(recipient_profile, sender_profile)
            )
        return False

    @staticmethod
    def recipient_groups(user):
        """
        // Role-scoped compose picker. Each group becomes one optgroup: a teacher
        // gets their actively-enrolled students (with the section that links
        // them), plus administrators; a student gets their instructors plus
        // administrators who already wrote to them; an admin gets everyone.
        // Contacts with an existing thread are always included, because
        // can_contact() lets either side keep replying.
        """
        if _is_admin(user):
            candidates = (
                User.objects.filter(is_active=True)
                .exclude(pk=user.pk)
                .select_related('classstamp_profile__department')
            )
            buckets = {
                Profile.ROLE_TEACHER: [],
                Profile.ROLE_STUDENT: [],
                Profile.ROLE_ADMIN: [],
                None: [],
            }
            for candidate in candidates:
                candidate_profile = getattr(candidate, 'classstamp_profile', None)
                bucket = candidate_profile.role if candidate_profile else None
                buckets.setdefault(bucket, []).append(_contact(candidate))
            return [
                _contact_group('instructors', 'Instructors', buckets[Profile.ROLE_TEACHER]),
                _contact_group('students', 'Students', buckets[Profile.ROLE_STUDENT]),
                _contact_group('administrators', 'Administrators', buckets[Profile.ROLE_ADMIN]),
                _contact_group('other', 'Other accounts', buckets[None]),
            ]

        profile = getattr(user, 'classstamp_profile', None)
        if profile is None:
            return []

        groups = []
        included_ids = set()

        if profile.role == Profile.ROLE_TEACHER:
            sections = _enrollment_sections(
                Enrollment.objects.filter(
                    class_obj__teacher_profile=profile,
                    class_obj__academic_year__is_active=True,
                    status=Enrollment.STATUS_ACTIVE,
                ),
                'student_profile__user_id',
                'class_obj__section_code',
                'class_obj__class_code',
                'class_obj__subject__code',
            )
            students = (
                User.objects.filter(pk__in=list(sections), is_active=True)
                .exclude(pk=user.pk)
                .select_related('classstamp_profile__department')
            )
            groups.append(_contact_group(
                'students',
                'My students',
                [_contact(student, sections.get(student.pk)) for student in students],
                'No students are enrolled in your classes yet. Students appear here after '
                'they join one of your sections with its enrollment code.',
            ))
            included_ids.update(student.pk for student in students)

            admins = (
                User.objects.filter(
                    is_active=True,
                    classstamp_profile__role=Profile.ROLE_ADMIN,
                )
                .exclude(pk=user.pk)
                .select_related('classstamp_profile__department')
            )
            groups.append(_contact_group(
                'administrators',
                'Administration',
                [_contact(admin) for admin in admins],
            ))
            included_ids.update(admin.pk for admin in admins)

        elif profile.role == Profile.ROLE_STUDENT:
            sections = _enrollment_sections(
                Enrollment.objects.filter(
                    student_profile=profile,
                    class_obj__academic_year__is_active=True,
                    status=Enrollment.STATUS_ACTIVE,
                ),
                'class_obj__teacher_profile__user_id',
                'class_obj__section_code',
                'class_obj__class_code',
                'class_obj__subject__code',
            )
            teachers = (
                User.objects.filter(pk__in=list(sections), is_active=True)
                .exclude(pk=user.pk)
                .select_related('classstamp_profile__department')
            )
            groups.append(_contact_group(
                'instructors',
                'My instructors',
                [_contact(teacher, sections.get(teacher.pk)) for teacher in teachers],
                'You are not enrolled in any class yet. Your instructors appear here '
                'after your enrollment is approved.',
            ))
            included_ids.update(teacher.pk for teacher in teachers)

            # No Administration group: students may only write to instructors.

        else:
            return []

        # Existing conversations remain replyable even when the enrollment that
        # started them is gone; can_contact() already allows that, so the
        # picker must not hide the recipient.
        history_filter = (
            User.objects.filter(
                Q(sent_messages__recipient=user) | Q(received_messages__sender=user),
                is_active=True,
            )
            .exclude(pk=user.pk)
            .select_related('classstamp_profile__department')
            .distinct()
        )
        if profile.role == Profile.ROLE_STUDENT:
            history_filter = history_filter.filter(
                classstamp_profile__role=Profile.ROLE_TEACHER,
            )
        history_users = history_filter
        history_contacts = [
            _contact(other) for other in history_users if other.pk not in included_ids
        ]
        if history_contacts:
            groups.append(_contact_group(
                'history', 'Previous conversations', history_contacts,
            ))

        return groups

    @staticmethod
    def eligible_recipients(user):
        """Flat list of users this sender may contact, for the compose picker."""
        contacts = []
        seen = set()
        for group in MessageService.recipient_groups(user):
            for contact in group['contacts']:
                if contact['user'].pk in seen:
                    continue
                seen.add(contact['user'].pk)
                contacts.append(contact['user'])
        return contacts

    @staticmethod
    def class_targets(user):
        """
        // Classes a teacher can message as a group, with the number of students
        // already enrolled. The compose picker turns each row into one option,
        // so selecting a subject/class includes every enrolled student without
        // ticking them one by one.
        """
        profile = getattr(user, 'classstamp_profile', None)
        if profile is None or profile.role != Profile.ROLE_TEACHER:
            return []
        return list(
            Class.objects.filter(
                teacher_profile=profile,
                is_active=True,
                academic_year__is_active=True,
            )
            .annotate(
                recipient_count=Count(
                    'enrollments',
                    filter=Q(
                        enrollments__status=Enrollment.STATUS_ACTIVE,
                        enrollments__student_profile__user__is_active=True,
                    ),
                )
            )
            .select_related('subject')
            .order_by('class_code')
        )

    @staticmethod
    def send_to_class(*, sender, class_id, subject, body):
        """
        // One message per actively enrolled student in the teacher's class.
        // Each student keeps a private thread; no group-address leakage.
        // Returns (sent_count, class_obj). Raises MessageError on bad input.
        """
        profile = getattr(sender, 'classstamp_profile', None)
        if profile is None or profile.role != Profile.ROLE_TEACHER:
            raise MessageError('Only instructors can message a whole class.')

        try:
            class_pk = int(class_id)
        except (TypeError, ValueError):
            raise MessageError('Choose a class.')

        subject, body = _clean_payload(subject, body)

        class_obj = Class.objects.filter(
            pk=class_pk,
            teacher_profile=profile,
            is_active=True,
            academic_year__is_active=True,
        ).select_related('subject').first()
        if class_obj is None:
            raise MessageError('Choose one of your own active classes.')

        student_ids = list(
            Enrollment.objects.filter(
                class_obj=class_obj,
                status=Enrollment.STATUS_ACTIVE,
            ).values_list('student_profile__user_id', flat=True)
        )
        students = list(
            User.objects.filter(pk__in=student_ids, is_active=True)
            .exclude(pk=sender.pk)
        )
        if not students:
            raise MessageError(
                'No students are enrolled in this class yet, so there is no one to message.'
            )

        with transaction.atomic():
            for student in students:
                MessageService.send(
                    sender=sender,
                    recipient_id=student.pk,
                    subject=subject,
                    body=body,
                )
        return len(students), class_obj

    @staticmethod
    def send(*, sender, recipient_id, subject, body):
        """
        // Create one message after role/enrollment validation.
        // Returns the Message. Raises MessageError — the view turns that into
        // a form error; nothing is truncated to make an invalid send "fit".
        """
        subject, body = _clean_payload(subject, body)

        try:
            recipient_pk = int(recipient_id)
        except (TypeError, ValueError):
            raise MessageError('Choose a recipient.')
        recipient = User.objects.filter(pk=recipient_pk).first()
        if recipient is None:
            raise MessageError('Choose a recipient.')
        if not MessageService.can_contact(sender, recipient):
            raise MessageError(
                'You can only message instructors of your active classes '
                '(or your own students / administrators).'
            )

        with transaction.atomic():
            message = Message.objects.create(
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
            )
            AuditEvent.objects.create(
                actor=sender,
                action='MESSAGE_SENT',
                object_type='Message',
                object_id=str(message.pk),
                new_value=f'{sender.username} -> {recipient.username}: {subject[:120]}',
            )
            create_notification(
                recipient,
                'message',
                f'New message: {subject}',
                (
                    f'{display_name(sender)} sent you a message: {body[:80]}'
                ),
                f'/messages/thread/{sender.pk}/',
            )
            notify_user(
                recipient,
                f'[KCC ClassStamp] New message — {subject}',
                (
                    f'Hello {display_name(recipient)},\n\n'
                    f'{display_name(sender)} sent you a message:\n\n'
                    f'{body}\n\n— KCC ClassStamp Messaging'
                ),
                action='MESSAGE_EMAIL_SENT',
                object_type='Message',
                object_id=message.pk,
            )
        return message

    @staticmethod
    def thread(viewer, other_user_id):
        """
        // Two-user conversation, oldest first. Only a participant (or someone
        // with history) may read it. Returns (other_user, messages) or (None, []).
        """
        from django.db.models import Q

        other = User.objects.filter(pk=other_user_id).select_related(
            'classstamp_profile__department'
        ).first()
        if other is None:
            return None, []
        has_history = Message.objects.filter(
            Q(sender=viewer, recipient=other) | Q(sender=other, recipient=viewer),
        ).exists()
        if not has_history and not MessageService.can_contact(viewer, other):
            return None, []
        messages = list(
            Message.objects.filter(
                Q(sender=viewer, recipient=other) | Q(sender=other, recipient=viewer),
            ).select_related(
                'sender__classstamp_profile__department'
            ).order_by('created_at')
        )
        return other, messages

    @staticmethod
    def mark_thread_as_read(messages, reader) -> int:
        """
        // Opening a thread used to walk every message through mark_as_read,
        // which is one UPDATE plus one AuditEvent per row (P3-2). A long
        // conversation therefore wrote N identical audit rows for one page
        // view. Mark the unread incoming subset in a single UPDATE and keep
        // one batch audit row.
        """
        unread = [
            message for message in messages
            if message.recipient_id == reader.pk and not message.is_read
        ]
        if not unread:
            return 0
        now = timezone.now()
        updated = Message.objects.filter(pk__in=[m.pk for m in unread]).update(
            is_read=True,
            read_at=now,
            updated_at=now,
        )
        for message in unread:
            message.is_read = True
            message.read_at = now
        AuditEvent.objects.create(
            actor=reader,
            action='MESSAGE_READ',
            object_type='Message',
            object_id=','.join(str(m.pk) for m in unread),
            reason=f'Thread opened: {updated} message(s) marked read',
        )
        return updated

    @staticmethod
    def mark_as_read(message, reader) -> bool:
        """Only the recipient may mark a message read. Returns True on change."""
        if message.recipient_id != reader.pk:
            return False
        if message.is_read:
            return True
        message.is_read = True
        message.read_at = timezone.now()
        message.save(update_fields=['is_read', 'read_at', 'updated_at'])
        AuditEvent.objects.create(
            actor=reader,
            action='MESSAGE_READ',
            object_type='Message',
            object_id=str(message.pk),
            reason=f'Read by {reader.username}',
        )
        return True

    @staticmethod
    def conversations(user):
        """
        // Inbox grouped by the other participant: last message + unread count.
        """
        from django.db.models import Q

        related = Message.objects.filter(Q(sender=user) | Q(recipient=user))
        # Map of other_user_id -> latest message id
        latest = {}
        unread = {}
        for message in related.order_by('-created_at').iterator():
            other_id = (
                message.recipient_id if message.sender_id == user.pk
                else message.sender_id
            )
            latest.setdefault(other_id, message)
            if message.recipient_id == user.pk and not message.is_read:
                unread[other_id] = unread.get(other_id, 0) + 1

        other_ids = list(latest.keys())
        users = {
            u.pk: u
            for u in User.objects.filter(pk__in=other_ids).select_related(
                'classstamp_profile__department'
            )
        }
        rows = []
        for other_id, last in latest.items():
            other = users.get(other_id)
            if other is None:
                continue
            rows.append({
                'other': other,
                'last_message': last,
                'unread': unread.get(other_id, 0),
                'is_mine': last.sender_id == user.pk,
                'name': display_name(other),
                'role': role_label(other),
                'role_key': role_key(other),
                'role_badge': role_badge_class(other),
                'meta': contact_meta(other),
                'read_only': (
                    _profile_role(user) == Profile.ROLE_STUDENT
                    and _is_admin(other)
                ),
            })
        rows.sort(key=lambda row: row['last_message'].created_at, reverse=True)
        return rows

    @staticmethod
    def unread_count(user) -> int:
        return Message.objects.filter(recipient=user, is_read=False).count()
