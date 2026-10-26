"""
# // ==============================================================================
# // KCC CLASSSTAMP - TEACHER SESSION HISTORY & CSV EXPORT TESTS
# // ==============================================================================
# // Verifies the teacher report views are teacher-scoped, filterable, paginated,
# // and export the correct CSV payloads.
# // ==============================================================================
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
    Profile,
    Program,
    Subject,
)

User = get_user_model()


class TeacherSessionReportTests(TestCase):
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

        self.teacher_user = User.objects.create_user(username='report_teacher', password='Teacher!Pass123')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.other_teacher_user = User.objects.create_user(username='other_teacher', password='Teacher!Pass123')
        self.other_teacher_profile = Profile.objects.create(
            user=self.other_teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.student_user = User.objects.create_user(
            username='report_student', password='Student!Pass123', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-2000',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

        self.class_a = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )
        self.class_b = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1B',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )
        self.class_x = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-9Z',
            subject=self.subject, teacher_profile=self.other_teacher_profile,
        )

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        self.slot_a1 = ClassSlot.objects.create(
            class_obj=self.class_a, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.slot_a2 = ClassSlot.objects.create(
            class_obj=self.class_a, weekday=today.weekday(),
            starts_at=time(10, 0), ends_at=time(11, 0), room='Room 2',
        )
        self.slot_b1 = ClassSlot.objects.create(
            class_obj=self.class_b, weekday=yesterday.weekday(),
            starts_at=time(13, 0), ends_at=time(14, 0), room='Room 3',
        )
        self.slot_x1 = ClassSlot.objects.create(
            class_obj=self.class_x, weekday=today.weekday(),
            starts_at=time(15, 0), ends_at=time(16, 0), room='Room 9',
        )

        now = timezone.now()
        self.session_a1 = ClassSession.objects.create(
            slot=self.slot_a1, session_date=today, status=ClassSession.STATUS_CLOSED,
            opened_at=now, closed_at=now, opened_by=self.teacher_user, created_by=self.teacher_user,
        )
        self.session_a2 = ClassSession.objects.create(
            slot=self.slot_a2, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=now, opened_by=self.teacher_user, created_by=self.teacher_user,
        )
        self.session_b1 = ClassSession.objects.create(
            slot=self.slot_b1, session_date=yesterday, status=ClassSession.STATUS_CLOSED,
            opened_at=now, closed_at=now, opened_by=self.teacher_user, created_by=self.teacher_user,
        )
        self.session_x1 = ClassSession.objects.create(
            slot=self.slot_x1, session_date=today, status=ClassSession.STATUS_CLOSED,
            opened_at=now, closed_at=now, opened_by=self.other_teacher_user,
            created_by=self.other_teacher_user,
        )

        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_a,
            status=Enrollment.STATUS_ACTIVE,
        )
        AttendanceRecord.objects.create(
            session=self.session_a1, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_PRESENT, method=AttendanceRecord.METHOD_QR,
            stamped_at=now,
        )
        AttendanceRecord.objects.create(
            session=self.session_b1, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_LATE, method=AttendanceRecord.METHOD_QR,
            stamped_at=now, late_minutes=5,
        )

        self.client.force_login(self.teacher_user)

    def _history_sessions(self, **params):
        response = self.client.get(reverse('teacher_session_history'), params)
        self.assertEqual(response.status_code, 200)
        return [s.pk for s in response.context['sessions']], response

    def test_history_lists_only_own_sessions(self):
        session_ids, _response = self._history_sessions()

        self.assertIn(self.session_a1.pk, session_ids)
        self.assertIn(self.session_a2.pk, session_ids)
        self.assertIn(self.session_b1.pk, session_ids)
        self.assertNotIn(self.session_x1.pk, session_ids)

    def test_history_filters_by_class(self):
        session_ids, _response = self._history_sessions(class_code='BSIT-1A')

        self.assertEqual(set(session_ids), {self.session_a1.pk, self.session_a2.pk})

    def test_history_filters_by_status(self):
        session_ids, _response = self._history_sessions(status='OPEN')

        self.assertEqual(session_ids, [self.session_a2.pk])

    def test_history_filters_by_date_range(self):
        session_ids, _response = self._history_sessions(
            date_from=timezone.localdate().isoformat()
        )

        self.assertIn(self.session_a1.pk, session_ids)
        self.assertNotIn(self.session_b1.pk, session_ids)

    def test_history_ignores_invalid_status_filter(self):
        session_ids, _response = self._history_sessions(status='NONSENSE')

        self.assertEqual(
            set(session_ids),
            {self.session_a1.pk, self.session_a2.pk, self.session_b1.pk},
        )

    def test_history_csv_export_contains_rows(self):
        response = self.client.get(reverse('teacher_session_history_export'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment;', response['Content-Disposition'])

        body = response.content.decode('utf-8')
        lines = [line for line in body.splitlines() if line.strip()]
        self.assertIn('Meeting Date', lines[0])
        self.assertEqual(len(lines), 4)
        self.assertIn('BSIT-1A', body)
        self.assertIn('BSIT-1B', body)
        self.assertNotIn('BSIT-9Z', body)

    def test_history_csv_export_respects_filters(self):
        response = self.client.get(
            reverse('teacher_session_history_export'), {'class_code': 'BSIT-1B'}
        )

        body = response.content.decode('utf-8')
        lines = [line for line in body.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn('BSIT-1B', body)
        self.assertNotIn('BSIT-1A', body)

    def test_single_session_csv_export_contains_student_roll(self):
        response = self.client.get(
            reverse('teacher_session_export', args=[self.session_a1.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))

        body = response.content.decode('utf-8')
        self.assertIn('Student Number', body)
        self.assertIn('2026-2000', body)
        self.assertIn('Cruz', body)
        self.assertIn('PRESENT', body)

    def test_single_session_export_blocks_other_teacher(self):
        self.client.force_login(self.other_teacher_user)

        response = self.client.get(
            reverse('teacher_session_export', args=[self.session_a1.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('teacher_dashboard'))

    def test_history_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse('teacher_session_history'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
