"""
# // ==============================================================================
# // KCC CLASSSTAMP - TWO-FACTOR AUTHENTICATION TESTS
# // ==============================================================================
# // Covers the admin/registrar second factor:
# //   - enrollment: seed provisioned, confirmed only with a valid code
# //   - login gate: a correct password alone must NOT authenticate
# //   - wrong code / attempt budget / expired challenge window
# //   - accounts without 2FA (teachers, students, unenrolled admins) unaffected
# ==============================================================================
"""

from datetime import timedelta
from unittest import mock

import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditEvent, Profile

User = get_user_model()

LOGIN_PW = 'Str0ng-Test-Pass-2026'


class TwoFactorEnrollmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tfa_admin', email='tfa@example.com')
        self.user.set_password(LOGIN_PW)
        self.user.save()
        self.profile = Profile.objects.create(user=self.user, role=Profile.ROLE_ADMIN)
        self.client.force_login(self.user)

    def test_setup_page_provisions_a_seed(self):
        response = self.client.get(reverse('two_factor_setup'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.profile.totp_enabled)
        self.assertIn('pending_2fa_secret', self.client.session)
        self.assertIn('otpauth://', response.context['otpauth_uri'])
        self.assertTrue(response.context['qr_data_uri'].startswith('data:image/png;base64,'))

    def test_valid_code_enables_two_factor(self):
        self.client.get(reverse('two_factor_setup'))
        secret = self.client.session['pending_2fa_secret']

        response = self.client.post(reverse('two_factor_setup'), {
            'action': 'enable',
            'code': pyotp.TOTP(secret).now(),
        })

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.totp_enabled)
        self.assertEqual(self.profile.totp_secret, secret)
        self.assertIsNotNone(self.profile.totp_confirmed_at)
        self.assertTrue(AuditEvent.objects.filter(action='TWO_FACTOR_ENABLED').exists())

    def test_wrong_code_does_not_enable(self):
        self.client.get(reverse('two_factor_setup'))

        response = self.client.post(reverse('two_factor_setup'), {
            'action': 'enable',
            'code': '000000',
        })

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.totp_enabled)
        self.assertEqual(self.profile.totp_secret, '')

    def test_disable_requires_a_current_code(self):
        secret = pyotp.random_base32()
        self.profile.totp_secret = secret
        self.profile.totp_enabled = True
        self.profile.totp_confirmed_at = timezone.now()
        self.profile.save()

        bad = self.client.post(reverse('two_factor_setup'), {'action': 'disable', 'code': '000000'})
        self.assertEqual(bad.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.totp_enabled, 'A wrong code must not remove the factor.')

        good = self.client.post(reverse('two_factor_setup'), {
            'action': 'disable', 'code': pyotp.TOTP(secret).now(),
        })
        self.assertEqual(good.status_code, 302)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.totp_enabled)
        self.assertEqual(self.profile.totp_secret, '')
        self.assertTrue(AuditEvent.objects.filter(action='TWO_FACTOR_DISABLED').exists())

    def test_non_admin_cannot_reach_setup(self):
        teacher = User.objects.create_user(username='tfa_teacher')
        Profile.objects.create(user=teacher, role=Profile.ROLE_TEACHER)
        self.client.force_login(teacher)

        response = self.client.get(reverse('two_factor_setup'))

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse('two_factor_setup'))


class TwoFactorLoginGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='gate_admin')
        self.user.set_password(LOGIN_PW)
        self.user.save()

        self.secret = pyotp.random_base32()
        self.profile = Profile.objects.create(
            user=self.user,
            role=Profile.ROLE_ADMIN,
            totp_secret=self.secret,
            totp_enabled=True,
            totp_confirmed_at=timezone.now(),
        )

    def _password_step(self):
        return self.client.post(reverse('login'), {
            'username': 'gate_admin',
            'password': LOGIN_PW,
        })

    def _code(self):
        return pyotp.TOTP(self.secret).now()

    def test_password_alone_does_not_authenticate(self):
        response = self._password_step()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('two_factor_verify'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_valid_code_completes_login(self):
        self._password_step()

        response = self.client.post(reverse('two_factor_verify'), {'code': self._code()})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        self.assertIn('_auth_user_id', self.client.session)
        self.assertTrue(AuditEvent.objects.filter(action='TWO_FACTOR_SUCCESS').exists())

    def test_wrong_code_keeps_session_unauthenticated(self):
        self._password_step()

        response = self.client.post(reverse('two_factor_verify'), {'code': '000000'})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(AuditEvent.objects.filter(action='TWO_FACTOR_FAILED').exists())

    def test_attempt_budget_locks_the_challenge(self):
        self._password_step()

        with mock.patch('apps.core.views.auth_views.MAX_2FA_ATTEMPTS', 2):
            self.client.post(reverse('two_factor_verify'), {'code': '000000'})
            self.client.post(reverse('two_factor_verify'), {'code': '000000'})
            response = self.client.post(reverse('two_factor_verify'), {'code': '000000'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn('pending_2fa_user_id', self.client.session)
        self.assertTrue(AuditEvent.objects.filter(action='TWO_FACTOR_LOCKED').exists())

    def test_expired_challenge_is_refused(self):
        self._password_step()

        session = self.client.session
        session['pending_2fa_at'] = (timezone.now() - timedelta(minutes=10)).timestamp()
        session.save()

        response = self.client.post(reverse('two_factor_verify'), {'code': self._code()})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_challenge_requires_a_pending_password_step(self):
        response = self.client.post(reverse('two_factor_verify'), {'code': self._code()})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

    def test_admin_without_two_factor_logs_in_directly(self):
        self.profile.totp_enabled = False
        self.profile.totp_secret = ''
        self.profile.save()

        response = self._password_step()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_teacher_login_is_unaffected(self):
        teacher = User.objects.create_user(username='gate_teacher')
        teacher.set_password(LOGIN_PW)
        teacher.save()
        Profile.objects.create(user=teacher, role=Profile.ROLE_TEACHER)

        response = self.client.post(reverse('login'), {
            'username': 'gate_teacher',
            'password': LOGIN_PW,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        self.assertIn('_auth_user_id', self.client.session)
