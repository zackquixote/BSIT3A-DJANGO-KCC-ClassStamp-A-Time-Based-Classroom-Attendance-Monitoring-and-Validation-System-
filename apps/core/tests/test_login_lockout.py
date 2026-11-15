"""
# // ==============================================================================
# // KCC CLASSSTAMP - LOGIN LOCKOUT ENFORCEMENT TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Authentication Throttling
# // Description: Proves the failed-attempt lockout lives on the server, not in
# //   the countdown that draws it. The browser-side review that triggered this
# //   suite could only observe the timer, so each claim it raised is pinned here:
# //
# //   1. Five failures lock the account and the refusal is an HTTP 429, not a
# //      200 page that merely says "too many attempts".
# //   2. Reloading the sign-in page cannot reopen the form: the lock is read
# //      from the cache on GET as well as POST.
# //   3. The account bucket holds across a different client address, so
# //      changing network does not buy five more guesses.
# //   4. A correct password is still refused while the window is open.
# //   5. The window ends, a success clears the counters, and the page ships the
# //      accessibility contract the controller relies on (aria-pressed, one
# //      status region).
# // ==============================================================================
"""

import math
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Profile
from apps.core.views.helpers import LOCK_DURATION, MAX_FAILED_ATTEMPTS

User = get_user_model()

USERNAME = 'lock_target'
RIGHT_PASSWORD = 'CorrectHorse9!Battery'
WRONG_PASSWORD = 'WrongPass!2026'
CLIENT_IP = '10.0.0.5'
OTHER_IP = '203.0.113.9'


class LoginLockoutTests(TestCase):
    """Lockout behaviour observed from the client, one claim per test."""

    def setUp(self):
        # // LocMem survives between tests in one process; a stray counter from
        # // an earlier test would silently pre-lock this one.
        cache.clear()
        self.url = reverse('login')
        self.user = User.objects.create_user(username=USERNAME, password=RIGHT_PASSWORD)
        Profile.objects.create(user=self.user, role=Profile.ROLE_ADMIN)

    def tearDown(self):
        # // The IP bucket is real cache state with a one-minute TTL. Leaving it
        # // behind would lock every later test that signs in from 127.0.0.1.
        cache.clear()

    def _post(self, password=None, username=USERNAME, ip=CLIENT_IP):
        password = WRONG_PASSWORD if password is None else password
        return self.client.post(
            self.url,
            {'username': username, 'password': password},
            REMOTE_ADDR=ip,
        )

    def _exhaust_attempts(self, ip=CLIENT_IP):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._post(ip=ip)

    # --------------------------------------------------------------------------
    # 1. Threshold answers 429
    # --------------------------------------------------------------------------
    def test_attempt_below_threshold_is_a_normal_retry(self):
        response = self._post(password=WRONG_PASSWORD)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '4 attempts remaining')

    def test_fifth_failure_locks_with_429_and_retry_after(self):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            self.assertEqual(self._post().status_code, 200)

        locked = self._post()

        self.assertEqual(locked.status_code, 429)
        self.assertGreaterEqual(int(locked['Retry-After']), 1)
        self.assertLessEqual(int(locked['Retry-After']), int(LOCK_DURATION.total_seconds()))
        self.assertTrue(locked.context['locked'])
        self.assertContains(locked, 'Too many failed attempts', status_code=429)

    # --------------------------------------------------------------------------
    # 2. A reload cannot reopen the form
    # --------------------------------------------------------------------------
    def test_reload_during_lockout_is_refused(self):
        self._exhaust_attempts()

        reloaded = self.client.get(self.url)

        self.assertEqual(reloaded.status_code, 429)
        self.assertTrue(reloaded.context['locked'])
        self.assertGreaterEqual(reloaded.context['remaining'], 1)
        self.assertContains(reloaded, 'data-remaining=', status_code=429)
        # // The countdown node and the Retry-After header must agree, otherwise
        # // the page unlocks before or after the server does.
        self.assertEqual(
            int(reloaded['Retry-After']),
            reloaded.context['remaining'],
        )

    def test_locked_form_is_disabled(self):
        self._exhaust_attempts()

        body = self.client.get(self.url).content.decode()

        self.assertIn('id="login-btn"', body)
        self.assertGreaterEqual(body.count('disabled'), 3, 'username, password and submit must all be disabled')

    # --------------------------------------------------------------------------
    # 3. The account bucket follows the account, not the connection
    # --------------------------------------------------------------------------
    def test_account_lock_holds_across_client_addresses(self):
        self._exhaust_attempts(ip=CLIENT_IP)

        # // A fresh client has no session and no cookie: only the account
        # // bucket can still know about the lock.
        other = self.client_class(REMOTE_ADDR=OTHER_IP)
        response = other.post(self.url, {'username': USERNAME, 'password': RIGHT_PASSWORD})

        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', other.session)

    # --------------------------------------------------------------------------
    # 4. The right password does not jump the queue
    # --------------------------------------------------------------------------
    def test_correct_password_is_refused_while_locked(self):
        self._exhaust_attempts()

        response = self._post(password=RIGHT_PASSWORD)

        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    # --------------------------------------------------------------------------
    # 5. Expiry, recovery and the page contract
    # --------------------------------------------------------------------------
    def test_window_expiry_reopens_sign_in(self):
        # // A negative window makes the lock it creates already expired, which
        # // is the same state the cache reaches once the real minute passes.
        with mock.patch(
            'apps.core.views.helpers.auth_helpers.LOCK_DURATION',
            timedelta(seconds=-1),
        ):
            self._exhaust_attempts()

        response = self._post(password=RIGHT_PASSWORD)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_success_clears_the_counters(self):
        self._post(password=WRONG_PASSWORD)
        self._post(password=WRONG_PASSWORD)

        response = self._post(password=RIGHT_PASSWORD)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('failed_attempts'), 0)
        self.assertIsNone(cache.get(f'login_failures:account:{USERNAME}'))
        self.assertIsNone(cache.get(f'login_failures:ip:{CLIENT_IP}'))

    def test_login_page_ships_the_toggle_and_status_contract(self):
        body = self.client.get(self.url).content.decode()

        self.assertEqual(body.count('id="login-status"'), 1)
        self.assertIn('aria-pressed="false"', body)
        self.assertIn('aria-controls="id_password"', body)
        self.assertIn('aria-describedby="login-status"', body)

    def test_remaining_seconds_are_rounded_up(self):
        # // Truncation released the client up to a second early; a countdown
        # // that ends before the server does produces a mystery re-lock.
        from apps.core.views.helpers import _set_lock_state

        request = self.client.get(self.url).wsgi_request
        _set_lock_state(request, USERNAME)

        from apps.core.views.helpers import _get_lock_state
        _, remaining = _get_lock_state(request, USERNAME)

        self.assertEqual(remaining, math.ceil(LOCK_DURATION.total_seconds()))
