"""
# // ==============================================================================
# // KCC CLASSSTAMP - TWO-FACTOR AUTHENTICATION SERVICE (ADMIN / REGISTRAR)
# // ==============================================================================
# // Subsystem: Account Security
# // Description:
# //   TOTP second factor for privileged accounts. The same RFC-6238 machinery
# //   already used for student QR badges (pyotp) is applied to the login form:
# //     - provision: base32 seed + otpauth:// URI + QR data-URI
# //     - verify:    +/-1 step window (30s steps), constant-time inside pyotp
# //   Student QR secrets and admin TOTP seeds are deliberately separate fields:
# //   one identifies a student to a classroom scanner, the other proves an
# //   administrator to the login form, and compromising one must not compromise
# //   the other.
# // References: apps/core/views/auth_views.py | docs/02_SECURITY.md
# // ==============================================================================
"""

import base64
from io import BytesIO
import re
import secrets

import pyotp
import qrcode
from django.utils import timezone

from apps.core.models import Profile, RecoveryCode
from apps.core.models.two_factor import hash_recovery_code

TOTP_INTERVAL = 30
TOTP_VALID_WINDOW = 1
ISSUER_NAME = 'KCC ClassStamp'


def new_secret():
    """Generate a fresh base32 seed suitable for an authenticator app."""
    return pyotp.random_base32()


def build_totp(secret):
    """Return a pyotp.TOTP for a seed, or None when the seed is unusable."""
    secret = (secret or '').strip()
    if not secret:
        return None
    try:
        return pyotp.TOTP(secret, interval=TOTP_INTERVAL)
    except Exception:
        return None


def provisioning_uri(profile, secret):
    """otpauth:// URI consumed by Google Authenticator, Authy, 1Password, etc."""
    label = profile.user.get_username()
    if profile.user.email:
        label = f'{ISSUER_NAME}:{label}'
    totp = build_totp(secret)
    if totp is None:
        return ''
    return totp.provisioning_uri(name=label, issuer_name=ISSUER_NAME)


def qr_data_uri(uri, box_size=6, border=2):
    """Render an otpauth URI to a base64 PNG data-URI for an <img> tag."""
    if not uri:
        return ''
    image = qrcode.make(uri, box_size=box_size, border=border)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def verify_code(profile, code):
    """Verify a 6-digit authenticator code against the profile's stored seed."""
    return verify_code_for_secret(getattr(profile, 'totp_secret', ''), code)


def verify_code_for_secret(secret, code):
    """Same check against a not-yet-saved seed (enrollment confirmation)."""
    totp = build_totp(secret)
    if totp is None:
        return False
    code = (code or '').strip().replace(' ', '')
    if not code.isdigit() or len(code) != 6:
        return False
    try:
        return bool(totp.verify(code, valid_window=TOTP_VALID_WINDOW))
    except Exception:
        return False


def is_privileged(profile):
    """Only administrators/registrars are subject to the second factor."""
    if profile is None:
        return False
    return profile.role == Profile.ROLE_ADMIN


def two_factor_required(profile):
    """True when this account must present a code in addition to its password."""
    return (
        is_privileged(profile)
        and profile.totp_enabled
        and bool((profile.totp_secret or '').strip())
    )


# // ==============================================================================
# // RECOVERY CODES
# // ==============================================================================
# // A lost phone must not mean a dead account. Each administrator gets a fixed
# // set of single-use codes; only their hashes are stored, and a spent code is
# // marked rather than removed so the audit trail can still name it.
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_RE = re.compile(r'^[A-Za-z0-9]{4,8}-[A-Za-z0-9]{4,8}$')


def _new_raw_code():
    return f'{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}'


def generate_recovery_codes(profile, count=RECOVERY_CODE_COUNT):
    """
    // Replace any unused codes with a fresh set and return the plaintext ONCE.
    // The caller is expected to show them to the account holder immediately; they
    // are unrecoverable afterwards.
    """
    RecoveryCode.objects.filter(profile=profile, used_at__isnull=True).delete()

    codes = []
    for _ in range(count):
        raw = _new_raw_code()
        RecoveryCode.objects.create(profile=profile, code_hash=hash_recovery_code(raw))
        codes.append(raw)
    return codes


def is_recovery_code_format(code):
    return bool(RECOVERY_CODE_RE.match((code or '').strip()))


def consume_recovery_code(profile, code):
    """Spend a code atomically. True only for the request that wins the update."""
    digest = hash_recovery_code(code)
    return RecoveryCode.objects.filter(
        profile=profile,
        code_hash=digest,
        used_at__isnull=True,
    ).update(used_at=timezone.now()) == 1


def remaining_recovery_codes(profile):
    return RecoveryCode.objects.filter(profile=profile, used_at__isnull=True).count()


def verify_second_factor(profile, code):
    """
    // Accept either a live 6-digit TOTP or an unused recovery code.
    // Returns {'ok', 'method', 'remaining'} so the caller can tell the user which
    // one was used and how many backups are left.
    """
    if verify_code(profile, code):
        return {'ok': True, 'method': 'TOTP', 'remaining': remaining_recovery_codes(profile)}

    if is_recovery_code_format(code) and consume_recovery_code(profile, code):
        return {
            'ok': True,
            'method': 'RECOVERY',
            'remaining': remaining_recovery_codes(profile),
        }

    return {'ok': False, 'method': '', 'remaining': None}


def reset_two_factor(profile):
    """Break-glass: remove the second factor and every backup code."""
    profile.totp_enabled = False
    profile.totp_secret = ''
    profile.totp_confirmed_at = None
    profile.save(update_fields=['totp_enabled', 'totp_secret', 'totp_confirmed_at'])
    deleted, _ = RecoveryCode.objects.filter(profile=profile).delete()
    return deleted
