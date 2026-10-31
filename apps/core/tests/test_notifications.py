"""
# // ==============================================================================
# // KCC CLASSSTAMP - NOTIFICATION SERVICE TESTS
# // ==============================================================================
# // Delivery, skip paths, audit trail, and the at-risk mailer command.
# // The test runner swaps in the locmem email backend, so mail.outbox is the
# // assertion surface.
# ==============================================================================
"""

from datetime import date, time
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    ExcuseSlip,
    Profile,
    Program,
    Subject,
)
from apps.core.services.notification_service import (
    notify_at_risk,
    notify_excuse_decision,
    notify_user,
)

User = get_user_model()


class NotifyUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='notify_user', email='student@example.com', first_name='Ana',
        )

    def test_sends_and_audits(self):
        delivered = notify_user(self.user, 'Subject line', 'Body text')

        self.assertTrue(delivered)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student@example.com'])
        self.assertTrue(AuditEvent.objects.filter(action='NOTIFICATION_SENT').exists())

    def test_missing_address_is_skipped_and_recorded(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])

        delivered = notify_user(self.user, 'Subject line', 'Body text')

        self.assertFalse(delivered)
        self.assertEqual(len(mail.outbox), 0)
        event = AuditEvent.objects.get(action='NOTIFICATION_SENT')
        self.assertIn('no email address', event.reason)

    @override_settings(NOTIFICATIONS_ENABLED=False)
    def test_disabled_switch_sends_nothing(self):
        delivered = notify_user(self.user, 'Subject line', 'Body text')

        self.assertFalse(delivered)
        self.assertEqual(len(mail.outbox), 0)

    def test_none_user_is_a_noop(self):
        self.assertFalse(notify_user(None, 'Subject', 'Body'))


class ExcuseDecisionNotificationTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='exc_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.student_user = User.objects.create_user(
            username='exc_student', email='ana@example.com', first_name='Ana',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-6001',
            program=self.program,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.session = ClassSession.objects.create(
            slot=slot, session_date=today, status=ClassSession.STATUS_CLOSED,
        )
        AttendanceRecord.objects.create(
            session=self.session, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_ABSENT,
            method=AttendanceRecord.METHOD_SYSTEM,
        )
        self.slip = ExcuseSlip.objects.create(
            student_profile=self.student_profile,
            session=self.session,
            reason='Medical appointment',
        )

    def test_approval_notifies_the_student(self):
        notify_excuse_decision(self.slip, approved=True)

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('BSIT-1A', body)
        self.assertIn('APPROVED', body)

    def test_rejection_includes_the_reviewer_note(self):
        notify_excuse_decision(self.slip, approved=False, note='No supporting document')

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('REJECTED', mail.outbox[0].body)
        self.assertIn('No supporting document', mail.outbox[0].body)


class AtRiskMailerTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='risk_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.student_user = User.objects.create_user(
            username='risk_student', email='risk@example.com', first_name='Ben',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-7001',
            program=self.program,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        session = ClassSession.objects.create(
            slot=slot, session_date=today, status=ClassSession.STATUS_CLOSED,
        )
        Enrollment.objects.create(
            student_profile=self.student_profile, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        AttendanceRecord.objects.create(
            session=session, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_ABSENT,
            method=AttendanceRecord.METHOD_SYSTEM,
        )

    def test_dry_run_sends_nothing(self):
        out = StringIO()
        call_command('notify_at_risk', '--dry-run', stdout=out)

        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('DRY-RUN', out.getvalue())

    def test_real_run_mails_at_risk_students(self):
        out = StringIO()
        call_command('notify_at_risk', stdout=out)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('BSIT-1A', mail.outbox[0].body)
        self.assertIn('Emailed 1', out.getvalue())

    def test_student_below_threshold_is_not_mailed(self):
        call_command('notify_at_risk', '--threshold', '150', stdout=StringIO())

        self.assertEqual(len(mail.outbox), 0)

    def test_direct_notify_helper(self):
        delivered = notify_at_risk(self.student_profile, self.class_obj, 100.0, 20)

        self.assertTrue(delivered)
        self.assertIn('100.0%', mail.outbox[0].body)
