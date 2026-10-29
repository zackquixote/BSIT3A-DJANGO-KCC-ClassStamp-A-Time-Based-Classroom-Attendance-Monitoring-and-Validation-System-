"""
# // ==============================================================================
# // KCC CLASSSTAMP - BULK FACULTY OPERATION TESTS
# // ==============================================================================
# // Covers the admin bulk action endpoint: explicit (non-toggling) activation,
# // deactivation, and password reset with returned temporary credentials.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Department, Profile

User = get_user_model()


class BulkTeacherOperationTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='bulk_admin', password='Admin!Pass123', is_staff=True,
        )
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')

        self.teacher_user = User.objects.create_user(
            username='faculty_one', password='Teacher!Pass123',
            email='faculty.one@example.com', is_active=True,
        )
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )

        self.bulk_url = reverse('bulk_teacher_operation')

    def _post(self, action, ids, user=None):
        self.client.force_login(user or self.admin_user)
        return self.client.post(self.bulk_url, {
            'action': action,
            'teacher_ids[]': [str(i) for i in ids],
        })

    def test_activate_is_explicit_not_a_toggle(self):
        self.teacher_user.is_active = True
        self.teacher_user.save(update_fields=['is_active'])

        response = self._post('activate', [self.teacher_profile.pk])

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.teacher_user.refresh_from_db()
        self.assertTrue(self.teacher_user.is_active)

    def test_deactivate_sets_inactive(self):
        response = self._post('deactivate', [self.teacher_profile.pk])

        self.assertEqual(response.status_code, 200)
        self.teacher_user.refresh_from_db()
        self.assertFalse(self.teacher_user.is_active)

    def test_reset_password_returns_credentials(self):
        response = self._post('reset-pw', [self.teacher_profile.pk])

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['credentials']), 1)
        credential = data['credentials'][0]
        self.assertEqual(credential['username'], self.teacher_user.username)

        self.teacher_user.refresh_from_db()
        self.assertTrue(self.teacher_user.check_password(credential['temporary_password']))

    def test_rejects_unsupported_action(self):
        response = self._post('delete-everything', [self.teacher_profile.pk])

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_non_admin_is_denied(self):
        response = self._post('activate', [self.teacher_profile.pk], user=self.teacher_user)

        self.assertEqual(response.status_code, 302)
        self.teacher_user.refresh_from_db()
        self.assertTrue(self.teacher_user.is_active)


class TeacherListPageTests(TestCase):
    """Regression tests for the faculty roster page rendering and filters."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='roster_admin', password='Admin!Pass123', is_staff=True,
        )
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.department = Department.objects.create(code='CEAS', name='College of Engineering')
        self.teacher_user = User.objects.create_user(
            username='faculty_roster', password='Teacher!Pass123',
            email='faculty.roster@example.com',
        )
        Profile.objects.create(
            user=self.teacher_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )

    def test_roster_renders_with_year_filter(self):
        self.client.force_login(self.admin_user)
        joined_year = self.teacher_user.date_joined.year

        response = self.client.get(reverse('teacher_list'), {'year_joined': str(joined_year)})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'teacher-checkbox')
        self.assertContains(response, 'data-bulk-url')

    def test_roster_renders_with_combined_filters(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('teacher_list'), {
            'status': 'active',
            'department': str(self.department.pk),
            'year_joined': str(self.teacher_user.date_joined.year),
        })

        self.assertEqual(response.status_code, 200)

    def test_roster_handles_invalid_year_filter(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('teacher_list'), {'year_joined': 'not-a-year'})

        self.assertEqual(response.status_code, 200)
