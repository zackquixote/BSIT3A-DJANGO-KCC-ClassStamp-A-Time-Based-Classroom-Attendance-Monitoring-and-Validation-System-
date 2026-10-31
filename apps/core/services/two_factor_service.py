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

import pyotp
import qrcode

from apps.core.models import Profile

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
