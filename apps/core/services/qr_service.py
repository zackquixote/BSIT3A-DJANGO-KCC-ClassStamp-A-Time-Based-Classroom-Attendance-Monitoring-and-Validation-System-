"""
// ==============================================================================
// KCC CLASSSTAMP - DYNAMIC QR / TOTP CREDENTIAL SERVICE
// ==============================================================================
// Subsystem: Student rotating badge generation & teacher-side verification.
// Description:
//   - Converts the stored 64-char hex `Profile.qr_secret` into a base32 TOTP seed.
//   - Generates the `classstamp:<student_number>:<token>` payload scanned by teachers.
//   - Renders that payload to a PNG data-URI for the student badge page.
//   - Verifies tokens using the same parameters as the scan API so the two sides
//     can never drift apart.
// References: apps/core/views/session_views.py | docs/02_SECURITY.md
// ==============================================================================
"""

import base64
from io import BytesIO

import pyotp
import qrcode

TOTP_INTERVAL = 30
PAYLOAD_PREFIX = 'classstamp'


def secret_to_base32(raw_secret):
    """
    // Convert a stored hex/plain secret into a base32 secret accepted by pyotp.
    // Mirrors the historical scan-API behaviour for backward compatibility.
    """
    raw_secret = raw_secret or ''
    if not raw_secret:
        return ''
    try:
        raw_bytes = bytes.fromhex(raw_secret)
        return base64.b32encode(raw_bytes).decode('utf-8').rstrip('=')
    except (ValueError, TypeError):
        return base64.b32encode(raw_secret.encode()).decode('utf-8').rstrip('=')


def get_totp(profile):
    """Build a pyotp.TOTP instance for a student profile, or None if unactivated."""
    b32_secret = secret_to_base32(getattr(profile, 'qr_secret', None))
    if not b32_secret:
        return None
    return pyotp.TOTP(b32_secret, interval=TOTP_INTERVAL)


def current_token(profile):
    """Return the current 6-digit token for a profile, or None if unactivated."""
    totp = get_totp(profile)
    return totp.now() if totp else None


def verify_token(profile, token, valid_window=1):
    """Verify a token with the same window the scan API uses."""
    totp = get_totp(profile)
    if not totp:
        return False
    try:
        return bool(totp.verify(str(token).strip(), valid_window=valid_window))
    except Exception:
        return False


def build_payload(profile, token):
    """Assemble the canonical payload string embedded in the student QR."""
    number = (getattr(profile, 'student_number', None) or profile.user.get_username()).strip()
    return f"{PAYLOAD_PREFIX}:{number}:{token}"


def qr_png_data_uri(payload, box_size=8, border=2):
    """Render a payload to a base64 PNG data-URI suitable for an <img> src."""
    image = qrcode.make(payload, box_size=box_size, border=border)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f"data:image/png;base64,{encoded}"
