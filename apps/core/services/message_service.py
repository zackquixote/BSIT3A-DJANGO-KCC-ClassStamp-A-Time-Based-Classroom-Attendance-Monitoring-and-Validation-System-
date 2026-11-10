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
from django.utils import timezone

from apps.core.models import AuditEvent, Enrollment, Message, Profile
from apps.core.services.in_app_notification_service import create_notification
from apps.core.services.notification_service import notify_user

User = get_user_model()

MAX_SUBJECT = 200
MAX_BODY = 5000


class MessageError(ValueError):
    """Raised when a send/mark operation violates a messaging rule."""


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


class MessageService:
    """Enrollment-aware internal messaging."""

    @staticmethod
    def can_contact(sender, recipient) -> bool:
        if sender is None or recipient is None or sender.pk == recipient.pk:
            return False
        if not recipient.is_active or not sender.is_active:
            return False
        if _is_admin(sender):
            return True

        sender_role = _profile_role(sender)
        recipient_role = _profile_role(recipient)
        sender_profile = getattr(sender, 'classstamp_profile', None)
        recipient_profile = getattr(recipient, 'classstamp_profile', None)

        if sender_role == Profile.ROLE_TEACHER and _is_admin(recipient):
            return True
        if sender_role == Profile.ROLE_TEACHER and recipient_role == Profile.ROLE_STUDENT:
            return bool(
                sender_profile and recipient_profile
                and _has_active_enrollment(recipient_profile, sender_profile)
            )
        if sender_role == Profile.ROLE_STUDENT and recipient_role == Profile.ROLE_TEACHER:
            return bool(
                sender_profile and recipient_profile
                and _has_active_enrollment(sender_profile, recipient_profile)
            )
        return False

    @staticmethod
    def eligible_recipients(user):
        """Users this sender may contact, for the compose picker."""
        if _is_admin(user):
            return User.objects.filter(is_active=True).exclude(pk=user.pk).order_by(
                'first_name', 'last_name', 'username',
            )

        role = _profile_role(user)
        profile = getattr(user, 'classstamp_profile', None)
        if profile is None:
            return User.objects.none()

        if role == Profile.ROLE_TEACHER:
            student_ids = Enrollment.objects.filter(
                class_obj__teacher_profile=profile,
                class_obj__academic_year__is_active=True,
                status=Enrollment.STATUS_ACTIVE,
            ).values_list('student_profile__user_id', flat=True)
            admin_ids = Profile.objects.filter(
                role=Profile.ROLE_ADMIN, user__is_active=True,
            ).values_list('user_id', flat=True)
            return User.objects.filter(is_active=True).filter(
                pk__in=list(set(list(student_ids) + list(admin_ids)))
            ).exclude(pk=user.pk).order_by('first_name', 'last_name', 'username')

        if role == Profile.ROLE_STUDENT:
            teacher_ids = Enrollment.objects.filter(
                student_profile=profile,
                class_obj__academic_year__is_active=True,
                status=Enrollment.STATUS_ACTIVE,
            ).values_list('class_obj__teacher_profile__user_id', flat=True)
            return User.objects.filter(is_active=True, pk__in=teacher_ids).exclude(
                pk=user.pk,
            ).order_by('first_name', 'last_name', 'username')

        return User.objects.none()

    @staticmethod
    def send(*, sender, recipient_id, subject, body):
        """
        // Create one message after role/enrollment validation.
        // Returns the Message. Raises MessageError — the view turns that into
        // a form error; nothing is truncated to make an invalid send "fit".
        """
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

        recipient = User.objects.filter(pk=recipient_id).first()
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
                    f'{sender.get_full_name() or sender.get_username()} sent you '
                    f'a message: {body[:80]}'
                ),
                '/messages/',
            )
            notify_user(
                recipient,
                f'[KCC ClassStamp] New message — {subject}',
                (
                    f'Hello {recipient.get_full_name() or recipient.get_username()},\n\n'
                    f'{sender.get_full_name() or sender.get_username()} sent you a message:\n\n'
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

        other = User.objects.filter(pk=other_user_id).first()
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
            ).order_by('created_at')
        )
        return other, messages

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
        from django.db.models import Q, Max, Count, F

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
            for u in User.objects.filter(pk__in=other_ids)
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
            })
        rows.sort(key=lambda row: row['last_message'].created_at, reverse=True)
        return rows

    @staticmethod
    def unread_count(user) -> int:
        return Message.objects.filter(recipient=user, is_read=False).count()
