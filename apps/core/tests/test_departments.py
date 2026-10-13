"""
# // ==============================================================================
# // KCC CLASSSTAMP - DEPARTMENT & PROGRAM CRUD TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Academic Organisation Module
# // Description: Tests for admin-only CRUD operations on Departments and Programs.
# //   Validates RBAC enforcement, create/edit roundtrips, and the soft-delete
# //   protection that deactivates (rather than hard-deletes) records with
# //   existing child associations.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Department, Profile, Program

User = get_user_model()


class DepartmentProgramCrudTests(TestCase):
    """CRUD tests for the Academic Organisation management pages."""

    def setUp(self):
        self.admin_user = User.objects.create_user(username='admin_boss', password='Boss!Password1')
        self.admin_profile = Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.student_user = User.objects.create_user(username='student_kid', password='Kid!Password1')
        self.student_profile = Profile.objects.create(
            user=self.student_kid if hasattr(self, 'student_kid') else self.student_user,
            role=Profile.ROLE_STUDENT,
        )

        self.dept = Department.objects.create(code='CITCS', name='College of Information Tech')
        self.prog = Program.objects.create(department=self.dept, code='BSIT', name='BS in Info Tech', years_total=4)

    def test_admin_can_view_department_and_program_lists(self):
        self.client.force_login(self.admin_user)
        r_dept = self.client.get(reverse('department_list'))
        self.assertEqual(r_dept.status_code, 200)
        self.assertTemplateUsed(r_dept, 'core/admin/departments.html')

        r_prog = self.client.get(reverse('program_list'))
        self.assertEqual(r_prog.status_code, 200)
        self.assertTemplateUsed(r_prog, 'core/admin/programs.html')

    def test_student_cannot_access_department_list(self):
        self.client.force_login(self.student_user)
        r = self.client.get(reverse('department_list'))
        self.assertEqual(r.status_code, 302)

    def test_admin_can_create_and_edit_department(self):
        self.client.force_login(self.admin_user)

        # Create a new department
        res = self.client.post(reverse('department_save'), {
            'code': 'CAS',
            'name': 'College of Arts and Sciences',
            'is_active': 'true',
        })
        self.assertEqual(res.status_code, 302)
        cas = Department.objects.get(code='CAS')
        self.assertEqual(cas.name, 'College of Arts and Sciences')

        # Edit the same department
        res_edit = self.client.post(reverse('department_save'), {
            'id': cas.id,
            'code': 'CAS',
            'name': 'College of Arts, Letters and Sciences',
            'is_active': 'true',
        })
        self.assertEqual(res_edit.status_code, 302)
        cas.refresh_from_db()
        self.assertEqual(cas.name, 'College of Arts, Letters and Sciences')

    def test_admin_can_create_and_edit_program(self):
        self.client.force_login(self.admin_user)

        # Create a new program
        res = self.client.post(reverse('program_save'), {
            'department_id': self.dept.id,
            'code': 'BSCS',
            'name': 'Bachelor of Science in Computer Science',
            'years_total': 4,
            'is_active': 'true',
        })
        self.assertEqual(res.status_code, 302)
        bscs = Program.objects.get(code='BSCS')
        self.assertEqual(bscs.department, self.dept)
        self.assertEqual(bscs.years_total, 4)

        # Edit the same program
        res_edit = self.client.post(reverse('program_save'), {
            'id': bscs.id,
            'department_id': self.dept.id,
            'code': 'BSCS',
            'name': 'BS in Computer Science (Enhanced)',
            'years_total': 4,
            'is_active': 'true',
        })
        self.assertEqual(res_edit.status_code, 302)
        bscs.refresh_from_db()
        self.assertEqual(bscs.name, 'BS in Computer Science (Enhanced)')

    def test_protected_department_deactivates_when_children_exist(self):
        # self.dept has self.prog attached; delete should soft-deactivate, not hard-delete.
        self.client.force_login(self.admin_user)
        res = self.client.post(reverse('department_delete', args=[self.dept.id]))
        self.assertEqual(res.status_code, 302)
        self.dept.refresh_from_db()
        self.assertFalse(self.dept.is_active)
        self.assertTrue(Department.objects.filter(pk=self.dept.id).exists())
