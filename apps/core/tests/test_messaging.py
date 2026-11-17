"""
# // ==============================================================================
# // KCC CLASSSTAMP - INTERNAL MESSAGING TESTS (tasks 4.8 / 4.9)
# // ==============================================================================
# // Role pairs, enrollment gating, thread privacy, read authorization,
# // notifications, empty states, CSRF, and boundary length validation.
# // ==============================================================================
"""

from datetime import date, time

from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSlot,
    Department,
    Enrollment,
    Notification,
    Profile,
    Program,
    Subject,
)
from apps.core.admin import MessageAdmin
from apps.core.models.messaging import Message
from apps.core.services.message_service import (
    MAX_BODY,
    MAX_SUBJECT,
    MessageError,
    MessageService,
    display_name,
    role_label,
)

User = get_user_model()


class MessagingFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(code='CCS', name='Computer Studies')
        cls.program = Program.objects.create(
            department=cls.department, code='BSIT', name='Information Technology',
        )
        cls.subject = Subject.objects.create(code='IT311', name='Web Development')
        cls.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        cls.teacher_user = User.objects.create_user(
            username='msg_teacher', email='msg_teacher@example.com', first_name='Tina',
        )
        cls.teacher = Profile.objects.create(
            user=cls.teacher_user, role=Profile.ROLE_TEACHER, department=cls.department,
        )
        cls.other_teacher_user = User.objects.create_user(
            username='msg_other_teacher', email='msg_other@example.com',
        )
        cls.other_teacher = Profile.objects.create(
            user=cls.other_teacher_user, role=Profile.ROLE_TEACHER, department=cls.department,
        )
        cls.admin_user = User.objects.create_user(
            username='msg_admin', email='msg_admin@example.com',
        )
        Profile.objects.create(user=cls.admin_user, role=Profile.ROLE_ADMIN)
        cls.student_user = User.objects.create_user(
            username='msg_student', email='msg_student@example.com', first_name='Sam',
        )
        cls.student = Profile.objects.create(
            user=cls.student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-8200', program=cls.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        cls.other_student_user = User.objects.create_user(
            username='msg_other_student', email='msg_other_student@example.com',
        )
        cls.other_student = Profile.objects.create(
            user=cls.other_student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-8201', program=cls.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        cls.class_obj = Class.objects.create(
            academic_year=cls.year, class_code='BSIT-3A-IT311', subject=cls.subject,
            teacher_profile=cls.teacher, program=cls.program, year_level=3,
        )
        ClassSlot.objects.create(
            class_obj=cls.class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        Enrollment.objects.create(
            student_profile=cls.student, class_obj=cls.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )


class MessageServiceTests(MessagingFixtureMixin, TestCase):
    def test_student_may_message_own_active_teacher(self):
        self.assertTrue(MessageService.can_contact(self.student_user, self.teacher_user))

    def test_student_cannot_message_unrelated_teacher(self):
        self.assertFalse(MessageService.can_contact(self.student_user, self.other_teacher_user))

    def test_teacher_may_message_enrolled_student(self):
        self.assertTrue(MessageService.can_contact(self.teacher_user, self.student_user))

    def test_teacher_cannot_message_unenrolled_student(self):
        self.assertFalse(MessageService.can_contact(self.teacher_user, self.other_student_user))

    def test_teacher_may_message_admin_without_enrollment(self):
        self.assertTrue(MessageService.can_contact(self.teacher_user, self.admin_user))

    def test_admin_may_message_anyone(self):
        self.assertTrue(MessageService.can_contact(self.admin_user, self.student_user))
        self.assertTrue(MessageService.can_contact(self.admin_user, self.other_teacher_user))

    def test_student_cannot_message_admin_or_peer(self):
        self.assertFalse(MessageService.can_contact(self.student_user, self.admin_user))
        self.assertFalse(MessageService.can_contact(self.student_user, self.other_student_user))

    def test_student_cannot_reply_to_an_administrator_even_with_history(self):
        MessageService.send(
            sender=self.admin_user,
            recipient_id=self.student_user.pk,
            subject='Please call the office',
            body='Reply with your preferred time.',
        )

        # Admin -> student announcements may exist, but the student side is
        # read-only: students may only write to their instructors.
        self.assertFalse(MessageService.can_contact(self.student_user, self.admin_user))
        recipients = list(MessageService.eligible_recipients(self.student_user))
        self.assertNotIn(self.admin_user, recipients)
        groups = MessageService.recipient_groups(self.student_user)
        self.assertEqual([group['key'] for group in groups], ['instructors'])

    def test_self_and_inactive_recipients_are_denied(self):
        self.assertFalse(MessageService.can_contact(self.student_user, self.student_user))
        self.other_teacher_user.is_active = False
        self.other_teacher_user.save()
        self.assertFalse(MessageService.can_contact(self.admin_user, self.other_teacher_user))

    def test_send_creates_message_audit_and_notifications(self):
        message = MessageService.send(
            sender=self.student_user,
            recipient_id=self.teacher_user.pk,
            subject='Question about IT311',
            body='Will the lab on Friday be moved?',
        )
        self.assertEqual(message.recipient, self.teacher_user)
        self.assertFalse(message.is_read)
        self.assertTrue(
            AuditEvent.objects.filter(
                action='MESSAGE_SENT', object_id=str(message.pk),
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.teacher_user, category='message',
            ).exists()
        )

    def test_send_rejects_unrelated_recipient(self):
        with self.assertRaises(MessageError):
            MessageService.send(
                sender=self.student_user,
                recipient_id=self.other_teacher_user.pk,
                subject='Hello',
                body='Are you my teacher?',
            )

    def test_send_enforces_subject_and_body_limits_without_truncation(self):
        with self.assertRaises(MessageError) as ctx:
            MessageService.send(
                sender=self.student_user,
                recipient_id=self.teacher_user.pk,
                subject='x' * (MAX_SUBJECT + 1),
                body='hello',
            )
        self.assertIn('too long', str(ctx.exception))

        with self.assertRaises(MessageError) as ctx:
            MessageService.send(
                sender=self.student_user,
                recipient_id=self.teacher_user.pk,
                subject='Hello',
                body='x' * (MAX_BODY + 1),
            )
        self.assertIn('too long', str(ctx.exception))

        self.assertFalse(
            Message.objects.filter(subject='x' * MAX_SUBJECT).exists()
        )

    def test_send_rejects_blank_and_self(self):
        with self.assertRaises(MessageError):
            MessageService.send(
                sender=self.student_user,
                recipient_id=self.teacher_user.pk,
                subject='   ',
                body='hello',
            )
        with self.assertRaises(MessageError):
            MessageService.send(
                sender=self.student_user,
                recipient_id=self.student_user.pk,
                subject='Note to self',
                body='hello',
            )

    def test_thread_is_private_to_participants(self):
        MessageService.send(
            sender=self.student_user,
            recipient_id=self.teacher_user.pk,
            subject='Private',
            body='Only we can see this.',
        )
        other, messages = MessageService.thread(self.other_student_user, self.teacher_user.pk)
        # Unrelated student has no history and cannot contact this teacher.
        self.assertIsNone(other)
        self.assertEqual(messages, [])

        other, messages = MessageService.thread(self.student_user, self.teacher_user.pk)
        self.assertEqual(other, self.teacher_user)
        self.assertEqual(len(messages), 1)

    def test_mark_as_read_is_recipient_only(self):
        message = MessageService.send(
            sender=self.student_user,
            recipient_id=self.teacher_user.pk,
            subject='Read me',
            body='Body',
        )
        # Sender cannot mark their own outgoing message read.
        self.assertFalse(MessageService.mark_as_read(message, self.student_user))
        self.assertTrue(MessageService.mark_as_read(message, self.teacher_user))
        message.refresh_from_db()
        self.assertTrue(message.is_read)
        self.assertIsNotNone(message.read_at)
        # Idempotent.
        self.assertTrue(MessageService.mark_as_read(message, self.teacher_user))

    def test_eligible_recipients_for_each_role(self):
        student_choices = MessageService.eligible_recipients(self.student_user)
        self.assertIn(self.teacher_user, student_choices)
        self.assertNotIn(self.other_teacher_user, student_choices)
        self.assertNotIn(self.admin_user, student_choices)

        teacher_choices = MessageService.eligible_recipients(self.teacher_user)
        self.assertIn(self.student_user, teacher_choices)
        self.assertIn(self.admin_user, teacher_choices)
        self.assertNotIn(self.other_student_user, teacher_choices)

        admin_choices = MessageService.eligible_recipients(self.admin_user)
        self.assertIn(self.student_user, admin_choices)
        self.assertIn(self.teacher_user, admin_choices)

    def test_send_notification_links_to_the_thread(self):
        MessageService.send(
            sender=self.student_user,
            recipient_id=self.teacher_user.pk,
            subject='Deep link',
            body='Should open the conversation, not the inbox.',
        )
        notification = Notification.objects.filter(
            user=self.teacher_user, category='message',
        ).order_by('-pk').first()
        self.assertIsNotNone(notification)
        self.assertEqual(
            notification.link,
            f'/messages/thread/{self.student_user.pk}/',
        )

    def test_thread_selects_related_sender(self):
        MessageService.send(
            sender=self.student_user,
            recipient_id=self.teacher_user.pk,
            subject='No N+1',
            body='Body',
        )
        other, messages = MessageService.thread(self.student_user, self.teacher_user.pk)
        self.assertEqual(other, self.teacher_user)
        self.assertEqual(len(messages), 1)
        # select_related('sender') must already have the user; no extra query.
        with self.assertNumQueries(0):
            self.assertEqual(messages[0].sender.username, 'msg_student')

    def test_message_admin_is_read_only(self):
        message_admin = MessageAdmin(Message, AdminSite())
        self.assertFalse(message_admin.has_add_permission(None))
        self.assertFalse(message_admin.has_delete_permission(None))
        self.assertIn('sender', message_admin.list_select_related)
        self.assertIn('recipient', message_admin.list_select_related)

    def test_display_name_uses_role_when_the_account_has_no_name(self):
        unnamed_admin = User.objects.create_user(username='unnamed_admin')
        Profile.objects.create(user=unnamed_admin, role=Profile.ROLE_ADMIN)
        self.assertEqual(display_name(unnamed_admin), 'Administrator')
        self.assertEqual(display_name(self.student_user), 'Sam')
        self.assertEqual(role_label(self.student_user), 'Student')

    def test_teacher_groups_list_enrolled_students_with_their_section(self):
        groups = MessageService.recipient_groups(self.teacher_user)
        student_group = next(group for group in groups if group['key'] == 'students')
        self.assertEqual(student_group['label'], 'My students')
        students = [contact['user'] for contact in student_group['contacts']]
        self.assertIn(self.student_user, students)
        self.assertNotIn(self.other_student_user, students)

        contact = next(
            row for row in student_group['contacts'] if row['user'] == self.student_user
        )
        self.assertEqual(contact['role'], 'Student')
        self.assertIn('2026-8200', contact['meta'])
        self.assertIn('BSIT-3A', contact['meta'])
        self.assertIn('IT311', contact['meta'])

        admin_group = next(group for group in groups if group['key'] == 'administrators')
        self.assertIn(self.admin_user, [row['user'] for row in admin_group['contacts']])

    def test_student_groups_list_only_their_own_instructors(self):
        groups = MessageService.recipient_groups(self.student_user)
        teacher_group = next(group for group in groups if group['key'] == 'instructors')
        teachers = [contact['user'] for contact in teacher_group['contacts']]
        self.assertIn(self.teacher_user, teachers)
        self.assertNotIn(self.other_teacher_user, teachers)
        self.assertNotIn(self.admin_user, teachers)

        contact = next(
            row for row in teacher_group['contacts'] if row['user'] == self.teacher_user
        )
        self.assertEqual(contact['role'], 'Instructor')
        self.assertIn('BSIT-3A', contact['meta'])
        self.assertIn('IT311', contact['meta'])

    def test_admin_groups_are_split_by_role_and_exclude_self(self):
        groups = MessageService.recipient_groups(self.admin_user)
        self.assertEqual(
            [group['key'] for group in groups],
            ['instructors', 'students', 'administrators', 'other'],
        )
        instructors = next(group for group in groups if group['key'] == 'instructors')
        students = next(group for group in groups if group['key'] == 'students')
        self.assertIn(self.teacher_user, [row['user'] for row in instructors['contacts']])
        self.assertIn(self.student_user, [row['user'] for row in students['contacts']])
        everyone = [
            row['user'] for group in groups for row in group['contacts']
        ]
        self.assertNotIn(self.admin_user, everyone)

    def test_previous_conversation_stays_in_the_picker_without_enrollment(self):
        # The enrollment is withdrawn after the thread started; the reply still
        # has to have a recipient in the compose picker.
        MessageService.send(
            sender=self.teacher_user,
            recipient_id=self.student_user.pk,
            subject='Before withdrawal',
            body='Keep this thread reachable.',
        )
        Enrollment.objects.filter(
            student_profile=self.student, class_obj=self.class_obj,
        ).update(status=Enrollment.STATUS_WITHDRAWN)
        groups = MessageService.recipient_groups(self.teacher_user)
        history = next(group for group in groups if group['key'] == 'history')
        self.assertIn(self.student_user, [row['user'] for row in history['contacts']])
        self.assertTrue(MessageService.can_contact(self.teacher_user, self.student_user))

    def test_class_targets_count_only_active_enrollments(self):
        targets = MessageService.class_targets(self.teacher_user)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].pk, self.class_obj.pk)
        self.assertEqual(targets[0].recipient_count, 1)

        Enrollment.objects.create(
            student_profile=self.other_student,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_WITHDRAWN,
        )
        targets = MessageService.class_targets(self.teacher_user)
        self.assertEqual(targets[0].recipient_count, 1)

        self.assertEqual(MessageService.class_targets(self.student_user), [])
        self.assertEqual(MessageService.class_targets(self.other_teacher_user), [])


