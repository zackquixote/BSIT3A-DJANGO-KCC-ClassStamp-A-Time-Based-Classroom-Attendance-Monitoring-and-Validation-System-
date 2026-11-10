"""
# // ==============================================================================
# // KCC CLASSSTAMP - PREDICTIVE ANALYTICS TESTS (tasks 5.1 / 5.2 / 5.3 — Req 15)
# // ==============================================================================
# // Validates AnalyticsService.predict_final_attendance against the acceptance
# // cases (session-count boundaries, 0% / 100%, monotonic trends, missing
# // records, clamping), the batch predict_class_attendance loader (including
# // the no-N+1 guarantee), the once-per-version algorithm audit, and the
# // prediction UI on the teacher matrix and admin matrix JSON.
# // ==============================================================================
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
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
from apps.core.services.analytics_service import (
    PREDICTION_ALGORITHM_VERSION,
    AnalyticsService,
)

User = get_user_model()


def _make_profile(username, *, role, program=None, student_number=None):
    user = User.objects.create_user(
        username=username,
        first_name=username.title(), last_name='Test',
    )
    return Profile.objects.create(
        user=user,
        role=role,
        department=None if role != Profile.ROLE_STUDENT else program.department,
        program=program,
        year_level=3 if role == Profile.ROLE_STUDENT else None,
        student_number=student_number,
        approval_status=Profile.APPROVAL_APPROVED,
    )


class PredictionTestCase(TestCase):
    """Shared fixtures: one class, one slot, N closed past sessions."""

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        cls.program = Program.objects.create(
            department=cls.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        cls.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        cls.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )
        cls.teacher_profile = _make_profile('pred_teacher', role=Profile.ROLE_TEACHER)
        cls.class_obj = Class.objects.create(
            academic_year=cls.academic_year, class_code='BSIT-3A',
            subject=cls.subject, teacher_profile=cls.teacher_profile,
        )
        cls.slot = ClassSlot.objects.create(
            class_obj=cls.class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )

    def _create_sessions(self, count, *, status=ClassSession.STATUS_CLOSED, past=True):
        """Create `count` sessions on consecutive dates ending today (or tomorrow)."""
        base = timezone.localdate() - timedelta(days=count + 1) if past else timezone.localdate() + timedelta(days=1)
        sessions = []
        for i in range(count):
            session = ClassSession.objects.create(
                slot=self.slot,
                session_date=base + timedelta(days=i + 1),
                status=status,
                opened_at=timezone.now(), closed_at=timezone.now(),
                opened_by=self.teacher_profile.user,
                created_by=self.teacher_profile.user,
            )
            sessions.append(session)
        return sessions

    def _record(self, session, profile, status):
        return AttendanceRecord.objects.create(
            session=session,
            student_profile=profile,
            status=status,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
        )

    def _enrollment(self, profile):
        return Enrollment.objects.create(
            student_profile=profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )


class PredictFinalAttendanceTests(PredictionTestCase):
    """Task 5.1: validate the existing prediction service."""

    def setUp(self):
        self.student_profile = _make_profile(
            'pred_student', role=Profile.ROLE_STUDENT,
            program=self.program, student_number='2026-9001',
        )
        self.enrollment = self._enrollment(self.student_profile)

    def test_fewer_than_five_sessions_returns_none(self):
        sessions = self._create_sessions(4)
        for session in sessions:
            self._record(session, self.student_profile, AttendanceRecord.STATUS_PRESENT)
        self.assertIsNone(AnalyticsService.predict_final_attendance(self.enrollment))

    def test_open_and_future_sessions_do_not_count_toward_minimum(self):
        sessions = self._create_sessions(4)
        for session in sessions:
            self._record(session, self.student_profile, AttendanceRecord.STATUS_PRESENT)
        # A fifth session that is still OPEN must not make the data "sufficient".
        # Dated far enough back to stay unique against the four closed sessions.
        ClassSession.objects.create(
            slot=self.slot,
            session_date=timezone.localdate() - timedelta(days=40),
            status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), closed_at=timezone.now(),
            opened_by=self.teacher_profile.user,
            created_by=self.teacher_profile.user,
        )
        self.assertIsNone(AnalyticsService.predict_final_attendance(self.enrollment))
        # A fifth session dated in the future must not count either.
        self._create_sessions(1, past=False)
        self.assertIsNone(AnalyticsService.predict_final_attendance(self.enrollment))

    def test_exactly_five_sessions_returns_a_prediction(self):
        sessions = self._create_sessions(5)
        for session in sessions:
            self._record(session, self.student_profile, AttendanceRecord.STATUS_PRESENT)
        prediction = AnalyticsService.predict_final_attendance(self.enrollment)
        self.assertIsNotNone(prediction)
        self.assertIsInstance(prediction, float)
        self.assertGreaterEqual(prediction, 0.0)
        self.assertLessEqual(prediction, 100.0)

    def test_all_absent_predicts_zero(self):
        sessions = self._create_sessions(5)
        for session in sessions:
            self._record(session, self.student_profile, AttendanceRecord.STATUS_ABSENT)
        self.assertEqual(AnalyticsService.predict_final_attendance(self.enrollment), 0.0)

    def test_all_present_predicts_one_hundred(self):
        sessions = self._create_sessions(5)
        for session in sessions:
            self._record(session, self.student_profile, AttendanceRecord.STATUS_PRESENT)
        self.assertEqual(AnalyticsService.predict_final_attendance(self.enrollment), 100.0)

    def test_missing_records_treated_as_not_attended(self):
        # No AttendanceRecord rows at all: every session counts as missed.
        self._create_sessions(5)
        self.assertEqual(AnalyticsService.predict_final_attendance(self.enrollment), 0.0)

    def test_monotonic_improvement_clamps_at_one_hundred(self):
        sessions = self._create_sessions(5)
        statuses = [
            AttendanceRecord.STATUS_ABSENT,
            AttendanceRecord.STATUS_PRESENT,
            AttendanceRecord.STATUS_PRESENT,
            AttendanceRecord.STATUS_PRESENT,
            AttendanceRecord.STATUS_PRESENT,
        ]
        for session, status in zip(sessions, statuses):
            self._record(session, self.student_profile, status)
        # The steep upward trend extrapolates past 100 and must be clamped.
        prediction = AnalyticsService.predict_final_attendance(self.enrollment)
        self.assertEqual(prediction, 100.0)

    def test_monotonic_decline_clamps_at_zero(self):
        sessions = self._create_sessions(5)
        statuses = [
            AttendanceRecord.STATUS_PRESENT,
            AttendanceRecord.STATUS_ABSENT,
            AttendanceRecord.STATUS_ABSENT,
            AttendanceRecord.STATUS_ABSENT,
            AttendanceRecord.STATUS_ABSENT,
        ]
        for session, status in zip(sessions, statuses):
            self._record(session, self.student_profile, status)
        # The steep downward trend extrapolates below 0 and must be clamped.
        prediction = AnalyticsService.predict_final_attendance(self.enrollment)
        self.assertEqual(prediction, 0.0)


class PredictClassAttendanceTests(PredictionTestCase):
    """Task 5.2 service side: batch predictions without per-student queries."""

    def _add_student(self, number):
        profile = _make_profile(
            f'pred_{number}', role=Profile.ROLE_STUDENT,
            program=self.program, student_number=f'2026-{number}',
        )
        self._enrollment(profile)
        return profile

    def test_insufficient_sessions_flags_every_student(self):
        self._create_sessions(3)
        student = self._add_student('9101')
        results = AnalyticsService.predict_class_attendance(self.class_obj)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['student_profile_id'], student.pk)
        self.assertTrue(results[0]['insufficient_data'])
        self.assertIsNone(results[0]['prediction'])

    def test_ranking_reflects_attendance(self):
        sessions = self._create_sessions(5)
        strong = self._add_student('9101')
        weak = self._add_student('9102')
        for session in sessions:
            self._record(session, strong, AttendanceRecord.STATUS_PRESENT)
            self._record(session, weak, AttendanceRecord.STATUS_ABSENT)
        by_id = {r['student_profile_id']: r for r in AnalyticsService.predict_class_attendance(self.class_obj)}
        self.assertFalse(by_id[strong.pk]['insufficient_data'])
        self.assertEqual(by_id[strong.pk]['prediction'], 100.0)
        self.assertEqual(by_id[weak.pk]['prediction'], 0.0)

    def test_query_count_is_independent_of_roster_size(self):
        # No N+1: the batch loader must issue the same queries for a small
        # roster as for a large one.
        self._create_sessions(5)
        for i in range(2):
            self._add_student(f'92{i:02d}')
        with CaptureQueriesContext(connection) as small:
            AnalyticsService.predict_class_attendance(self.class_obj)

        for i in range(4):
            self._add_student(f'93{i:02d}')
        with CaptureQueriesContext(connection) as large:
            AnalyticsService.predict_class_attendance(self.class_obj)

        self.assertEqual(len(small), len(large))

    def test_empty_roster_returns_empty_list(self):
        self._create_sessions(5)
        self.assertEqual(AnalyticsService.predict_class_attendance(self.class_obj), [])


class AlgorithmVersionAuditTests(PredictionTestCase):
    """Task 5.3: one audit event per algorithm version, never per page view."""

    def test_version_recorded_once(self):
        AnalyticsService.ensure_algorithm_version_audited()
        AnalyticsService.ensure_algorithm_version_audited()
        events = AuditEvent.objects.filter(
            action='PREDICTION_ALGORITHM_VERSION',
            new_value=PREDICTION_ALGORITHM_VERSION,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().object_id, PREDICTION_ALGORITHM_VERSION)

    def test_version_constant_is_explicit(self):
        self.assertIsInstance(PREDICTION_ALGORITHM_VERSION, str)
        self.assertTrue(PREDICTION_ALGORITHM_VERSION)


class PredictionUITests(PredictionTestCase):
    """Task 5.2 UI: teacher matrix page and admin matrix JSON."""

    def setUp(self):
        self.client.force_login(self.teacher_profile.user)

    def test_matrix_page_shows_insufficient_data_state(self):
        student = _make_profile(
            'pred_ui_student', role=Profile.ROLE_STUDENT,
            program=self.program, student_number='2026-9501',
        )
        self._enrollment(student)
        self._create_sessions(3)

        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Predicted')
        self.assertContains(response, '— data')
        self.assertContains(response, 'advisory')
        self.assertContains(response, '85%')
        self.assertContains(response, PREDICTION_ALGORITHM_VERSION)
        self.assertContains(response, 'At-risk only (0)')

    def test_matrix_page_highlights_and_filters_at_risk(self):
        at_risk = _make_profile(
            'pred_ui_risk', role=Profile.ROLE_STUDENT,
            program=self.program, student_number='2026-9502',
        )
        healthy = _make_profile(
            'pred_ui_ok', role=Profile.ROLE_STUDENT,
            program=self.program, student_number='2026-9503',
        )
        self._enrollment(at_risk)
        self._enrollment(healthy)
        sessions = self._create_sessions(5)
        for session in sessions:
            self._record(session, at_risk, AttendanceRecord.STATUS_ABSENT)
            self._record(session, healthy, AttendanceRecord.STATUS_PRESENT)

        url = reverse('teacher_attendance_matrix', args=[self.class_obj.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # One at-risk student is counted and flagged.
        self.assertContains(response, 'At-risk only (1)')
        self.assertContains(response, '2026-9502')
        self.assertContains(response, 'badge--danger')

        # The at-risk-only filter keeps the at-risk row and drops the other.
        filtered = self.client.get(url, {'at_risk_only': '1'})
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, '2026-9502')
        self.assertNotContains(filtered, '2026-9503')
        self.assertContains(filtered, 'show all')

        # Prediction cells render numeric percentages.
        self.assertContains(filtered, '0.0%')

    def test_admin_matrix_json_includes_prediction_metadata(self):
        admin_profile = _make_profile('pred_ui_admin', role=Profile.ROLE_ADMIN)
        self.client.force_login(admin_profile.user)
        student = _make_profile(
            'pred_ui_json', role=Profile.ROLE_STUDENT,
            program=self.program, student_number='2026-9504',
        )
        self._enrollment(student)
        self._create_sessions(5)

        response = self.client.get(
            reverse('class_attendance_matrix', args=[self.class_obj.pk])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('predictions', payload)
        self.assertEqual(payload['prediction_algorithm_version'], PREDICTION_ALGORITHM_VERSION)
        self.assertEqual(payload['prediction_passing_threshold'], 80.0)
        self.assertIn('85%', payload['prediction_note'])
        prediction_rows = payload['predictions']
        self.assertEqual(len(prediction_rows), 1)
        self.assertEqual(prediction_rows[0]['student_profile_id'], student.pk)
        self.assertFalse(prediction_rows[0]['insufficient_data'])
