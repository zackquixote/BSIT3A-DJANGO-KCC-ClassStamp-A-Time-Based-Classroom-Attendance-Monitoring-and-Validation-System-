"""
# // ==============================================================================
# // KCC CLASSSTAMP - FORM VALIDATION GUARDS
# // ==============================================================================
# // Covers the five gaps found in the November 2026 admin/teacher/student form
# // audit:
# //   1. /classes/ filters must ignore non-numeric ids instead of raising 500
# //   2. Department / Program / Subject code+name length ceilings (server side)
# //   3. AcademicEvent title / location ceilings
# //   4. Subject units upper bound
# //   5. Masterlist year level follows the program's duration, not a hard 1-4
# // ==============================================================================
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    Department,
    Profile,
    Program,
    Subject,
)

User = get_user_model()
PASSWORD = 'GuardPass!2026'


class _Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        today = datetime.date.today()
        cls.department = Department.objects.create(code='GRD', name='Guard Department')
        cls.program = Program.objects.create(
            department=cls.department, code='BSGRD', name='Guard Program', years_total=4,
        )
        cls.long_program = Program.objects.create(
            department=cls.department, code='BSLONG', name='Five Year Program', years_total=5,
        )
        cls.academic_year = AcademicYear.objects.create(
            name='2026-2027 Guard', starts_on=today - datetime.timedelta(days=30),
            ends_on=today + datetime.timedelta(days=300), is_active=True,
        )
        cls.admin = User.objects.create_user(username='guardadmin', password=PASSWORD)
        Profile.objects.create(user=cls.admin, role=Profile.ROLE_ADMIN)
        cls.student = User.objects.create_user(username='guardstudent', password=PASSWORD)
        cls.student_profile = Profile.objects.create(
            user=cls.student, role=Profile.ROLE_STUDENT, student_number='GRD-0001',
            program=cls.long_program, year_level=4, department=cls.department,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='g' * 64,
        )

    def _admin(self):
        client = Client()
        client.force_login(self.admin)
        return client

    def _ajax(self, client, url, data):
        return client.post(url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')


class ClassListFilterTests(_Fixture):
    """A tampered query string must never take the classes page down."""

    def test_non_numeric_filters_are_ignored(self):
        client = self._admin()
        for query in ('?ay=abc', '?subject=abc', '?teacher=abc',
                      '?ay=abc&subject=abc&teacher=abc&year_level=abc&department=abc'):
            with self.subTest(query=query):
                response = client.get(reverse('class_list') + query)
                self.assertEqual(response.status_code, 200)

    def test_numeric_academic_year_filter_still_works(self):
        client = self._admin()
        response = client.get(reverse('class_list') + f'?ay={self.academic_year.pk}')
        self.assertEqual(response.status_code, 200)


class CatalogueLengthTests(_Fixture):
    """VARCHAR ceilings are enforced server-side, not only by maxlength."""

    def test_department_code_over_limit_rejected(self):
        response = self._ajax(self._admin(), reverse('department_save'), {
            'code': 'D' * 21, 'name': 'Overlong Code Department',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('20 characters or fewer', response.json()['error'])

    def test_department_name_over_limit_rejected(self):
        response = self._ajax(self._admin(), reverse('department_save'), {
            'code': 'GRD2', 'name': 'N' * 151,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('150 characters or fewer', response.json()['error'])

    def test_department_at_limit_accepted(self):
        response = self._ajax(self._admin(), reverse('department_save'), {
            'code': 'D' * 20, 'name': 'Exactly Twenty',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

    def test_program_code_over_limit_rejected(self):
        response = self._ajax(self._admin(), reverse('program_save'), {
            'department_id': self.department.pk, 'code': 'P' * 21,
            'name': 'Overlong Program', 'years_total': 4,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('20 characters or fewer', response.json()['error'])

    def test_subject_code_over_limit_rejected(self):
        response = self._ajax(self._admin(), reverse('subject_save'), {
            'code': 'S' * 41, 'name': 'Overlong Subject', 'units': 3,
            'curriculum_program_id': self.program.pk, 'curriculum_year_level': 1,
            'curriculum_semester': '1', 'curriculum_is_major': '1',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('40 characters or fewer', response.json()['error'])

    def test_subject_name_over_limit_rejected(self):
        response = self._ajax(self._admin(), reverse('subject_save'), {
            'code': 'GRD101', 'name': 'N' * 151, 'units': 3,
            'curriculum_program_id': self.program.pk, 'curriculum_year_level': 1,
            'curriculum_semester': '1', 'curriculum_is_major': '1',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('150 characters or fewer', response.json()['error'])


class SubjectUnitsTests(_Fixture):
    """Units feed the wizard's '1 unit = 1 class hour' rule, so they need a roof."""

    def test_absurd_units_rejected(self):
        response = self._ajax(self._admin(), reverse('subject_save'), {
            'code': 'GRD900', 'name': 'Huge Units', 'units': 999,
            'curriculum_program_id': self.program.pk, 'curriculum_year_level': 1,
            'curriculum_semester': '1', 'curriculum_is_major': '1',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Units cannot exceed 12', response.json()['error'])

    def test_twelve_units_accepted(self):
        response = self._ajax(self._admin(), reverse('subject_save'), {
            'code': 'GRD112', 'name': 'Twelve Units', 'units': 12,
            'curriculum_program_id': self.program.pk, 'curriculum_year_level': 1,
            'curriculum_semester': '1', 'curriculum_is_major': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])


class CalendarLengthTests(_Fixture):
    def test_overlong_title_rejected(self):
        response = self._ajax(self._admin(), reverse('admin_calendar_event_save'), {
            'title': 'T' * 201, 'category': 'MEETING',
            'start_datetime': '2027-02-10T08:00', 'end_datetime': '2027-02-10T09:00',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('200 characters or fewer', response.json()['error'])

    def test_overlong_location_rejected(self):
        response = self._ajax(self._admin(), reverse('admin_calendar_event_save'), {
            'title': 'Guard Event', 'category': 'MEETING',
            'start_datetime': '2027-02-11T08:00', 'end_datetime': '2027-02-11T09:00',
            'location': 'L' * 151,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('150 characters or fewer', response.json()['error'])

    def test_title_at_limit_accepted(self):
        response = self._ajax(self._admin(), reverse('admin_calendar_event_save'), {
            'title': 'T' * 200, 'category': 'MEETING',
            'start_datetime': '2027-02-12T08:00', 'end_datetime': '2027-02-12T09:00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')


class MasterlistYearLevelTests(_Fixture):
    """A five-year program must accept Year 5; the ceiling stays at 8."""

    def test_year_five_allowed_for_five_year_program(self):
        response = self._ajax(self._admin(), reverse('student_profile_update_ajax'), {
            'student_id': self.student_profile.pk, 'student_number': 'GRD-0001',
            'first_name': 'Guard', 'last_name': 'Student',
            'department': self.department.pk, 'program': self.long_program.pk,
            'year_level': 5,
        })
        self.assertEqual(response.status_code, 200)
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.year_level, 5)

    def test_year_above_eight_rejected(self):
        response = self._ajax(self._admin(), reverse('student_profile_update_ajax'), {
            'student_id': self.student_profile.pk, 'student_number': 'GRD-0001',
            'first_name': 'Guard', 'last_name': 'Student',
            'department': self.department.pk, 'program': self.long_program.pk,
            'year_level': 9,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('1 and 8', response.json()['errors']['year_level'])

    def test_year_beyond_program_duration_rejected(self):
        response = self._ajax(self._admin(), reverse('student_profile_update_ajax'), {
            'student_id': self.student_profile.pk, 'student_number': 'GRD-0001',
            'first_name': 'Guard', 'last_name': 'Student',
            'department': self.department.pk, 'program': self.program.pk,
            'year_level': 5,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('cannot exceed 4', response.json()['errors']['year_level'])
