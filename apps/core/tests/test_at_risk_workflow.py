"""
# // ==============================================================================
# // KCC CLASSSTAMP - AT-RISK DAILY WORKFLOW TESTS (task 4.4)
# // ==============================================================================
# // notify_at_risk: canonical radar calculation, one OPEN flag per
# // student/class/year, student+teacher email and in-app, RESOLVED when the
# // rate drops, dry-run mutates nothing, run totals are audited.
# // ==============================================================================
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AnomalyFlag,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    Notification,
    Profile,
    Program,
    Subject,
)

User = get_user_model()

RULE = 'RULE_AT_RISK_ABSENCE'


class AtRiskWorkflowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(
            username='risk_wf_teacher', email='risk_wf_teacher@example.com',
        )
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.student_user = User.objects.create_user(
            username='risk_wf_student', email='risk_wf_student@example.com',
        )
        self.student = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-8100', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3A-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
        )
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        Enrollment.objects.create(
            student_profile=self.student, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

    def _session(self, days_ago, status=ClassSession.STATUS_CLOSED):
        return ClassSession.objects.create(
            slot=self.slot,
            session_date=timezone.localdate() - timedelta(days=days_ago),
            status=status,
            created_by=self.teacher_user,
        )

    def _record(self, session, status):
        return AttendanceRecord.objects.create(
            session=session, student_profile=self.student, status=status,
            method=AttendanceRecord.METHOD_SYSTEM,
        )

    def _seed_at_threshold(self):
        """5 finalized records, 1 ABSENT = 20.0% (default CHED threshold)."""
        for days in range(5):
            session = self._session(days + 1)
            status = (
                AttendanceRecord.STATUS_ABSENT if days == 0
                else AttendanceRecord.STATUS_PRESENT
            )
            self._record(session, status)

    def test_at_threshold_creates_one_flag_and_notifies_both_parties(self):
        self._seed_at_threshold()
        call_command('notify_at_risk', stdout=__import__('io').StringIO())

        flags = AnomalyFlag.objects.filter(
            student_profile=self.student,
            class_obj=self.class_obj,
            academic_year=self.year,
            rule_code=RULE,
        )
        self.assertEqual(flags.count(), 1)
        flag = flags.first()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_OPEN)
        self.assertIsNone(flag.resolved_at)
        self.assertIsNone(flag.attendance_record)
        self.assertIsNone(flag.session)

        # Student + teacher emails.
        recipients = {addr for message in mail.outbox for addr in message.to}
        self.assertIn('risk_wf_student@example.com', recipients)
        self.assertIn('risk_wf_teacher@example.com', recipients)

        # In-app for both (push flows through create_notification).
        self.assertTrue(
            Notification.objects.filter(
                user=self.student_user, category='attendance',
                title='Attendance warning',
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.teacher_user, category='attendance',
                title='Student at risk',
            ).exists()
        )

        self.assertTrue(
            AuditEvent.objects.filter(action='AT_RISK_FLAG_CREATED').exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action='AT_RISK_RUN_COMPLETE').exists()
        )

    def test_second_run_does_not_duplicate_the_open_flag(self):
        self._seed_at_threshold()
        out = __import__('io').StringIO()
        call_command('notify_at_risk', stdout=out)
        call_command('notify_at_risk', stdout=out)

        self.assertEqual(
            AnomalyFlag.objects.filter(
                student_profile=self.student, rule_code=RULE,
                status=AnomalyFlag.STATUS_OPEN,
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(action='AT_RISK_FLAG_CREATED').count(),
            1,
        )

    def test_rate_below_threshold_resolves_the_flag(self):
        self._seed_at_threshold()
        call_command('notify_at_risk', stdout=__import__('io').StringIO())
        flag = AnomalyFlag.objects.get(rule_code=RULE)
        self.assertEqual(flag.status, AnomalyFlag.STATUS_OPEN)

        # Approve-style correction: the absence becomes EXCUSED, rate 0%.
        absent_record = AttendanceRecord.objects.get(status=AttendanceRecord.STATUS_ABSENT)
        absent_record.status = AttendanceRecord.STATUS_EXCUSED
        absent_record.save()

        call_command('notify_at_risk', stdout=__import__('io').StringIO())

        flag.refresh_from_db()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_RESOLVED)
        self.assertIsNotNone(flag.resolved_at)
        self.assertTrue(
            AuditEvent.objects.filter(action='AT_RISK_FLAG_RESOLVED').exists()
        )

    def test_just_below_threshold_is_not_at_risk(self):
        # 1/6 = 16.7% < 20%.
        self._seed_at_threshold()
        extra = self._session(10)
        self._record(extra, AttendanceRecord.STATUS_PRESENT)

        call_command('notify_at_risk', stdout=__import__('io').StringIO())
        self.assertFalse(AnomalyFlag.objects.filter(rule_code=RULE).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_dry_run_creates_no_flags_notifications_or_mail(self):
        self._seed_at_threshold()
        out = __import__('io').StringIO()
        call_command('notify_at_risk', '--dry-run', stdout=out)

        self.assertIn('DRY-RUN', out.getvalue())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AnomalyFlag.objects.filter(rule_code=RULE).count(), 0)
        self.assertEqual(Notification.objects.filter(category='attendance').count(), 0)
        self.assertFalse(
            AuditEvent.objects.filter(action='AT_RISK_RUN_COMPLETE').exists()
        )

    def test_dry_run_does_not_resolve_existing_flags(self):
        self._seed_at_threshold()
        call_command('notify_at_risk', stdout=__import__('io').StringIO())
        flag = AnomalyFlag.objects.get(rule_code=RULE)

        absent_record = AttendanceRecord.objects.get(status=AttendanceRecord.STATUS_ABSENT)
        absent_record.status = AttendanceRecord.STATUS_EXCUSED
        absent_record.save()

        call_command('notify_at_risk', '--dry-run', stdout=__import__('io').StringIO())
        flag.refresh_from_db()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_OPEN)
