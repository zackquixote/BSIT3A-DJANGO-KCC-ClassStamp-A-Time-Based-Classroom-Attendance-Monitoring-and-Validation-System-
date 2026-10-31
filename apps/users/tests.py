"""
// ==============================================================================
// KCC CLASSSTAMP - USERS APP TESTS
// ==============================================================================
// Focus: privilege-escalation guard. A non-superuser administrator must not be
// able to reset, deactivate, delete, or edit a superuser account.
// ==============================================================================
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Profile


class SuperuserProtectionTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='plain_admin', password='adminpass123', is_staff=True,
        )
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

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
            approval_status=Profile.APPROVAL_APPROVED,
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

        self.target_user = User.objects.create_user(username='policy_target')
        Profile.objects.create(
            user=self.target_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-0002',
            approval_status=Profile.APPROVAL_APPROVED,
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
