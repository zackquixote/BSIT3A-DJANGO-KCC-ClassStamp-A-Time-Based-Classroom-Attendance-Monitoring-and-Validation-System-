"""
# // ==============================================================================
# // KCC CLASSSTAMP - CACHE CONTROL MIDDLEWARE TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Security Middleware
# // Description: Verifies that the CacheControlMiddleware injects the required
# //   no-cache headers on every response (HTML pages and redirects), preventing
# //   browsers from serving stale authenticated pages from cache.
# // ==============================================================================
"""

from django.test import TestCase
from django.urls import reverse


class CacheControlMiddlewareTests(TestCase):
    """Middleware must inject no-cache headers on every HTTP response."""

    def test_html_response_includes_no_cache_headers(self):
        # The login page is publicly accessible; verify headers are present.
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)
        self.assertIn('must-revalidate', cache_control)

    def test_logout_redirect_includes_no_cache_headers(self):
        # Redirects must also carry no-cache headers.
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        cache_control = response.headers.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)
