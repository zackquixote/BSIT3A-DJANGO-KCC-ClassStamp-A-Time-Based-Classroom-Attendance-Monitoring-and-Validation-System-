"""
# // ==============================================================================
# // KCC CLASSSTAMP - PASSWORD RESET LINK HOST TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Account Recovery
# // Description: A reset email must never follow the request Host header.
# //   A forged Host plus an open ALLOWED_HOSTS is account takeover
# //   (docs/10_PENTEST_2026-11-15.md, Finding 2).
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class ResetLinkHostTests(TestCase):
    """The emailed link uses SITE_URL, not the attacker's Host."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='host_victim',
            password='Host!2026x',
            email='host_victim@example.com',
            first_name='Vic',
            last_name='Tim',
        )

    def _request(self, **extra):
        return self.client.post(
            reverse('password_reset_request'),
            {'identifier': 'host_victim'},
            **extra,
        )

    def _last_link(self):
        self.assertTrue(mail.outbox, 'expected a reset email')
        body = mail.outbox[-1].body
        links = [ln.strip() for ln in body.splitlines() if '/password-reset/' in ln]
        self.assertTrue(links, f'no reset link in:\n{body}')
        return links[-1]

    def test_forged_host_is_ignored(self):
        response = self._request(HTTP_HOST='evil.example')

        self.assertEqual(response.status_code, 200)
        link = self._last_link()
        self.assertNotIn('evil.example', link)
        self.assertIn('/password-reset/', link)

    def test_production_rejects_a_forged_host(self):
        # // With a closed ALLOWED_HOSTS, DisallowedHost is a 400 before the view:
        # // the poisoned Host never reaches the mailer. That is the production fix.
        with override_settings(
            SITE_URL='https://kccclassstamp.pythonanywhere.com',
            ALLOWED_HOSTS=['kccclassstamp.pythonanywhere.com'],
        ):
            response = self._request(HTTP_HOST='evil.example')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(mail.outbox)

    def test_production_site_url_wins_when_the_host_is_allowed(self):
        with override_settings(
            SITE_URL='https://kccclassstamp.pythonanywhere.com',
            ALLOWED_HOSTS=['kccclassstamp.pythonanywhere.com'],
        ):
            self._request(HTTP_HOST='kccclassstamp.pythonanywhere.com')

        link = self._last_link()
        self.assertTrue(link.startswith('https://kccclassstamp.pythonanywhere.com'))
        self.assertNotIn('evil.example', link)

    def test_local_dev_site_url_is_used(self):
        from django.conf import settings

        self._request(HTTP_HOST='evil.example')
        link = self._last_link()
        expected = getattr(settings, 'SITE_URL', '').rstrip('/')
        self.assertTrue(link.startswith(expected), f'{link} does not start with {expected}')
        self.assertNotIn('evil.example', link)
