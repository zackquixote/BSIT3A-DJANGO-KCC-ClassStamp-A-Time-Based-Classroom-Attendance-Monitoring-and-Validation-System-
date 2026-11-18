"""
Tests for the teacher/admin attendance report ranges: weekly, custom, and real
Prelim/Midterm/Finals windows backed by GradingPeriod.
"""

import datetime
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    GradingPeriod,
    Profile,
    Program,
    Subject,
)
from apps.core.services.attendance_report_service import resolve_report_range

User = get_user_model()


class AttendanceReportFixture(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027 1st Sem',
            starts_on=datetime.date(2026, 8, 1),
            ends_on=datetime.date(2027, 5, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='report_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        self.other_teacher_user = User.objects.create_user(username='report_other')
        self.other_teacher = Profile.objects.create(
            user=self.other_teacher_user, role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        self.admin_user = User.objects.create_user(username='report_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.student_user = User.objects.create_user(
            username='report_student', first_name='Ana', last_name='Cruz',
        )
        self.student = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-3000', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3A-IT311',
            section_code='BSIT-3A', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
            is_active=True,
        )
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=0,
            starts_at=datetime.time(8, 0), ends_at=datetime.time(9, 0),
            room='LAB-1',
        )
        Enrollment.objects.create(
            student_profile=self.student, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

        self.sessions = {}
        for label, session_date in {
            'aug_10': datetime.date(2026, 8, 10),
            'aug_24': datetime.date(2026, 8, 24),
            'sep_14': datetime.date(2026, 9, 14),
            'oct_05': datetime.date(2026, 10, 5),
            'nov_02': datetime.date(2026, 11, 2),
            'nov_09': datetime.date(2026, 11, 9),
        }.items():
            session = ClassSession.objects.create(
                slot=self.slot, session_date=session_date,
                status=ClassSession.STATUS_CLOSED,
            )
            AttendanceRecord.objects.create(
                session=session, student_profile=self.student,
                status=AttendanceRecord.STATUS_PRESENT,
                method=AttendanceRecord.METHOD_QR,
                stamped_at=timezone.now(),
            )
            self.sessions[label] = session

        for code, start, end in (
            (GradingPeriod.CODE_PRELIM, datetime.date(2026, 8, 1), datetime.date(2026, 8, 31)),
            (GradingPeriod.CODE_MIDTERM, datetime.date(2026, 9, 1), datetime.date(2026, 10, 15)),
            (GradingPeriod.CODE_FINALS, datetime.date(2026, 10, 16), datetime.date(2026, 12, 15)),
        ):
            GradingPeriod.objects.create(
                academic_year=self.year, code=code, start_date=start, end_date=end,
            )

        self.client.force_login(self.teacher_user)


class RangeResolverTests(AttendanceReportFixture):
    def test_week_range_is_monday_to_sunday(self):
        result = resolve_report_range(
            self.class_obj, range_key='week', today=datetime.date(2026, 11, 18),
        )
        self.assertEqual(result['start'], datetime.date(2026, 11, 16))
        self.assertEqual(result['end'], datetime.date(2026, 11, 22))
        self.assertIn('This Week', result['label'])

    def test_period_range_uses_grading_period_dates(self):
        result = resolve_report_range(self.class_obj, period='midterm')
        self.assertEqual(result['start'], datetime.date(2026, 9, 1))
        self.assertEqual(result['end'], datetime.date(2026, 10, 15))
        self.assertEqual(result['label'], 'Midterm')

    def test_missing_grading_period_returns_a_readable_error(self):
        GradingPeriod.objects.filter(
            academic_year=self.year, code=GradingPeriod.CODE_PRELIM,
        ).delete()
        result = resolve_report_range(self.class_obj, period='prelim')
        self.assertTrue(result['error'])
        self.assertIn('not configured', result['error'])

    def test_custom_range_requires_both_dates(self):
        result = resolve_report_range(self.class_obj, range_key='custom', start='2026-11-01')
        self.assertTrue(result['error'])

        result = resolve_report_range(
            self.class_obj, range_key='custom',
            start='2026-11-01', end='2026-11-10',
        )
        self.assertEqual(result['start'], datetime.date(2026, 11, 1))
        self.assertEqual(result['end'], datetime.date(2026, 11, 10))
        self.assertFalse(result['error'])


class MatrixRangeTests(AttendanceReportFixture):
    def test_matrix_period_filters_sessions_to_the_window(self):
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk]),
            {'period': 'prelim'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_sessions'], 2)
        self.assertEqual(response.context['report_range']['key'], 'prelim')
        self.assertContains(response, 'Prelim')

    def test_matrix_csv_is_scoped_to_the_period(self):
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk]),
            {'period': 'midterm', 'format': 'csv'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('_midterm_', response['Content-Disposition'])
        body = response.content.decode('utf-8')
        self.assertIn('Sep 14', body)
        self.assertIn('Oct 05', body)
        self.assertNotIn('Aug 10', body)

    def test_matrix_week_export_contains_only_that_week(self):
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk]),
            {'range': 'week', 'format': 'csv'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('_week_', response['Content-Disposition'])

    def test_excel_period_export_uses_period_dates_and_label(self):
        response = self.client.get(
            reverse('teacher_class_term_export', args=[self.class_obj.pk]),
            {'period': 'prelim'},
        )
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        worksheet = workbook.active
        self.assertEqual(worksheet.title, 'Prelim Attendance')
        headers = [cell.value for cell in worksheet[1]]
        week_columns = [value for value in headers if value and str(value).startswith('Week ')]
        self.assertEqual(len(week_columns), 2)
        self.assertIn('prelim_attendance_BSIT-3A-IT311.xlsx', response['Content-Disposition'])

    def test_other_teacher_cannot_export_report(self):
        self.client.force_login(self.other_teacher_user)
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('teacher_dashboard'))

    def test_admin_can_open_a_class_report(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk]),
        )
        self.assertEqual(response.status_code, 200, response.content[:800])

    def test_admin_can_export_a_class_report(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse('teacher_class_term_export', args=[self.class_obj.pk]),
            {'period': 'prelim'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])
        self.assertIn('prelim_attendance_', response['Content-Disposition'])


class GradingPeriodAdminTests(AttendanceReportFixture):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def test_admin_can_save_three_periods(self):
        response = self.client.post(
            reverse('grading_periods', args=[self.year.pk]),
            {
                'prelim_start': '2026-08-01', 'prelim_end': '2026-08-31',
                'midterm_start': '2026-09-01', 'midterm_end': '2026-10-15',
                'finals_start': '2026-10-16', 'finals_end': '2026-12-15',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            GradingPeriod.objects.filter(academic_year=self.year).count(), 3,
        )

    def test_overlapping_periods_are_rejected(self):
        response = self.client.post(
            reverse('grading_periods', args=[self.year.pk]),
            {
                'prelim_start': '2026-08-01', 'prelim_end': '2026-09-10',
                'midterm_start': '2026-09-01', 'midterm_end': '2026-10-15',
                'finals_start': '2026-10-16', 'finals_end': '2026-12-15',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'overlaps')

    def test_teacher_cannot_open_grading_period_admin(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('grading_periods', args=[self.year.pk]))
        self.assertIn(response.status_code, (302, 403))

    def test_grading_period_page_lists_inputs(self):
        response = self.client.get(reverse('grading_periods', args=[self.year.pk]))
        self.assertEqual(response.status_code, 200)
        for field in ('prelim_start', 'midterm_start', 'finals_start'):
            self.assertContains(response, f'name="{field}"')
