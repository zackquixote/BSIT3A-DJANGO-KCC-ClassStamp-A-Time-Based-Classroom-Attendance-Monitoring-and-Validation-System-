"""
# // ==============================================================================
# // KCC CLASSSTAMP - ADVANCE EXCUSE FILING TESTS
# // ==============================================================================
# // Students can now file an excuse before a meeting happens (a known appointment)
# // instead of waiting to be marked ABSENT. Covers the window, the enrolment
# // requirement, duplicate protection, and approval creating the EXCUSED record.
# ==============================================================================
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
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
    ExcuseSlip,
    Profile,
    Program,
    Subject,
)
from apps.core.views.excuse_views import EXCUSE_ADVANCE_DAYS, EXCUSE_BACKFILL_DAYS

User = get_user_model()


class AdvanceExcuseBase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='adv_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3A-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
        )
        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.student_user = User.objects.create_user(username='adv_student', first_name='Ana')
        self.student = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-3300',
            program=self.program,
            year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        Enrollment.objects.create(
            student_profile=self.student, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.student_user)

    def _session(self, days_from_today, status=ClassSession.STATUS_SCHEDULED):
        return ClassSession.objects.create(
            slot=self.slot,
            session_date=timezone.localdate() + timedelta(days=days_from_today),
            status=status,
            created_by=self.teacher_user,
        )

    def _file(self, session, reason='Medical appointment'):
        return self.client.post(reverse('student_excuse_slips'), {
            'session_id': session.pk,
            'reason': reason,
        })


class AdvanceFilingTests(AdvanceExcuseBase):
    def test_future_session_can_be_excused_in_advance(self):
        session = self._session(5)

        response = self._file(session)

        self.assertEqual(response.status_code, 302)
        slip = ExcuseSlip.objects.get(student_profile=self.student, session=session)
        self.assertEqual(slip.status, ExcuseSlip.STATUS_PENDING)

    def test_upcoming_sessions_are_listed_on_the_page(self):
        session = self._session(3)

        response = self.client.get(reverse('student_excuse_slips'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'File ahead')
        ids = [s.pk for s in response.context['upcoming_sessions']]
        self.assertIn(session.pk, ids)

    def test_filing_beyond_the_advance_window_is_refused(self):
        session = self._session(EXCUSE_ADVANCE_DAYS + 10)

        self._file(session)

        self.assertFalse(ExcuseSlip.objects.filter(session=session).exists())

    def test_filing_for_an_ancient_session_is_refused(self):
        session = self._session(-(EXCUSE_BACKFILL_DAYS + 10))

        self._file(session)

        self.assertFalse(ExcuseSlip.objects.filter(session=session).exists())

    def test_past_session_within_backfill_window_is_allowed(self):
        session = self._session(-3)

        self._file(session)

        self.assertTrue(ExcuseSlip.objects.filter(session=session).exists())

    def test_duplicate_slip_is_refused(self):
        session = self._session(4)
        self._file(session)

        self._file(session, reason='Second attempt')

        self.assertEqual(ExcuseSlip.objects.filter(session=session).count(), 1)

    def test_student_must_be_enrolled(self):
        other_subject = Subject.objects.create(code='IT312', name='Mobile Development')
        other_class = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3B-IT312', subject=other_subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
        )
        other_slot = ClassSlot.objects.create(
            class_obj=other_class, weekday=timezone.localdate().weekday(),
            starts_at=time(10, 0), ends_at=time(11, 0), room='Room 2',
        )
        foreign_session = ClassSession.objects.create(
            slot=other_slot, session_date=timezone.localdate() + timedelta(days=2),
            status=ClassSession.STATUS_SCHEDULED,
        )

        self._file(foreign_session)

        self.assertFalse(ExcuseSlip.objects.filter(session=foreign_session).exists())


class AdvanceApprovalTests(AdvanceExcuseBase):
    def test_approval_creates_the_excused_record_for_a_future_session(self):
        session = self._session(6)
        self._file(session)
        slip = ExcuseSlip.objects.get(session=session)
        self.assertFalse(AttendanceRecord.objects.filter(session=session).exists())

        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('excuse_slip_review_ajax', args=[slip.pk]),
            {'action': 'approve', 'note': 'Approved in advance'},
        )

        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(session=session, student_profile=self.student)
        self.assertEqual(record.status, AttendanceRecord.STATUS_EXCUSED)
        slip.refresh_from_db()
        self.assertEqual(slip.status, ExcuseSlip.STATUS_APPROVED)

    def test_absent_record_without_slip_still_files_normally(self):
        session = self._session(-1, status=ClassSession.STATUS_CLOSED)
        AttendanceRecord.objects.create(
            session=session, student_profile=self.student,
            status=AttendanceRecord.STATUS_ABSENT,
            method=AttendanceRecord.METHOD_SYSTEM,
        )

        response = self.client.get(reverse('student_excuse_slips'))

        ids = [r.session_id for r in response.context['fileable_records']]
        self.assertIn(session.pk, ids)
