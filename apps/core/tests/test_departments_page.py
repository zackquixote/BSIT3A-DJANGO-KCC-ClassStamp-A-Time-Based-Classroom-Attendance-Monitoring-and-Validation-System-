"""
# // ==============================================================================
# // KCC CLASSSTAMP - DEPARTMENT DIRECTORY TESTS
# // ==============================================================================
# // Two fixes on /departments/:
# //   - the Faculty column counted every profile, students included
# //   - retiring a department with an open attendance session is refused
# ==============================================================================
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Profile,
    Program,
    Subject,
)

User = get_user_model()


class DepartmentBase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='dept_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.other_department = Department.objects.create(code='CBA', name='College of Business')
        self.client.force_login(self.admin_user)

    def _teacher(self, username, department=None):
        user = User.objects.create_user(username=username)
        return Profile.objects.create(
            user=user, role=Profile.ROLE_TEACHER, department=department or self.department,
        )

    def _student(self, number, department=None):
        user = User.objects.create_user(username=f'user_{number}')
        self.program = getattr(self, 'program', None) or Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=number,
            program=self.program,
            department=department,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )


class FacultyCountTests(DepartmentBase):
    def test_students_are_not_counted_as_faculty(self):
        self._teacher('dept_teacher')
        self._student('2026-8001', department=self.department)

        response = self.client.get(reverse('department_list'))

        row = next(d for d in response.context['departments'] if d.pk == self.department.pk)
        self.assertEqual(row.faculty_count, 1)

    def test_two_teachers_count_as_two(self):
        self._teacher('dept_teacher_a')
        self._teacher('dept_teacher_b')

        response = self.client.get(reverse('department_list'))

        row = next(d for d in response.context['departments'] if d.pk == self.department.pk)
        self.assertEqual(row.faculty_count, 2)

    def test_teacher_in_another_department_is_not_counted(self):
        self._teacher('dept_teacher_c', department=self.other_department)

        response = self.client.get(reverse('department_list'))

        row = next(d for d in response.context['departments'] if d.pk == self.department.pk)
        self.assertEqual(row.faculty_count, 0)


class DepartmentArchiveGuardTests(DepartmentBase):
    def setUp(self):
        super().setUp()
        self.teacher = self._teacher('guard_teacher')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=1,
        )
        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )

    def _session(self, status=ClassSession.STATUS_OPEN):
        return ClassSession.objects.create(
            slot=self.slot, session_date=timezone.localdate(), status=status,
            opened_by=self.teacher.user, created_by=self.teacher.user,
        )

    def _retire(self, ajax=True):
        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return self.client.post(
            reverse('department_delete', args=[self.department.pk]), **headers
        )

    def test_open_session_blocks_archiving(self):
        self._session()

        response = self._retire()

        self.assertEqual(response.status_code, 400)
        self.assertIn('open attendance session', response.json()['error'])
        self.department.refresh_from_db()
        self.assertTrue(self.department.is_active)
        self.assertFalse(AuditEvent.objects.filter(action='DEACTIVATE_DEPARTMENT').exists())

    def test_closed_session_allows_archiving(self):
        self._session(status=ClassSession.STATUS_CLOSED)

        response = self._retire()

        self.assertEqual(response.status_code, 200)
        self.department.refresh_from_db()
        self.assertFalse(self.department.is_active)
        self.assertEqual(response.json()['type'], 'deactivated')

    def test_archiving_reports_teacher_count_not_profile_count(self):
        self._student('2026-8100', department=self.department)

        response = self._retire()

        self.assertEqual(response.status_code, 200)
        self.assertIn('1 faculty', response.json()['message'])

    def test_empty_department_is_hard_deleted(self):
        response = self._retire()

        # The base department still has a program attached in this fixture, so use
        # the untouched one to prove the hard-delete path.
        self.assertEqual(response.status_code, 200)
        empty = Department.objects.create(code='EMPTY', name='Empty Unit')

        self.client.post(reverse('department_delete', args=[empty.pk]))

        self.assertFalse(Department.objects.filter(pk=empty.pk).exists())

    def test_non_ajax_refusal_redirects_with_message(self):
        self._session()

        response = self._retire(ajax=False)

        self.assertEqual(response.status_code, 302)
        self.department.refresh_from_db()
        self.assertTrue(self.department.is_active)
