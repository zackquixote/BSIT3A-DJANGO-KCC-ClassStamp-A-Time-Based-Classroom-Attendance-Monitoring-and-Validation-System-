"""
# // ==============================================================================
# // KCC CLASSSTAMP - IN-PLACE STUDENT PROFILE EDITOR TESTS (A-03)
# // ==============================================================================
# // Covers:
# //   - Admin can edit student number, name, department, program, year level
# //   - Duplicate student number rejected; program/department mismatch rejected
# //   - Year level capped by program.years_total
# //   - TOTP QR secret reset rotates the seed and audits both actions
# //   - Non-admin rejected; directory page renders the editor modal
# // ==============================================================================
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Department,
    Profile,
    Program,
)

User = get_user_model()


class ProfileEditorTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.other_department = Department.objects.create(code='CBA', name='College of Business')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.other_program = Program.objects.create(
            department=self.other_department, code='BSA',
            name='BS Accountancy', years_total=4,
        )
        self.short_program = Program.objects.create(
            department=self.department, code='ACT',
            name='Associate in Computer Technology', years_total=2,
        )
        AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31), is_active=True,
        )

        self.admin_user = User.objects.create_user(username='dir_admin', password='Admin!Pass123')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.teacher_user = User.objects.create_user(username='dir_teacher', password='Teacher!Pass123')
        Profile.objects.create(user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department)

        self.student_user = User.objects.create_user(
            username='dir_student', password='Student!Pass123', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT, student_number='2026-5001',
            program=self.program, year_level=1,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='a' * 64,
        )

        other_student = User.objects.create_user(
            username='dir_student2', password='Student!Pass123', first_name='Ben', last_name='Reyes',
        )
        Profile.objects.create(
            user=other_student, role=Profile.ROLE_STUDENT, student_number='2026-5002',
            program=self.program, year_level=1,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='b' * 64,
        )

        self.client.force_login(self.admin_user)

    def _post(self, **overrides):
        data = {
            'student_id': self.student_profile.pk,
            'first_name': 'Maria',
            'last_name': 'Santos',
            'student_number': '2026-5100',
            'department': self.department.pk,
            'program': self.program.pk,
            'year_level': '2',
        }
        data.update(overrides)
        return self.client.post(reverse('student_profile_update_ajax'), data)

    def test_update_profile_success(self):
        res = self._post()
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['student_number'], '2026-5100')
        self.assertEqual(data['full_name'], 'Maria Santos')
        self.assertEqual(data['program_code'], 'BSIT')
        self.assertEqual(data['year_level'], 2)

        self.student_profile.refresh_from_db()
        self.student_user.refresh_from_db()
        self.assertEqual(self.student_profile.student_number, '2026-5100')
        self.assertEqual(self.student_profile.year_level, 2)
        self.assertEqual(self.student_user.first_name, 'Maria')
        self.assertEqual(self.student_user.last_name, 'Santos')
        self.assertTrue(AuditEvent.objects.filter(action='STUDENT_PROFILE_UPDATE').exists())

    def test_duplicate_student_number_rejected(self):
        res = self._post(student_number='2026-5002')
        self.assertEqual(res.status_code, 400)
        self.assertIn('already in use', res.json()['errors']['student_number'])

    def test_program_department_mismatch_rejected(self):
        res = self._post(department=self.department.pk, program=self.other_program.pk)
        self.assertEqual(res.status_code, 400)
        self.assertIn('does not belong', res.json()['errors']['program'])

    def test_year_level_capped_by_program(self):
        res = self._post(program=self.short_program.pk, year_level='3')
        self.assertEqual(res.status_code, 400)
        self.assertIn('cannot exceed', res.json()['errors']['year_level'])

    def test_missing_name_rejected(self):
        res = self._post(first_name='', last_name='')
        self.assertEqual(res.status_code, 400)
        self.assertIn('full_name', res.json()['errors'])

    def test_qr_reset_rotates_secret_and_audits(self):
        old_secret = self.student_profile.qr_secret
        res = self._post(reset_qr='1')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['qr_reset'])

        self.student_profile.refresh_from_db()
        self.assertNotEqual(self.student_profile.qr_secret, old_secret)
        self.assertEqual(len(self.student_profile.qr_secret), 64)
        self.assertTrue(AuditEvent.objects.filter(action='STUDENT_QR_RESET').exists())

    def test_non_admin_forbidden(self):
        self.client.force_login(self.teacher_user)
        res = self._post()
        # role_required decorator redirects unauthorized roles away (302)
        self.assertIn(res.status_code, (302, 403))
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.student_number, '2026-5001')

    def test_directory_renders_editor_modal(self):
        res = self.client.get(reverse('student_directory'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'studentEditModal')
        self.assertContains(res, 'js-edit-student')
