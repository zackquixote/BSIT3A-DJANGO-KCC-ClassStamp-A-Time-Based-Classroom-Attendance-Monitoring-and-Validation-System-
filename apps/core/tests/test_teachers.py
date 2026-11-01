"""
# // ==============================================================================
# // KCC CLASSSTAMP - FACULTY ROSTER RENDERING TESTS
# // ==============================================================================
# // Covers the /teachers/ list view: filter combinations and the current page
# // contract (no bulk-selection column any more).
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Department, Profile

User = get_user_model()


class TeacherRosterTests(TestCase):
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

    def test_roster_renders_with_year_filter(self):
        self.client.force_login(self.admin_user)
        joined_year = self.teacher_user.date_joined.year

        response = self.client.get(reverse('teacher_list'), {'year_joined': str(joined_year)})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'teacher-checkbox')

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
