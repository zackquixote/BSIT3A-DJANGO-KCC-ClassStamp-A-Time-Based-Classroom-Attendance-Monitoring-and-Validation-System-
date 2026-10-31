"""
# // ==============================================================================
# // KCC CLASSSTAMP - HARD ATTENDANCE WINDOW TESTS
# // ==============================================================================
# // The attendance window has two edges:
# //   start -> grace period -> LATE ... scheduled end + tolerance -> REFUSED
# // Covers:
# //   - _scan_window_closed boundary arithmetic (pure, wall-clock independent)
# //   - a scan after class end is refused and logged, not recorded as LATE
# //   - a scan inside the window still stamps LATE (positive control)
# ==============================================================================
"""

from datetime import date, datetime, time, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    Profile,
    Program,
    StampAttempt,
    Subject,
)
from apps.core.services.qr_service import build_payload, current_token
from apps.core.views import session_views

User = get_user_model()

# A fixed midday anchor: keeps the window arithmetic independent of the hour the
# suite happens to run at (a near-midnight run would otherwise wrap slot times).
FIXED_NOW = timezone.make_aware(datetime(2026, 5, 12, 10, 0))


class ScanWindowBoundaryTests(TestCase):
    """Pure boundary checks against _scan_window_closed (no request, no DB rows)."""

    def setUp(self):
        self.slot = ClassSlot(starts_at=time(9, 0), ends_at=time(10, 0))
        self.session = ClassSession(slot=self.slot, session_date=date(2026, 5, 12))

    def _at(self, hour, minute):
        return timezone.make_aware(datetime(2026, 5, 12, hour, minute))

    def test_scan_before_end_is_inside_window(self):
        self.assertFalse(session_views._scan_window_closed(self.session, now=self._at(9, 59)))

    def test_scan_within_tolerance_is_inside_window(self):
        tolerance = session_views.SCAN_CLOSE_TOLERANCE_MINUTES
        inside = self._at(10, 0) + timedelta(minutes=tolerance - 1)
        self.assertFalse(session_views._scan_window_closed(self.session, now=inside))

    def test_scan_past_tolerance_is_closed(self):
        tolerance = session_views.SCAN_CLOSE_TOLERANCE_MINUTES
        outside = self._at(10, 0) + timedelta(minutes=tolerance + 1)
        self.assertTrue(session_views._scan_window_closed(self.session, now=outside))

    def test_scan_hours_late_is_closed(self):
        self.assertTrue(session_views._scan_window_closed(self.session, now=self._at(15, 0)))


class ScanAfterClassEndTests(TestCase):
    def setUp(self):
        cache.clear()

        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )

        self.teacher_user = User.objects.create_user(username='win_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.student_user = User.objects.create_user(
            username='win_student', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-4000',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
            qr_secret='c' * 64,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1A',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            grace_minutes=10,
        )
        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.teacher_user)

    def _session_ending(self, ends_at, starts_at=time(9, 0)):
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=FIXED_NOW.date().weekday(),
            starts_at=starts_at,
            ends_at=ends_at,
            room='Room 1',
        )
        return ClassSession.objects.create(
            slot=slot,
            session_date=FIXED_NOW.date(),
            status=ClassSession.STATUS_OPEN,
            opened_at=FIXED_NOW - timedelta(minutes=60),
            opened_by=self.teacher_user,
            created_by=self.teacher_user,
        )

    def _scan(self, session):
        token = current_token(self.student_profile)
        with mock.patch(
            'apps.core.views.session_views.timezone.now', return_value=FIXED_NOW
        ), mock.patch(
            'apps.core.views.session_views.timezone.localdate',
            return_value=FIXED_NOW.date(),
        ):
            return self.client.post(reverse('attendance_scan_api'), {
                'session_id': session.pk,
                'qr_payload': build_payload(self.student_profile, token),
            })

    def test_scan_after_class_end_is_refused_and_logged(self):
        session = self._session_ending(ends_at=time(9, 30))

        response = self._scan(session)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['outcome'], StampAttempt.OUTCOME_WINDOW_CLOSED)
        self.assertIn('window has already closed', response.json()['error'])
        self.assertFalse(
            AttendanceRecord.objects.filter(session=session).exists(),
            'A refused scan must not create an attendance record.',
        )
        self.assertTrue(
            StampAttempt.objects.filter(
                session=session, outcome=StampAttempt.OUTCOME_WINDOW_CLOSED,
            ).exists()
        )

    def test_scan_inside_window_still_stamps_late(self):
        # Class 09:00-11:00, grace 10 min, scanned at 10:00 -> LATE, accepted.
        session = self._session_ending(ends_at=time(11, 0))

        response = self._scan(session)

        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(session=session)
        self.assertEqual(record.status, AttendanceRecord.STATUS_LATE)
        self.assertEqual(record.late_minutes, 50)

    def test_scan_within_close_tolerance_is_accepted(self):
        # Class ends 09:50; tolerance keeps 10:00 inside the window.
        session = self._session_ending(ends_at=time(9, 50))

        response = self._scan(session)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            AttendanceRecord.objects.get(session=session).status,
            AttendanceRecord.STATUS_LATE,
        )
