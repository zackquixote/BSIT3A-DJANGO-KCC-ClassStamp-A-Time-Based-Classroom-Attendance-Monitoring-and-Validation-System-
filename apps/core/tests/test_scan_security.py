"""
# // ==============================================================================
# // KCC CLASSSTAMP - QR SCAN ANTI-REPLAY & RATE-LIMIT TESTS
# // ==============================================================================
# // Covers the attendance scan API security controls:
# //   - a token is accepted once per class meeting
# //   - a captured token cannot be replayed into a second open session
# //   - excessive scan attempts are throttled with HTTP 429
# // ==============================================================================
"""

from datetime import date, time
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

User = get_user_model()


class ScanSecurityTests(TestCase):
    def setUp(self):
        cache.clear()

        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31), is_active=True,
        )

        self.teacher_user = User.objects.create_user(username='scan_teacher', password='Teacher!Pass123')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.student_user = User.objects.create_user(
            username='scan_student', password='Student!Pass123', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-1000',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
            qr_secret='a' * 64,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1A',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            grace_minutes=10,
        )

        today = timezone.localdate()
        self.slot_one = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.slot_two = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(10, 0), ends_at=time(11, 0), room='Room 2',
        )

        self.session_one = ClassSession.objects.create(
            slot=self.slot_one, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user, created_by=self.teacher_user,
        )
        self.session_two = ClassSession.objects.create(
            slot=self.slot_two, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user, created_by=self.teacher_user,
        )

        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

        self.client.force_login(self.teacher_user)

    def _scan(self, session, token=None, payload=None):
        if payload is None:
            payload = build_payload(self.student_profile, token or current_token(self.student_profile))
        return self.client.post(reverse('attendance_scan_api'), {
            'session_id': session.pk,
            'qr_payload': payload,
        })

    def test_valid_token_is_accepted_once(self):
        response = self._scan(self.session_one)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AttendanceRecord.objects.filter(
                session=self.session_one, student_profile=self.student_profile
            ).exists()
        )

    def test_token_cannot_be_replayed_into_another_session(self):
        token = current_token(self.student_profile)

        first = self._scan(self.session_one, token=token)
        self.assertEqual(first.status_code, 200)

        replay = self._scan(self.session_two, token=token)
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(replay.json()['outcome'], StampAttempt.OUTCOME_DUPLICATE)
        self.assertFalse(
            AttendanceRecord.objects.filter(
                session=self.session_two, student_profile=self.student_profile
            ).exists()
        )

    def test_duplicate_scan_in_same_session_is_rejected(self):
        token = current_token(self.student_profile)

        self.assertEqual(self._scan(self.session_one, token=token).status_code, 200)
        duplicate = self._scan(self.session_one, token=token)

        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()['outcome'], StampAttempt.OUTCOME_DUPLICATE)
        self.assertEqual(
            AttendanceRecord.objects.filter(
                session=self.session_one, student_profile=self.student_profile
            ).count(),
            1,
        )

    def test_invalid_token_is_rejected(self):
        with mock.patch('apps.core.views.session_views.verify_token', return_value=False):
            response = self._scan(self.session_one)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['outcome'], StampAttempt.OUTCOME_EXPIRED)
        self.assertFalse(AttendanceRecord.objects.filter(session=self.session_one).exists())

    def test_rate_limit_blocks_excess_scan_attempts(self):
        with mock.patch('apps.core.views.session_views.SCAN_RATE_LIMIT_PER_USER', 2), \
                mock.patch('apps.core.views.session_views.SCAN_RATE_LIMIT_PER_IP', 9999):
            for _ in range(2):
                response = self._scan(self.session_one, payload='not-a-valid-payload')
                self.assertEqual(response.status_code, 400)

            throttled = self._scan(self.session_one, payload='not-a-valid-payload')

        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(throttled.json()['outcome'], 'RATE_LIMITED')

    def test_replay_attempt_is_audited(self):
        token = current_token(self.student_profile)
        self._scan(self.session_one, token=token)
        self._scan(self.session_two, token=token)

        self.assertEqual(
            StampAttempt.objects.filter(
                session=self.session_two,
                student_profile=self.student_profile,
                outcome=StampAttempt.OUTCOME_DUPLICATE,
            ).count(),
            1,
        )
