"""
# // ==============================================================================
# // KCC CLASSSTAMP - SESSION INTEGRITY & SCAN CONCURRENCY TESTS
# // ==============================================================================
# // Covers the attendance-window integrity controls added to the session engine:
# //   - a supplied slot must belong to the class AND fall on today's weekday
# //   - an inactive slot cannot launch a session
# //   - a matching slot still opens normally (positive control)
# //   - two simultaneous inserts resolve to an idempotent DUPLICATE answer
# //     instead of a 500 from the unique (session, student) constraint
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


class SessionWindowIntegrityTests(TestCase):
    """The schedule slot that anchors a session must match the session date."""

    def setUp(self):
        cache.clear()

        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )

        self.teacher_user = User.objects.create_user(username='window_teacher')
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

        self.client.force_login(self.teacher_user)

    def _open(self, slot_id=None, **extra):
        payload = {'class_id': self.class_obj.pk}
        if slot_id is not None:
            payload['slot_id'] = slot_id
        payload.update(extra)
        return self.client.post(reverse('teacher_session_open'), payload, follow=True)

    def test_slot_for_another_weekday_is_rejected(self):
        today = timezone.localdate()
        other_weekday = (today.weekday() + 2) % 7
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=other_weekday,
            starts_at=time(8, 0),
            ends_at=time(9, 0),
            room='Room 1',
        )

        response = self._open(slot.pk)

        self.assertFalse(
            ClassSession.objects.filter(slot=slot, session_date=today).exists(),
            'A slot scheduled for another weekday must not open a session today.',
        )
        messages_list = [str(m) for m in response.context['messages']]
        self.assertTrue(
            any('does not meet today' in m for m in messages_list),
            f'Expected a weekday-mismatch advisory, got: {messages_list}',
        )

    def test_inactive_slot_is_rejected(self):
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=today.weekday(),
            starts_at=time(8, 0),
            ends_at=time(9, 0),
            room='Room 1',
            is_active=False,
        )

        response = self._open(slot.pk)

        self.assertFalse(
            ClassSession.objects.filter(slot=slot, session_date=today).exists(),
            'An inactive slot must not launch an attendance session.',
        )
        messages_list = [str(m) for m in response.context['messages']]
        self.assertTrue(any('inactive' in m for m in messages_list))

    def test_matching_slot_still_opens(self):
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=today.weekday(),
            starts_at=time(8, 0),
            ends_at=time(9, 0),
            room='Room 1',
        )

        self._open(slot.pk)

        session = ClassSession.objects.filter(slot=slot, session_date=today).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, ClassSession.STATUS_OPEN)


class ScanInsertConcurrencyTests(TestCase):
    """A lost insert race must answer DUPLICATE, never a 500."""

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

        self.teacher_user = User.objects.create_user(username='race_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.student_user = User.objects.create_user(
            username='race_student', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-2000',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
            qr_secret='b' * 64,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1A',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            grace_minutes=10,
        )

        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.session = ClassSession.objects.create(
            slot=self.slot, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user,
            created_by=self.teacher_user,
        )

        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

        self.client.force_login(self.teacher_user)

    def test_lost_insert_race_returns_duplicate_not_server_error(self):
        # Stand-in for the record a competing request committed first.
        winner = AttendanceRecord.objects.create(
            session=self.session,
            student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_PRESENT,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
            marked_by=self.teacher_user,
        )

        # Simulate the race: the duplicate pre-check misses, and get_or_create
        # reports that the row already exists (created=False).
        fake_manager = mock.MagicMock()
        fake_manager.filter.return_value.first.return_value = None
        fake_manager.get_or_create.return_value = (winner, False)
        fake_model = mock.MagicMock()
        fake_model.METHOD_QR = AttendanceRecord.METHOD_QR
        fake_model.objects = fake_manager

        token = current_token(self.student_profile)
        with mock.patch('apps.core.views.session_views.AttendanceRecord', fake_model):
            response = self.client.post(reverse('attendance_scan_api'), {
                'session_id': self.session.pk,
                'qr_payload': build_payload(self.student_profile, token),
            })

        self.assertEqual(
            response.status_code, 400,
            'A lost insert race must not surface as an unhandled server error.',
        )
        self.assertEqual(response.json()['outcome'], StampAttempt.OUTCOME_DUPLICATE)
        self.assertIn('ALREADY stamped', response.json()['error'])
