"""
# // ==============================================================================
# // KCC CLASSSTAMP - INTERNAL MESSAGING TESTS (tasks 4.8 / 4.9)
# // ==============================================================================
# // Role pairs, enrollment gating, thread privacy, read authorization,
# // notifications, empty states, CSRF, and boundary length validation.
# // ==============================================================================
"""

from datetime import date, time

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
from apps.core.models.messaging import Message
from apps.core.services.message_service import (
    MAX_BODY,
    MAX_SUBJECT,
    MessageError,
    MessageService,
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
        self.assertEqual(response.status_code, 403)

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
