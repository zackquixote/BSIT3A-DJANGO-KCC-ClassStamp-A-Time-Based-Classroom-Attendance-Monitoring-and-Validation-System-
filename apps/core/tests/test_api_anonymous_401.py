"""
# // ==============================================================================
# // KCC CLASSSTAMP - ANONYMOUS /api/ CONTRACT TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Request Pipeline
# // Description: Anonymous XHR clients must receive 401 JSON, not an HTML login
# //   redirect. /api/csp-report/ stays public (the browser cannot attach a token).
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Profile

User = get_user_model()


class ApiAnonymousContractTests(TestCase):
    """Anonymous /api/* is 401 JSON; authenticated students still get 200."""

    def test_unread_api_is_401_json(self):
        response = self.client.get(reverse('notification_unread_api'))

        self.assertEqual(response.status_code, 401)
        self.assertIn('application/json', response.get('Content-Type', ''))
        self.assertIn(b'Authentication required', response.content)

    def test_student_qr_token_api_is_401_json(self):
        response = self.client.get(reverse('student_qr_token_api'))

        self.assertEqual(response.status_code, 401)
        self.assertIn('application/json', response.get('Content-Type', ''))

    def test_excuse_calendar_api_is_401_json(self):
        response = self.client.get(reverse('excuse_calendar'))

        self.assertEqual(response.status_code, 401)

    def test_csp_report_is_not_intercepted(self):
        # POST-only view: the 401 branch must not swallow it (405 = passed through).
        response = self.client.get(reverse('csp_report'))

        self.assertEqual(response.status_code, 405)

    def test_authenticated_student_still_reaches_the_unread_api(self):
        user = User.objects.create_user(username='api_student', password='Api!2026x')
        Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number='API-0001',
            approval_status=Profile.APPROVAL_APPROVED,
            qr_secret='f' * 64,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('notification_unread_api'))

        self.assertEqual(response.status_code, 200)
