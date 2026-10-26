"""
# // ==============================================================================
# // KCC CLASSSTAMP - MIDDLEWARE SUITE TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Security & Request Pipeline Middlewares
# // Description: Comprehensive unit tests covering:
# //   - CacheControlMiddleware (HTML, redirects, sensitive JSON)
# //   - SecurityHeadersMiddleware (CSP, X-Content-Type-Options, etc.)
# //   - RequestCorrelationIdMiddleware (UUID generation & header preservation)
# //   - AttachProfileMiddleware (request.profile attachment)
# //   - SessionInactivityTimeoutMiddleware (idle logout, AJAX 401, polling immunity)
# // ==============================================================================
"""

import json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.middleware import (
    AttachProfileMiddleware,
    DisableBrowserCacheMiddleware,
    RequestCorrelationIdMiddleware,
    SecurityHeadersMiddleware,
    SessionInactivityTimeoutMiddleware,
)
from apps.core.models import Profile

User = get_user_model()


class CacheControlMiddlewareTests(TestCase):
    """Middleware must inject no-cache headers on HTML, redirects, and sensitive JSON."""

    def test_html_response_includes_no_cache_headers(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)
        self.assertIn('must-revalidate', cache_control)

    def test_logout_redirect_includes_no_cache_headers(self):
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)


class SecurityHeadersMiddlewareTests(TestCase):
    """Middleware must inject modern defense-in-depth security headers."""

    def test_security_headers_present(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(response.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')
        self.assertEqual(response.headers.get('Cross-Origin-Opener-Policy'), 'same-origin')
        self.assertEqual(response.headers.get('X-XSS-Protection'), '0')
        self.assertIn('camera=(self)', response.headers.get('Permissions-Policy', ''))
        self.assertIn("default-src 'self'", response.headers.get('Content-Security-Policy', ''))


class RequestCorrelationIdMiddlewareTests(TestCase):
    """Middleware must stamp each request and response with X-Request-ID."""

    def test_generates_request_id(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        request_id = response.headers.get('X-Request-ID')
        self.assertIsNotNone(request_id)
        self.assertTrue(len(request_id) >= 16)

    def test_preserves_inbound_request_id(self):
        custom_id = 'test-trace-id-12345'
        response = self.client.get(reverse('login'), HTTP_X_REQUEST_ID=custom_id)
        self.assertEqual(response.headers.get('X-Request-ID'), custom_id)


class AttachProfileMiddlewareTests(TestCase):
    """Middleware must attach request.profile for authenticated users."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testprofileuser', password='password123')
        self.profile = Profile.objects.create(
            user=self.user,
            role=Profile.ROLE_ADMIN,
        )

    def test_anonymous_user_has_none_profile(self):
        request = self.factory.get('/')
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()

        middleware = AttachProfileMiddleware(lambda req: req)
        middleware(request)

        self.assertIsNone(request.profile)

    def test_authenticated_user_has_attached_profile(self):
        request = self.factory.get('/')
        request.user = self.user

        middleware = AttachProfileMiddleware(lambda req: req)
        middleware(request)

        self.assertEqual(request.profile, self.profile)


class SessionInactivityTimeoutMiddlewareTests(TestCase):
    """Middleware terminates idle sessions, emits 401 for AJAX, and respects polling exemption."""

    def setUp(self):
        self.user = User.objects.create_user(username='timeoutuser', password='password123')
        Profile.objects.create(user=self.user, role=Profile.ROLE_ADMIN)

    def test_active_session_does_not_timeout(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['last_activity'] = timezone.now().isoformat()
        session.save()

        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)

    def test_inactive_session_logs_out_regular_request(self):
        self.client.force_login(self.user)
        session = self.client.session
        expired_time = timezone.now() - timedelta(seconds=2000)
        session['last_activity'] = expired_time.isoformat()
        session.save()

        res = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(
            res.url.startswith(settings.LOGIN_URL + '?next='),
            f'Expected redirect to {settings.LOGIN_URL}, got {res.url}',
        )

    def test_inactive_session_returns_401_json_for_ajax(self):
        self.client.force_login(self.user)
        session = self.client.session
        expired_time = timezone.now() - timedelta(seconds=2000)
        session['last_activity'] = expired_time.isoformat()
        session.save()

        res = self.client.get(
            reverse('admin_pending_count_json'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertEqual(data.get('error'), 'session_expired')
        self.assertTrue(
            data.get('login_url', '').startswith(settings.LOGIN_URL + '?next='),
            f"Expected login_url on {settings.LOGIN_URL}, got {data.get('login_url')}",
        )

    def test_timeout_redirect_url_resolves_to_login_page(self):
        # Regression (B-09): the default /accounts/login/ 404s — the configured
        # LOGIN_URL must point at the project's real login route.
        self.assertEqual(settings.LOGIN_URL, '/')
        res = self.client.get(settings.LOGIN_URL)
        self.assertEqual(res.status_code, 200)

    def test_polling_endpoints_do_not_refresh_last_activity(self):
        self.client.force_login(self.user)
        initial_activity = timezone.now() - timedelta(seconds=120)
        session = self.client.session
        session['last_activity'] = initial_activity.isoformat()
        session.save()

        # Call polling endpoint
        res = self.client.get(reverse('admin_pending_count_json'))
        self.assertEqual(res.status_code, 200)

        # last_activity must not have been bumped to now
        session = self.client.session
        self.assertEqual(session.get('last_activity'), initial_activity.isoformat())
