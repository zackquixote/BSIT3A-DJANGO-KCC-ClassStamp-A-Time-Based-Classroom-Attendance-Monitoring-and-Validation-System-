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
