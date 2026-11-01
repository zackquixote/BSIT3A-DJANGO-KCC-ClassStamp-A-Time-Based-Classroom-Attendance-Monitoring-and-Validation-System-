"""
# // ==============================================================================
# // KCC CLASSSTAMP - SELF-SERVICE PASSWORD RESET
# // ==============================================================================
# // Subsystem: Account Recovery
# // Description:
# //   Until now "Forgot password?" was a browser alert telling the user to walk to
# //   the registrar. This service issues a signed, time-limited reset link instead.
# //
# //   Design notes:
# //     - The token embeds a digest of the current password hash, so it stops
# //       working the moment the password changes (single use, no extra table).
# //     - Requesting a reset never reveals whether an account exists: the view
# //       shows the same answer either way.
# //     - A completed reset revokes every active session for that account.
# //     - Two-factor is NOT bypassed: after a reset the login still asks for the
# //       authenticator or a recovery code. A password reset must not become a
# //       way around the second factor.
# // References: apps/core/services/credential_service.py | docs/02_SECURITY.md
# // ==============================================================================
"""

import hashlib
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone

from apps.core.models import AuditEvent, Profile
from apps.core.services.credential_service import revoke_user_sessions

User = get_user_model()

RESET_SALT = 'classstamp-password-reset'
RESET_TOKEN_MAX_AGE = 1800  # 30 minutes


def _password_fingerprint(user) -> str:
    """Short digest of the current password hash; changes when the password does."""
    return hashlib.sha256((user.password or '').encode('utf-8')).hexdigest()[:16]


def make_reset_token(user) -> str:
    return signing.dumps(
        {'uid': user.pk, 'fp': _password_fingerprint(user)},
        salt=RESET_SALT,
        compress=True,
    )


def read_reset_token(token):
    """
    // Return the matching User for a token, or None when it is invalid, expired,
    // or already spent (password changed since the link was issued).
    """
    try:
        payload = signing.loads(token, salt=RESET_SALT, max_age=RESET_TOKEN_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired):
        return None

    user = User.objects.filter(pk=payload.get('uid')).select_related('classstamp_profile').first()
    if user is None or not user.is_active:
        return None
    if payload.get('fp') != _password_fingerprint(user):
        return None
    return user


def find_account(identifier: str):
    """Resolve a username, email or student number to a user (or None)."""
    identifier = (identifier or '').strip()
    if not identifier:
        return None

    user = User.objects.filter(username__iexact=identifier).first()
    if user:
        return user
    user = User.objects.filter(email__iexact=identifier).first()
    if user:
        return user

    profile = (
        Profile.objects.filter(student_number__iexact=identifier, role=Profile.ROLE_STUDENT)
        .select_related('user')
        .first()
    )
    return profile.user if profile else None


def request_reset(identifier: str, request=None) -> bool:
    """
    // Issue and email a reset link. Returns True when a link was sent.
    // The caller must not expose this boolean to the browser.
    """
    user = find_account(identifier)
    if user is None or not user.email:
        return False

    token = make_reset_token(user)
    path = f'/password-reset/{quote(token, safe="")}/'
    base = request.build_absolute_uri('/')[:-1] if request is not None else ''
    link = f'{base}{path}'

    display = user.get_full_name() or user.get_username()
    # Deliberately not fail_silently: a wrong SMTP password must leave a trace in
    # the server log and the audit trail, not just a student who never got a link.
    delivered = True
    try:
        send_mail(
            '[KCC ClassStamp] Password reset link',
            (
                f'Hello {display},\n\n'
                f'Someone asked to reset the password for this account. If that was you, '
                f'open the link below within 30 minutes:\n\n{link}\n\n'
                f'If you did not request this, ignore this message — your password stays '
                f'unchanged, and the link expires on its own.\n\n'
                f'— KCC ClassStamp Security'
            ),
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@classstamp.local'),
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:
        delivered = False
        logger.warning('Password reset email to %s failed: %s', user.email, exc)

    AuditEvent.objects.create(
        actor=None,
        action='PASSWORD_RESET_REQUESTED',
        object_type='User',
        object_id=str(user.pk),
        new_value=(
            f'Reset link emailed to {user.email}' if delivered
            else f'Reset link delivery FAILED for {user.email}'
        ),
        reason='Self-service password reset request',
    )
    return True


def reset_password(token: str, new_password: str):
    """
    // Complete a reset. Raises ValueError with a user-facing message on any
    // problem; returns the user on success.
    """
    user = read_reset_token(token)
    if user is None:
        raise ValueError('This reset link is invalid or has expired. Request a new one.')

    profile = getattr(user, 'classstamp_profile', None)
    try:
        validate_password(new_password, user)
    except ValidationError as exc:
        raise ValueError(' '.join(exc.messages))

    user.set_password(new_password)
    user.save(update_fields=['password'])

    revoked = revoke_user_sessions(user.pk)

    AuditEvent.objects.create(
        actor=None,
        action='PASSWORD_RESET_COMPLETED',
        object_type='User',
        object_id=str(user.pk),
        new_value=f'Password changed; {revoked} session(s) revoked',
        reason=(
            f'Self-service reset via emailed link'
            + (f' (account role: {profile.role})' if profile else '')
        ),
    )
    return user