class MessageViewTests(MessagingFixtureMixin, TestCase):
    def setUp(self):
        self.client = Client()

    def test_compose_without_csrf_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.student_user)
        response = csrf_client.post(reverse('message_compose'), {
            'recipient': self.teacher_user.pk,
            'subject': 'No token',
            'body': 'Should fail',
        })
        # The site installs CSRF_FAILURE_VIEW: a browser post is sent back to the
        # form with a retry message (302); the bare 403 is reserved for AJAX.
        self.assertIn(response.status_code, (302, 403))
        # Whatever the shape of the refusal, nothing may reach the outbox.
        self.assertFalse(Message.objects.exists())

    def test_inbox_empty_then_conversation(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('message_inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No conversations yet')

        MessageService.send(
            sender=self.teacher_user,
            recipient_id=self.student_user.pk,
            subject='Lab reminder',
            body='Bring your laptop.',
        )
        response = self.client.get(reverse('message_inbox'))
        self.assertContains(response, 'Lab reminder')
        self.assertContains(response, '1 new')

    def test_compose_and_thread_round_trip(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse('message_compose'), {
            'recipient': self.teacher_user.pk,
            'subject': 'Question',
            'body': 'Is the deadline extended?',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('message_thread', args=[self.teacher_user.pk]),
        )

        # Recipient sees the message; opening the thread marks it read.
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('message_inbox'))
        self.assertContains(response, 'Question')
        response = self.client.get(
            reverse('message_thread', args=[self.student_user.pk]),
        )
        self.assertContains(response, 'Is the deadline extended?')
        message = Message.objects.get(subject='Question')
        self.assertTrue(message.is_read)

        # Reply
        response = self.client.post(
            reverse('message_thread', args=[self.student_user.pk]),
            {'subject': 'Re: Question', 'body': 'Yes, one more week.'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 2)

    def test_student_cannot_open_unrelated_thread(self):
        MessageService.send(
            sender=self.teacher_user,
            recipient_id=self.student_user.pk,
            subject='For Sam',
            body='Enrolled student only.',
        )
        self.client.force_login(self.other_student_user)
        response = self.client.get(
            reverse('message_thread', args=[self.teacher_user.pk]),
        )
        # Denied thread redirects back to the inbox.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('message_inbox'))

    def test_compose_rejects_unrelated_recipient(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse('message_compose'), {
            'recipient': self.other_teacher_user.pk,
            'subject': 'Hello',
            'body': 'Are you my teacher?',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'instructors of your active classes')

    def test_messages_require_login(self):
        response = self.client.get(reverse('message_inbox'))
        self.assertEqual(response.status_code, 302)

    def test_inbox_empty_state_copy_matches_role(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('message_inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'instructors of your active classes')
        self.assertNotContains(response, 'your own students or administrators')

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('message_inbox'))
        self.assertContains(response, 'your own students or administrators')
        self.assertNotContains(response, 'instructors of your active classes')

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('message_inbox'))
        self.assertContains(response, 'any active user')

    def test_thread_reply_prefills_latest_subject(self):
        MessageService.send(
            sender=self.student_user,
            recipient_id=self.teacher_user.pk,
            subject='First topic',
            body='hello',
        )
        MessageService.send(
            sender=self.teacher_user,
            recipient_id=self.student_user.pk,
            subject='Latest topic',
            body='hi',
        )
        self.client.force_login(self.student_user)
        response = self.client.get(
            reverse('message_thread', args=[self.teacher_user.pk]),
        )
        self.assertEqual(response.status_code, 200)
        # Reply box quotes the newest subject, not messages[0].
        self.assertContains(response, 'value="Re: Latest topic"')
        self.assertNotContains(response, 'value="Re: First topic"')

    def test_thread_auto_scrolls_with_csp_nonce(self):
        self.client.force_login(self.student_user)
        response = self.client.get(
            reverse('message_thread', args=[self.teacher_user.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "querySelector('.msg-log')")
        self.assertContains(response, 'nonce=')

    def test_admin_feedback_reaches_the_teacher_and_teacher_can_reply(self):
        MessageService.send(
            sender=self.admin_user,
            recipient_id=self.teacher_user.pk,
            subject='Observation feedback',
            body='Please adjust the rubric for the lab component.',
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('message_inbox'))
        self.assertContains(response, 'Observation feedback')
        self.assertContains(response, 'Administrator')

        response = self.client.get(
            reverse('message_thread', args=[self.admin_user.pk]),
        )
        self.assertContains(response, 'Please adjust the rubric for the lab component.')
        self.assertContains(response, 'Administrator')

        response = self.client.post(
            reverse('message_thread', args=[self.admin_user.pk]),
            {'subject': 'Re: Observation feedback', 'body': 'Noted, I will update it.'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Message.objects.filter(
                sender=self.teacher_user,
                recipient=self.admin_user,
                body='Noted, I will update it.',
            ).exists()
        )

    def test_teacher_messages_enrolled_student_and_student_replies(self):
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('message_compose'), {
            'recipient': self.student_user.pk,
            'subject': 'Missing lab output',
            'body': 'Please submit the week 4 output.',
        })
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.student_user)
        response = self.client.get(
            reverse('message_thread', args=[self.teacher_user.pk]),
        )
        self.assertContains(response, 'Missing lab output')
        self.assertContains(response, 'Instructor')

        response = self.client.post(
            reverse('message_thread', args=[self.teacher_user.pk]),
            {'subject': 'Re: Missing lab output', 'body': 'Uploading it tonight.'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Message.objects.filter(
                sender=self.student_user,
                recipient=self.teacher_user,
                body='Uploading it tonight.',
            ).exists()
        )

    def test_compose_renders_grouped_searchable_picker(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('message_compose'))
        self.assertContains(response, '<optgroup label="My students">')
        self.assertContains(response, '<optgroup label="Administration">')
        self.assertContains(response, '2026-8200')
        self.assertContains(response, 'recipient-search')

    def test_inbox_shows_role_meta_and_marks_own_last_message(self):
        MessageService.send(
            sender=self.teacher_user,
            recipient_id=self.student_user.pk,
            subject='From your instructor',
            body='Bring your notebook.',
        )
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('message_inbox'))
        self.assertContains(response, 'You:')
        self.assertContains(response, 'badge--success')
        self.assertContains(response, '2026-8200')

    def test_student_admin_thread_is_read_only_in_the_ui(self):
        MessageService.send(
            sender=self.admin_user,
            recipient_id=self.student_user.pk,
            subject='Office notice',
            body='Please visit the registrar.',
        )

        self.client.force_login(self.student_user)
        response = self.client.get(
            reverse('message_thread', args=[self.admin_user.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Students can only reply to their instructors.')
        self.assertNotContains(response, 'name="body"')

        # A crafted POST must not create a student -> admin message either.
        response = self.client.post(
            reverse('message_thread', args=[self.admin_user.pk]),
            {'subject': 'Re: Office notice', 'body': 'I will visit.'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 1)
        self.assertFalse(
            Message.objects.filter(sender=self.student_user, recipient=self.admin_user).exists()
        )

    def test_student_compose_never_offers_administrators(self):
        MessageService.send(
            sender=self.admin_user,
            recipient_id=self.student_user.pk,
            subject='Office notice',
            body='Please visit the registrar.',
        )

        self.client.force_login(self.student_user)
        response = self.client.get(reverse('message_compose'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<optgroup label="My instructors">')
        self.assertNotContains(response, '<optgroup label="Administration">')
        self.assertNotContains(response, 'Administrator')

    def test_teacher_can_message_a_whole_class_without_picking_students(self):
        Enrollment.objects.create(
            student_profile=self.other_student,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('message_compose'), {
            'recipient': f'class:{self.class_obj.pk}',
            'subject': 'Week 5 reminder',
            'body': 'Submit the lab output before Friday.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('message_inbox'))
        self.assertEqual(
            Message.objects.filter(subject='Week 5 reminder').count(), 2,
        )
        self.assertTrue(
            Message.objects.filter(
                sender=self.teacher_user,
                recipient=self.student_user,
                subject='Week 5 reminder',
            ).exists()
        )
        self.assertTrue(
            Message.objects.filter(
                sender=self.teacher_user,
                recipient=self.other_student_user,
                subject='Week 5 reminder',
            ).exists()
        )

    def test_class_message_skips_students_who_are_not_enrolled(self):
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('message_compose'), {
            'recipient': f'class:{self.class_obj.pk}',
            'subject': 'Enrolled only',
            'body': 'This should reach one student.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 1)
        self.assertFalse(
            Message.objects.filter(recipient=self.other_student_user).exists()
        )

    def test_teacher_cannot_message_someone_elses_class(self):
        other_class = Class.objects.create(
            academic_year=self.year,
            class_code='BSIT-3B-IT311',
            subject=self.subject,
            teacher_profile=self.other_teacher,
            program=self.program,
            year_level=3,
        )
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('message_compose'), {
            'recipient': f'class:{other_class.pk}',
            'subject': 'Not mine',
            'body': 'Should be rejected.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'your own active classes')
        self.assertFalse(Message.objects.exists())

    def test_student_cannot_use_a_class_recipient(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse('message_compose'), {
            'recipient': f'class:{self.class_obj.pk}',
            'subject': 'Nope',
            'body': 'Students cannot address a class.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Only instructors can message a whole class.')
        self.assertFalse(Message.objects.exists())

    def test_teacher_compose_offers_whole_class_option_with_enrolled_count(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('message_compose'))
        self.assertContains(response, '<optgroup label="Whole class">')
        self.assertContains(response, 'BSIT-3A-IT311')
        self.assertContains(response, '(1 enrolled)')

    def test_single_recipient_is_preselected(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('message_compose'))
        self.assertContains(
            response,
            f'value="{self.teacher_user.pk}" selected',
        )
