"""
# // ==============================================================================
# // KCC CLASSSTAMP - SELF-SERVICE PASSWORD RESET TESTS
# // ==============================================================================
# // "Forgot password?" used to be a browser alert. It is now a signed, single-use,
# // 30-minute link: no account enumeration, sessions revoked, 2FA untouched.
# ==============================================================================
"""

import re
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as _User  # noqa: F401  (keeps import explicit)
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditEvent, Profile
from apps.core.services import password_reset_service

User = get_user_model()

OLD_PW = 'Old-Str0ng-Pass-2026'
NEW_PW = 'New-Str0ng-Pass-2026'


class PasswordResetBase(TestCase):
    def setUp(self):
        # The reset endpoint is throttled per client address through the cache;
        # clear it so one test's requests cannot silence the next test's mail.
        cache.clear()
        self.user = User.objects.create_user(
            username='reset_user', email='reset@example.com', first_name='Ana',
        )
        self.user.set_password(OLD_PW)
        self.user.save()
        self.profile = Profile.objects.create(
            user=self.user, role=Profile.ROLE_STUDENT, student_number='2026-4400',
            approval_status=Profile.APPROVAL_APPROVED,
        )

    def _request_reset(self, identifier='reset@example.com'):
        return self.client.post(reverse('password_reset_request'), {'identifier': identifier})

    def _token_from_mail(self):
        body = mail.outbox[-1].body
        match = re.search(r'/password-reset/([^/\s]+)/', body)
        # The link is percent-encoded; a browser decodes it before the view sees it.
        return unquote(match.group(1)) if match else None


class ResetRequestTests(PasswordResetBase):
    def test_known_account_gets_a_link(self):
        response = self._request_reset()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password-reset/', mail.outbox[0].body)
        self.assertTrue(response.context['submitted'])
        self.assertTrue(
            AuditEvent.objects.filter(action='PASSWORD_RESET_REQUESTED').exists()
        )

    def test_unknown_account_gets_the_same_page_and_no_mail(self):
        response = self._request_reset('nobody@example.com')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(response.context['submitted'])

    def test_username_and_student_number_both_work(self):
        self._request_reset('reset_user')
        self.assertEqual(len(mail.outbox), 1)

        self._request_reset('2026-4400')
        self.assertEqual(len(mail.outbox), 2)

    def test_account_without_email_is_silently_skipped(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])

        self._request_reset('reset_user')

        self.assertEqual(len(mail.outbox), 0)


class ResetConfirmTests(PasswordResetBase):
    def _link(self):
        self._request_reset()
        return self._token_from_mail()

    def test_token_opens_the_form(self):
        token = self._link()

        response = self.client.get(reverse('password_reset_confirm', args=[token]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['account'], 'reset_user')

    def test_new_password_is_accepted_and_audited(self):
        token = self._link()

        response = self.client.post(
            reverse('password_reset_confirm', args=[token]),
            {'new_password': NEW_PW, 'confirm_password': NEW_PW},
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PW))
        self.assertFalse(self.user.check_password(OLD_PW))

        event = AuditEvent.objects.get(action='PASSWORD_RESET_COMPLETED')
        self.assertIn('Password changed', event.new_value)

    def test_weak_password_is_rejected(self):
        token = self._link()

        response = self.client.post(
            reverse('password_reset_confirm', args=[token]),
            {'new_password': '123', 'confirm_password': '123'},
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PW))

    def test_mismatched_passwords_are_rejected(self):
        token = self._link()

        response = self.client.post(
            reverse('password_reset_confirm', args=[token]),
            {'new_password': NEW_PW, 'confirm_password': NEW_PW + 'x'},
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PW))

    def test_token_is_single_use(self):
        token = self._link()
        self.client.post(
            reverse('password_reset_confirm', args=[token]),
            {'new_password': NEW_PW, 'confirm_password': NEW_PW},
        )

        second = self.client.get(reverse('password_reset_confirm', args=[token]))

        self.assertEqual(second.status_code, 302)
        self.assertEqual(second.url, reverse('password_reset_request'))

    def test_expired_token_is_refused(self):
        token = self._link()

        original = password_reset_service.RESET_TOKEN_MAX_AGE
        password_reset_service.RESET_TOKEN_MAX_AGE = 0
        try:
            response = self.client.get(reverse('password_reset_confirm', args=[token]))
        finally:
            password_reset_service.RESET_TOKEN_MAX_AGE = original

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('password_reset_request'))

    def test_garbage_token_is_refused(self):
        response = self.client.get(reverse('password_reset_confirm', args=['not-a-token']))

        self.assertEqual(response.status_code, 302)

    def test_reset_revokes_existing_sessions(self):
        # Sign in as the user first, then reset from another client.
        other = self.client_class()
        other.post(reverse('login'), {'username': 'reset_user', 'password': OLD_PW})
        self.assertIn('_auth_user_id', other.session)

        token = self._link()
        self.client.post(
            reverse('password_reset_confirm', args=[token]),
            {'new_password': NEW_PW, 'confirm_password': NEW_PW},
        )

        # The old session no longer identifies a logged-in user.
        other.get(reverse('dashboard'))
        self.assertNotIn('_auth_user_id', other.session)


class ResetDoesNotBypassTwoFactorTests(PasswordResetBase):
    def test_admin_with_two_factor_still_needs_the_code(self):
        import pyotp

        self.profile.role = Profile.ROLE_ADMIN
        self.profile.totp_secret = pyotp.random_base32()
        self.profile.totp_enabled = True
        self.profile.save()

        self._request_reset()
        token = self._token_from_mail()
        self.client.post(
            reverse('password_reset_confirm', args=[token]),
            {'new_password': NEW_PW, 'confirm_password': NEW_PW},
        )

        response = self.client.post(reverse('login'), {
            'username': 'reset_user',
            'password': NEW_PW,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('two_factor_verify'))
        self.assertNotIn('_auth_user_id', self.client.session)
