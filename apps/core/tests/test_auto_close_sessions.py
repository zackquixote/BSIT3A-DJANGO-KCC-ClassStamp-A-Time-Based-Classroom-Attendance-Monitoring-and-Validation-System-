"""
# // ==============================================================================
# // KCC CLASSSTAMP - AUTO-CLOSE SESSION SCHEDULER TESTS (B-12)
# // ==============================================================================
# // Subsystem: Quality Assurance — Session Lifecycle Automation
# // Description: Verifies the auto_close_sessions management command finalizes
# //   OPEN sessions past slot.ends_at, auto-marks unscanned active enrollees
# //   ABSENT (METHOD_SYSTEM), sets auto_closed=True, audits, and supports
# //   --dry-run / --grace-minutes.
# // ==============================================================================
"""

from datetime import date, time, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
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
    Profile,
    Program,
    Subject,
)

User = get_user_model()


class AutoCloseSessionsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31), is_active=True,
        )

        self.teacher_user = User.objects.create_user(username='ac_teacher', password='Teacher!Pass123')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1A',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            grace_minutes=10,
        )

        self.today = timezone.localdate()
        self.now = timezone.now()
        # Slot times are Asia/Manila wall-clock — derive them from local time.
        self.local_now = timezone.localtime()

    def _make_student(self, index):
        user = User.objects.create_user(username=f'ac_student{index}', password='Student!Pass123')
        profile = Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=f'2026-20{index:02d}',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
            qr_secret='c' * 64,
        )
        Enrollment.objects.create(
            student_profile=profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        return profile

    def _make_session(self, ends_delta, starts_delta=None, weekday=None, session_date=None):
        if starts_delta is None:
            starts_delta = ends_delta - timedelta(hours=1)
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=self.today.weekday() if weekday is None else weekday,
            starts_at=(self.local_now + starts_delta).time(),
            ends_at=(self.local_now + ends_delta).time(),
            room='Room X',
        )
        return ClassSession.objects.create(
            slot=slot,
            session_date=self.today if session_date is None else session_date,
            status=ClassSession.STATUS_OPEN,
            opened_at=self.now - timedelta(hours=2),
            opened_by=self.teacher_user,
            created_by=self.teacher_user,
        )

    def _run(self, *args):
        out = StringIO()
        call_command('auto_close_sessions', *args, stdout=out)
        return out.getvalue()

    def test_due_open_session_is_closed_and_missing_marked_absent(self):
        stamped = self._make_student(1)
        missing = self._make_student(2)
        session = self._make_session(ends_delta=timedelta(hours=-2))

        AttendanceRecord.objects.create(
            session=session,
            student_profile=stamped,
            status=AttendanceRecord.STATUS_PRESENT,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=self.now,
            marked_by=self.teacher_user,
        )

        output = self._run()

        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CLOSED)
        self.assertTrue(session.auto_closed)
        self.assertIsNotNone(session.closed_at)

        missing_records = AttendanceRecord.objects.filter(session=session, student_profile=missing)
        self.assertEqual(missing_records.count(), 1)
        record = missing_records.first()
        self.assertEqual(record.status, AttendanceRecord.STATUS_ABSENT)
        self.assertEqual(record.method, AttendanceRecord.METHOD_SYSTEM)
        self.assertIsNone(record.marked_by)
        self.assertIn('Auto-marked absent', record.correction_reason)

        # Stamped student keeps exactly one record (no duplicate ABSENT)
        self.assertEqual(
            AttendanceRecord.objects.filter(session=session, student_profile=stamped).count(), 1,
        )

        audit = AuditEvent.objects.filter(action='AUTO_CLOSE_SESSION', object_id=str(session.pk))
        self.assertEqual(audit.count(), 1)
        self.assertIn('Closed BSIT-1A', output)
        self.assertIn('1 marked ABSENT', output)

    def test_session_ending_later_remains_open(self):
        # Tomorrow's date keeps this deterministic regardless of wall-clock time;
        # a same-day "+2h" slot wraps past midnight when run after 22:00.
        session = self._make_session(
            ends_delta=timedelta(hours=2),
            session_date=self.today + timedelta(days=1),
        )
        output = self._run()

        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_OPEN)
        self.assertFalse(session.auto_closed)
        self.assertEqual(
            AttendanceRecord.objects.filter(session=session).count(), 0,
        )
        self.assertIn('No OPEN sessions', output)

    def test_dry_run_writes_nothing(self):
        self._make_student(1)
        session = self._make_session(ends_delta=timedelta(hours=-2))

        output = self._run('--dry-run')

        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_OPEN)
        self.assertEqual(AttendanceRecord.objects.filter(session=session).count(), 0)
        self.assertEqual(AuditEvent.objects.filter(action='AUTO_CLOSE_SESSION').count(), 0)
        self.assertIn('DRY-RUN', output)

    def test_grace_minutes_defers_close(self):
        self._make_student(1)
        session = self._make_session(ends_delta=timedelta(minutes=-10))

        output = self._run('--grace-minutes', '30')

        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_OPEN)
        self.assertIn('No OPEN sessions', output)

        # With no grace the same session is due
        self._run()
        session.refresh_from_db()
        self.assertEqual(session.status, ClassSession.STATUS_CLOSED)

    def test_scheduled_and_canceled_sessions_untouched(self):
        # Non-OPEN sessions must never be closed by the scheduler
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=self.today.weekday(),
            starts_at=(self.local_now - timedelta(hours=5)).time(),
            ends_at=(self.local_now - timedelta(hours=4)).time(),
            room='Room Y',
        )
        ClassSession.objects.create(
            slot=slot,
            session_date=self.today,
            status=ClassSession.STATUS_SCHEDULED,
            created_by=self.teacher_user,
        )

        output = self._run()
        self.assertIn('No OPEN sessions', output)
