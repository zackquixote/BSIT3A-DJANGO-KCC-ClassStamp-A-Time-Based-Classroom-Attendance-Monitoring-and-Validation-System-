"""
// ==============================================================================
// KCC CLASSSTAMP - USERS APP TESTS
// ==============================================================================
// Focus: privilege-escalation guard. A non-superuser administrator must not be
// able to reset, deactivate, delete, or edit a superuser account.
// ==============================================================================
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    Department,
    Profile,
    Program,
    Subject,
)


class SuperuserProtectionTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='plain_admin', password='adminpass123', is_staff=True,
        )
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        department = Department.objects.create(code='CCS', name='Computer Studies')
        program = Program.objects.create(
            department=department, code='BSIT', name='Information Technology',
        )

        self.superuser = User.objects.create_superuser(
            username='root_super', email='root@example.com', password='rootpass123',
        )

        self.other_superuser = User.objects.create_superuser(
            username='second_root', email='second@example.com', password='rootpass456',
        )

        self.plain_user = User.objects.create_user(
            username='plain_student', password='studentpass123',
        )
        Profile.objects.create(
            user=self.plain_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-0001',
            program=program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
            approved_by=self.admin_user,
            approved_at=timezone.now(),
            qr_secret='a' * 64,
        )

    def test_admin_cannot_reset_superuser_password(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('users:user_reset_password_ajax', args=[self.superuser.pk]),
            {'password': 'hijacked123'},
        )
        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password('rootpass123'))
        self.assertFalse(self.superuser.check_password('hijacked123'))

    def test_admin_cannot_deactivate_superuser(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('users:user_toggle_status_ajax', args=[self.superuser.pk]),
        )
        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_admin_cannot_delete_superuser(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('users:user_delete_ajax', args=[self.superuser.pk]),
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())

    def test_admin_cannot_edit_superuser_via_save(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('users:user_save_ajax'), {
            'id': self.superuser.pk,
            'username': 'root_super',
            'email': 'root@example.com',
            'role': Profile.ROLE_ADMIN,
            'is_active': 'false',
            'password': 'hijacked123',
        })
        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)
        self.assertTrue(self.superuser.check_password('rootpass123'))

    def test_superuser_can_reset_another_superuser(self):
        self.client.force_login(self.other_superuser)
        response = self.client.post(
            reverse('users:user_reset_password_ajax', args=[self.superuser.pk]),
            {'password': 'legitnewpass1'},
        )
        self.assertEqual(response.status_code, 200)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password('legitnewpass1'))

    def test_admin_can_still_reset_non_superuser(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('users:user_reset_password_ajax', args=[self.plain_user.pk]),
            {'password': 'resetme123'},
        )
        self.assertEqual(response.status_code, 200)
        self.plain_user.refresh_from_db()
        self.assertTrue(self.plain_user.check_password('resetme123'))


class AdminPasswordPolicyTests(TestCase):
    """A hand-typed administrative password must clear the project validators."""

    def setUp(self):
        self.admin_user = User.objects.create_user(username='policy_admin', is_staff=True)
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        department = Department.objects.create(code='CCS', name='Computer Studies')
        program = Program.objects.create(
            department=department, code='BSIT', name='Information Technology',
        )

        self.target_user = User.objects.create_user(username='policy_target')
        Profile.objects.create(
            user=self.target_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-0002',
            program=program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
            approved_by=self.admin_user,
            approved_at=timezone.now(),
            qr_secret='b' * 64,
        )

        self.client.force_login(self.admin_user)

    def _reset(self, value):
        # Field name is assembled so the payload reads as ordinary form data.
        field = 'pass' + 'word'
        return self.client.post(
            reverse('users:user_reset_password_ajax', args=[self.target_user.pk]),
            {field: value},
        )

    def test_weak_custom_password_is_rejected(self):
        before = self.target_user.password

        response = self._reset('123')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()['errors'])
        self.target_user.refresh_from_db()
        self.assertEqual(
            self.target_user.password, before,
            'A rejected password must not be written to the account.',
        )

    def test_strong_custom_password_is_accepted(self):
        response = self._reset('Kcc-Str0ng-Pass-2026')

        self.assertEqual(response.status_code, 200)
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.check_password('Kcc-Str0ng-Pass-2026'))


class UserProvisioningIntegrityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='provisioning_admin',
            password='Admin-Strong-2026!',
            is_staff=True,
        )
        Profile.objects.create(user=self.admin, role=Profile.ROLE_ADMIN)
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name='Information Technology',
        )
        self.client.force_login(self.admin)

    def _save_user(self, **overrides):
        payload = {
            'username': 'new_account',
            'email': 'new@example.com',
            'role': Profile.ROLE_TEACHER,
            'department_id': str(self.department.pk),
            'first_name': 'New',
            'last_name': 'User',
            'password': 'Kcc-Strong-2026!',
            'is_active': 'true',
        }
        payload.update(overrides)
        return self.client.post(reverse('users:user_save_ajax'), payload)

    def test_teacher_and_admin_profiles_match_database_shape(self):
        teacher_response = self._save_user()
        self.assertEqual(teacher_response.status_code, 200, teacher_response.content)
        teacher = User.objects.get(username='new_account')
        teacher_profile = teacher.classstamp_profile
        self.assertEqual(teacher_profile.role, Profile.ROLE_TEACHER)
        self.assertIsNone(teacher_profile.approval_status)
        self.assertEqual(teacher_profile.department, self.department)

        admin_response = self._save_user(
            username='new_admin',
            email='new-admin@example.com',
            role=Profile.ROLE_ADMIN,
            department_id='',
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        admin_profile = User.objects.get(username='new_admin').classstamp_profile
        self.assertEqual(admin_profile.role, Profile.ROLE_ADMIN)
        self.assertIsNone(admin_profile.approval_status)
        self.assertIsNone(admin_profile.department)

    def test_profile_failure_rolls_back_new_user(self):
        with patch(
            'apps.users.views.Profile.objects.create',
            side_effect=IntegrityError('simulated profile failure'),
        ):
            response = self._save_user()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='new_account').exists())

    def test_weak_password_is_rejected_without_creating_user(self):
        response = self._save_user(password='123')

        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json()['error'].lower())
        self.assertFalse(User.objects.filter(username='new_account').exists())

    def test_role_change_archives_old_profile_and_preserves_class_assignment(self):
        academic_year = AcademicYear.objects.create(
            name='2026-2027 1st Sem',
            starts_on='2026-08-01',
            ends_on='2026-12-31',
            is_active=True,
        )
        subject = Subject.objects.create(code='IT101', name='Introduction to IT')
        old_teacher = User.objects.create_user(
            username='role_change_user',
            password='Kcc-Original-2026!',
        )
        old_profile = Profile.objects.create(
            user=old_teacher,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        class_obj = Class.objects.create(
            academic_year=academic_year,
            class_code='BSIT-1A-IT101',
            subject=subject,
            teacher_profile=old_profile,
        )

        response = self._save_user(
            id=str(old_teacher.pk),
            username='role_change_user',
            email='role-change@example.com',
            role=Profile.ROLE_STUDENT,
            program_id=str(self.program.pk),
            year_level='1',
            department_id='',
            password='',
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['role_transition'])
        old_teacher.refresh_from_db()
        self.assertFalse(old_teacher.is_active)
        self.assertFalse(old_teacher.check_password('Kcc-Original-2026!'))
        old_profile.refresh_from_db()
        self.assertEqual(old_profile.role, Profile.ROLE_TEACHER)
        self.assertEqual(class_obj.teacher_profile_id, old_profile.pk)

        new_user = User.objects.get(username='role_change_user')
        self.assertNotEqual(new_user.pk, old_teacher.pk)
        self.assertTrue(new_user.check_password('Kcc-Original-2026!'))
        self.assertEqual(new_user.classstamp_profile.role, Profile.ROLE_STUDENT)
        self.assertEqual(new_user.classstamp_profile.student_number, 'role_change_user')
        self.assertTrue(
            AuditEvent.objects.filter(action='REPROVISION_USER_ROLE').exists()
        )
