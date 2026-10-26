"""
# // ==============================================================================
# // KCC CLASSSTAMP - DASHBOARD DISPATCH TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Dashboard Module
# // Description: After login, the smart dashboard dispatcher at /dashboard/ must
# //   render the correct role-scoped template: admin, teacher, or student.
# //   Also validates superuser fallback and the profile-less user edge case.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AnomalyFlag, Department, Profile, Program

User = get_user_model()


class DashboardDispatchTests(TestCase):
    """After login, ``/dashboard/`` must render the dashboard matching the role."""

    def setUp(self):
        self.department = Department.objects.create(code='CITCS', name='College of IT')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )

    def _make(self, username, role, **profile_kwargs):
        """Helper: create a user + profile and return the user."""
        user = User.objects.create_user(username=username, password='Pass1234!x')
        Profile.objects.create(user=user, role=role, **profile_kwargs)
        return user

    def test_admin_lands_on_admin_dashboard(self):
        user = self._make('boss', Profile.ROLE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/admin/dashboard.html')

    def test_admin_dashboard_renders_with_open_anomaly_flag(self):
        # Regression: the bell dropdown links to the anomaly queue; a wrong URL
        # name there only surfaces once an OPEN flag exists.
        AnomalyFlag.objects.create(
            rule_code='TOKEN_REPLAY_ACROSS_SESSION',
            risk_score=0.85,
            reason='Test flag',
        )
        user = self._make('boss2', Profile.ROLE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Open Anomaly')

    def test_teacher_lands_on_teacher_dashboard(self):
        user = self._make('teach', Profile.ROLE_TEACHER, department=self.department)
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/teacher/dashboard.html')

    def test_student_lands_on_student_dashboard(self):
        user = self._make(
            'stud', Profile.ROLE_STUDENT,
            program=self.program, year_level=1, student_number='2023-7000',
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/student/dashboard.html')

    def test_superuser_without_profile_gets_admin_dashboard(self):
        # Superusers bypass the Profile lookup and land on the admin dashboard.
        user = User.objects.create_superuser(
            username='rooty', password='Pass1234!x', email='r@x.com',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/admin/dashboard.html')

    def test_plain_user_without_profile_gets_fallback_home(self):
        # A user with no Profile gets the generic home.html fallback.
        user = User.objects.create_user(username='nobody', password='Pass1234!x')
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
