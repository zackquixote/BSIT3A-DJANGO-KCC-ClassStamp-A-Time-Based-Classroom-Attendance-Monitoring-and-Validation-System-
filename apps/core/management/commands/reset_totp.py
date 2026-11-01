"""
# // ==============================================================================
# // KCC CLASSSTAMP - BREAK-GLASS TWO-FACTOR RESET
# // ==============================================================================
# // Usage: python manage.py reset_totp <username|email> [--reason "..."]
# // Description:
# //   Removes an administrator's TOTP factor and every recovery code. This is the
# //   last resort when both the authenticator and the printed codes are gone —
# //   without it the account is unrecoverable and the only fix is editing the
# //   database by hand.
# //   Requires server access, which is the point: it cannot be triggered remotely.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import AuditEvent, Profile
from apps.core.services.two_factor_service import reset_two_factor

User = get_user_model()


class Command(BaseCommand):
    help = 'Removes two-factor authentication and recovery codes for one account'

    def add_arguments(self, parser):
        parser.add_argument('identifier', help='Username or email of the account')
        parser.add_argument('--reason', default='', help='Recorded in the audit trail')

    def handle(self, *args, **options):
        identifier = options['identifier'].strip()
        reason = (options['reason'] or '').strip() or 'Break-glass reset via management command'

        user = User.objects.filter(username__iexact=identifier).first()
        if user is None:
            user = User.objects.filter(email__iexact=identifier).first()
        if user is None:
            raise CommandError(f'No account matches "{identifier}".')

        profile = getattr(user, 'classstamp_profile', None)
        if profile is None:
            raise CommandError(f'"{identifier}" has no ClassStamp profile.')

        was_enabled = profile.totp_enabled
        deleted_codes = reset_two_factor(profile)

        AuditEvent.objects.create(
            actor=None,
            action='TWO_FACTOR_RESET',
            object_type='Profile',
            object_id=str(profile.pk),
            old_value=f'totp_enabled={was_enabled}, codes={deleted_codes}',
            new_value='totp_enabled=False',
            reason=reason,
        )

        state = 'disabled' if was_enabled else 'already off'
        self.stdout.write(self.style.SUCCESS(
            f'{user.get_username()}: two-factor {state}; {deleted_codes} recovery code(s) removed.'
        ))
