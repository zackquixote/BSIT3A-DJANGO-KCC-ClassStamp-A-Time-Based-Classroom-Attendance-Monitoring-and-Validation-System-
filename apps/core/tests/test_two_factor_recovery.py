"""
# // ==============================================================================
# // KCC CLASSSTAMP - TWO-FACTOR RECOVERY TESTS
# // ==============================================================================
# // The escape hatch for a lost phone:
# //   - enrolment issues 10 single-use codes, shown exactly once
# //   - a code works at the login challenge and cannot be replayed
# //   - `manage.py reset_totp` is the break-glass path and is audited
# ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

import pyotp

from apps.core.models import AuditEvent, Profile, RecoveryCode
from apps.core.services.two_factor_service import generate_recovery_codes

User = get_user_model()

LOGIN_PW = 'Str0ng-Test-Pass-2026'


class RecoveryEnrolmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rec_admin', email='rec@example.com')
        self.user.set_password(LOGIN_PW)
        self.user.save()
        self.profile = Profile.objects.create(user=self.user, role=Profile.ROLE_ADMIN)
        self.client.force_login(self.user)

    def _enable(self):
        self.client.get(reverse('two_factor_setup'))
        secret = self.client.session['pending_2fa_secret']
        return self.client.post(
            reverse('two_factor_setup'),
            {'action': 'enable', 'code': pyotp.TOTP(secret).now()},
            follow=True,
        )

    def test_enrolment_issues_ten_codes_and_shows_them_once(self):
        response = self._enable()

        codes = response.context['new_recovery_codes']
        self.assertEqual(len(codes), 10)
        self.assertEqual(RecoveryCode.objects.filter(profile=self.profile).count(), 10)

        again = self.client.get(reverse('two_factor_setup'))
        self.assertNotIn('new_recovery_codes', again.context)

    def test_codes_are_hashed_not_stored_plain(self):
        response = self._enable()
        plaintext = response.context['new_recovery_codes'][0]

        self.assertFalse(
            RecoveryCode.objects.filter(code_hash=plaintext).exists(),
            'The plaintext code must never be stored.',
        )

    def test_disabling_removes_the_codes(self):
        self._enable()
        secret = self.profile.totp_secret
        self.profile.refresh_from_db()

        self.client.post(reverse('two_factor_setup'), {
            'action': 'disable',
            'code': pyotp.TOTP(self.profile.totp_secret).now(),
        })

        self.assertEqual(RecoveryCode.objects.filter(profile=self.profile).count(), 0)


class RecoveryLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rec_login')
        self.user.set_password(LOGIN_PW)
        self.user.save()
        self.secret = pyotp.random_base32()
        self.profile = Profile.objects.create(
            user=self.user,
            role=Profile.ROLE_ADMIN,
            totp_secret=self.secret,
            totp_enabled=True,
        )
        self.codes = generate_recovery_codes(self.profile)

    def _password_step(self):
        return self.client.post(reverse('login'), {
            'username': 'rec_login',
            'password': LOGIN_PW,
        })

    def test_recovery_code_completes_login(self):
        self._password_step()

        response = self.client.post(
            reverse('two_factor_verify'), {'code': self.codes[0]}, follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('_auth_user_id', self.client.session)
        record = RecoveryCode.objects.get(code_hash__isnull=False, used_at__isnull=False)
        self.assertIsNotNone(record.used_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action='TWO_FACTOR_SUCCESS', reason__icontains='recovery'
            ).exists()
        )

    def test_recovery_code_cannot_be_reused(self):
        self._password_step()
        self.client.post(reverse('two_factor_verify'), {'code': self.codes[0]})
        self.client.logout()

        self._password_step()
        response = self.client.post(reverse('two_factor_verify'), {'code': self.codes[0]})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_authenticator_still_works(self):
        self._password_step()

        response = self.client.post(
            reverse('two_factor_verify'), {'code': pyotp.TOTP(self.secret).now()}
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_remaining_count_decreases(self):
        self._password_step()
        self.client.post(reverse('two_factor_verify'), {'code': self.codes[0]})

        self.assertEqual(
            RecoveryCode.objects.filter(profile=self.profile, used_at__isnull=True).count(),
            9,
        )


class ResetTotpCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reset_admin')
        self.profile = Profile.objects.create(
            user=self.user,
            role=Profile.ROLE_ADMIN,
            totp_secret=pyotp.random_base32(),
            totp_enabled=True,
        )
        generate_recovery_codes(self.profile)

    def test_command_clears_factor_and_codes(self):
        call_command('reset_totp', 'reset_admin', '--reason', 'Phone lost in transit')

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.totp_enabled)
        self.assertEqual(self.profile.totp_secret, '')
        self.assertEqual(RecoveryCode.objects.filter(profile=self.profile).count(), 0)

        event = AuditEvent.objects.get(action='TWO_FACTOR_RESET')
        self.assertEqual(event.reason, 'Phone lost in transit')

    def test_command_accepts_email(self):
        self.user.email = 'reset@example.com'
        self.user.save(update_fields=['email'])

        call_command('reset_totp', 'reset@example.com')

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.totp_enabled)

    def test_unknown_account_fails_loudly(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('reset_totp', 'nobody-here')
