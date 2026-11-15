"""
# // ==============================================================================
# // KCC CLASSSTAMP - PRE-AUTH RATE LIMIT TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Request Pipeline
# // Description: /register/check-availability/ and /password-reset/ used to be
# //   unlimited anonymous oracles. They now share a per-IP fixed-window bucket.
# // ==============================================================================
"""

from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.core.middleware.ratelimit import RateLimitMiddleware


def _ok(request):
    return HttpResponse('ok')


class AuthSensitiveRateLimitTests(TestCase):
    """The availability oracle and password-reset share one per-IP bucket."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _mw(self):
        return RateLimitMiddleware(_ok)

    @override_settings(RATE_LIMIT_AUTHSENSITIVE=3)
    def test_availability_oracle_is_throttled(self):
        mw = self._mw()
        last = None
        for _ in range(4):
            last = mw(self.factory.get('/register/check-availability/?type=student_number&value=x'))
        self.assertEqual(last.status_code, 429)
        self.assertGreaterEqual(int(last['Retry-After']), 1)

    @override_settings(RATE_LIMIT_AUTHSENSITIVE=3)
    def test_password_reset_is_throttled(self):
        mw = self._mw()
        last = None
        for _ in range(4):
            last = mw(self.factory.post('/password-reset/', {'identifier': 'x'}))
        self.assertEqual(last.status_code, 429)

    @override_settings(RATE_LIMIT_AUTHSENSITIVE=3)
    def test_get_and_post_share_one_ip_bucket(self):
        mw = self._mw()
        # Two GETs + two POSTs = four hits against a limit of 3.
        mw(self.factory.get('/register/check-availability/'))
        mw(self.factory.get('/register/check-availability/'))
        mw(self.factory.post('/password-reset/', {'identifier': 'x'}))
        last = mw(self.factory.post('/password-reset/', {'identifier': 'x'}))
        self.assertEqual(last.status_code, 429)

    @override_settings(RATE_LIMIT_AUTHSENSITIVE=3)
    def test_different_ip_is_a_different_bucket(self):
        mw = self._mw()
        for _ in range(4):
            mw(self.factory.get('/register/check-availability/', REMOTE_ADDR='10.9.9.9'))
        fresh = mw(self.factory.get('/register/check-availability/', REMOTE_ADDR='10.9.9.10'))
        self.assertEqual(fresh.status_code, 200)

    def test_login_page_is_not_in_the_auth_bucket(self):
        mw = self._mw()
        last = None
        for _ in range(35):
            last = mw(self.factory.get('/'))
        self.assertEqual(last.status_code, 200)
