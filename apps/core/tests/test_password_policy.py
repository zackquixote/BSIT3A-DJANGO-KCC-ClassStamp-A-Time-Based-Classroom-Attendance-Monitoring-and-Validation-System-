"""
# // ==============================================================================
# // KCC CLASSSTAMP - PASSWORD POLICY TESTS (tasks 1.6 and 1.7)
# // ==============================================================================
# // Composition validator, compliant generator, last-five history, and the
# // set_user_password service contract.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import AuditEvent, PasswordHistory, Profile
from apps.core.services.credential_service import (
    PASSWORD_HISTORY_DEPTH,
    generate_compliant_password,
    password_is_reused,
    set_user_password,
)
from apps.core.validators.password_validators import CompositionPasswordValidator

User = get_user_model()


class CompositionValidatorTests(TestCase):
    def test_rejects_each_missing_character_class(self):
        cases = [
            ('alllowercase1!', 'uppercase'),
            ('ALLUPPERCASE1!', 'lowercase'),
            ('NoDigitsHere!', 'digit'),
            ('NoSpecial123A', 'special'),
            ('Sh0rt!', '8 characters'),
        ]
        for password, needle in cases:
            with self.subTest(password=password):
                with self.assertRaises(ValidationError) as ctx:
                    CompositionPasswordValidator().validate(password)
                messages = ' '.join(ctx.exception.messages)
                self.assertIn(needle, messages)

    def test_accepts_a_strong_password(self):
        CompositionPasswordValidator().validate('Str0ng-Pass-2026!')

    def test_reports_every_unmet_rule_at_once(self):
        with self.assertRaises(ValidationError) as ctx:
            CompositionPasswordValidator().validate('abc')
        # length, uppercase, digit, special — lowercase is present.
        self.assertEqual(len(ctx.exception.messages), 4)


class CompliantGeneratorTests(TestCase):
    def test_generated_passwords_always_pass_the_validator(self):
        validator = CompositionPasswordValidator()
        for _ in range(50):
            password = generate_compliant_password(12)
            validator.validate(password)  # must not raise

    def test_generated_passwords_are_unique(self):
        passwords = {generate_compliant_password(12) for _ in range(20)}
        self.assertEqual(len(passwords), 20)


class PasswordHistoryServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='hist_user',
            password='First-Str0ng-2026!',
            email='hist@example.com',
        )
        Profile.objects.create(user=self.user, role=Profile.ROLE_STUDENT)

    def test_reuse_of_current_password_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            set_user_password(
                self.user, 'First-Str0ng-2026!', validate=False,
            )
        self.assertIn('cannot reuse', str(ctx.exception))

    def test_history_is_recorded_and_pruned_to_five(self):
        current = 'First-Str0ng-2026!'
        for i in range(2, 10):
            current = f'Rotate-{i}-Str0ng!'
            set_user_password(self.user, current, validate=False)
        hashes = list(
            PasswordHistory.objects.filter(user=self.user)
            .order_by('-created_at')
            .values_list('password_hash', flat=True)
        )
        self.assertEqual(len(hashes), PASSWORD_HISTORY_DEPTH)

    def test_cannot_reuse_any_of_the_last_five(self):
        used = ['First-Str0ng-2026!']
        current = used[0]
        for i in range(2, 7):  # 6 rotations so the first leaves the window
            current = f'Rotate-{i}-Str0ng!'
            set_user_password(self.user, current, validate=False)
            used.append(current)
        # First password has been pruned out of the last-five window.
        self.assertFalse(password_is_reused(self.user, used[0]))
        # The five most recent are all rejected.
        for password in used[1:]:
            with self.assertRaises(ValueError):
                set_user_password(self.user, password, validate=False)

    def test_successful_change_audits_and_keeps_session_hash_path(self):
        events = AuditEvent.objects.filter(
            actor=self.user, action='PASSWORD_CHANGED',
        ).count()
        set_user_password(
            self.user, 'Brand-New-Str0ng-2026!', validate=False, actor=self.user,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                actor=self.user, action='PASSWORD_CHANGED',
            ).count(),
            events + 1,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Brand-New-Str0ng-2026!'))

    def test_weak_password_is_rejected_when_validating(self):
        with self.assertRaises(ValueError) as ctx:
            set_user_password(self.user, 'weakpass', validate=True)
        self.assertIn('uppercase', str(ctx.exception))
        self.assertTrue(self.user.check_password('First-Str0ng-2026!'))
