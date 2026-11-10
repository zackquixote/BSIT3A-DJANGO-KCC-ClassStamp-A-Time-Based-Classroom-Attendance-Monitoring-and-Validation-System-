"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT CREDENTIAL LIFECYCLE SERVICE
# // ==============================================================================
# // Subsystem: Identity & QR Credential Revocation
# // Description: Single source of truth for rotating a student's dynamic QR
# //   secret. Every entry point (profile editor, dedicated QR reset, scheduled
# //   rotation command, and future password-reset/deactivation flows) must use
# //   this service so that revocation is complete and consistent:
# //     - generates a fresh 64-char hex TOTP secret
# //     - stamps qr_rotated_at for the rotation policy
# //     - deletes every unconsumed offline badge derived from the old secret
# //     - writes an immutable AuditEvent
# //     - optionally invalidates the student's active login sessions
# // References: docs/02_SECURITY.md | apps/core/services/qr_service.py
# // ==============================================================================
"""

import secrets
import string

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditEvent, PasswordHistory, Profile

User = get_user_model()

# Task 1.7: reject reuse of the current password plus the last five hashes.
PASSWORD_HISTORY_DEPTH = 5


def generate_compliant_password(length: int = 14) -> str:
    """
    // Generate a password that always satisfies the composition policy:
    // at least one uppercase, lowercase, digit, and special character.
    """
    if length < 8:
        length = 8
    pools = [
        string.ascii_uppercase,
        string.ascii_lowercase,
        string.digits,
        string.punctuation,
    ]
    characters = [secrets.choice(pool) for pool in pools]
    alphabet = ''.join(pools)
    characters.extend(
        secrets.choice(alphabet) for _ in range(length - len(characters))
    )
    secrets.SystemRandom().shuffle(characters)
    return ''.join(characters)


def password_is_reused(user, raw_password: str) -> bool:
    """
    // True when raw_password matches the current hash or any of the last
    // PASSWORD_HISTORY_DEPTH stored hashes. Hashes only — never plaintext.
    """
    hashes = [user.password or '']
    hashes.extend(
        PasswordHistory.objects.filter(user=user)
        .order_by('-created_at')
        .values_list('password_hash', flat=True)[:PASSWORD_HISTORY_DEPTH]
    )
    return any(
        check_password(raw_password, stored)
        for stored in hashes
        if stored
    )


def record_password_history(user) -> None:
    """
    // Store the user's current password hash in history and prune entries
    // older than the retained five. Call after every successful set_password.
    """
    if not user.password:
        return
    PasswordHistory.objects.create(user=user, password_hash=user.password)
    stale = PasswordHistory.objects.filter(user=user).order_by('-created_at')
    for row in stale[PASSWORD_HISTORY_DEPTH:]:
        row.delete()


def set_user_password(
    user,
    raw_password: str,
    *,
    validate: bool = True,
    actor=None,
    audit_action: str = 'PASSWORD_CHANGED',
    revoke_sessions: bool = False,
    reason: str = '',
):
    """
    // Single entry point for changing an existing account's password.
    //
    // Validates composition/policy, rejects reuse of the current password or
    // the last five hashes, writes the new hash, records history, prunes,
    // audits, and optionally revokes sessions.
    //
    // Raises ValueError with a user-facing message on policy failure.
    """
    if validate:
        try:
            validate_password(raw_password, user)
        except ValidationError as exc:
            raise ValueError(' '.join(exc.messages)) from exc

    if password_is_reused(user, raw_password):
        raise ValueError(
            'You cannot reuse your current password or any of your last '
            f'{PASSWORD_HISTORY_DEPTH} passwords.'
        )

    user.set_password(raw_password)
    user.save(update_fields=['password'])
    record_password_history(user)

    AuditEvent.objects.create(
        actor=actor,
        action=audit_action,
        object_type='User',
        object_id=str(user.pk),
        reason=reason or f'Password changed for {user.username}',
    )

    revoked = 0
    if revoke_sessions:
        revoked = revoke_user_sessions(user.pk)
    return {'user': user, 'revoked_sessions': revoked}


def revoke_user_sessions(user_id) -> int:
    """
    // Delete every active Django session belonging to a user account.
    // Used when a credential reset must also terminate authenticated access.
    // Returns the number of sessions removed.
    """
    removed = 0
    now = timezone.now()
    for session in Session.objects.filter(expire_date__gte=now).iterator():
        try:
            data = session.get_decoded()
        except Exception:
            continue
        if str(data.get('_auth_user_id')) == str(user_id):
            session.delete()
            removed += 1
    return removed


def rotate_student_credentials(
    profile,
    *,
    actor=None,
    reason='',
    audit_action='STUDENT_QR_RESET',
    revoke_sessions=False,
):
    """
    // [Service] Atomically rotate a student's QR credential and revoke all
    // outstanding offline badges derived from the previous secret.
    //
    // Arguments:
    //   profile         — Profile instance (must be a STUDENT).
    //   actor           — User performing the reset, or None for automation.
    //   reason          — Human-readable audit reason.
    //   audit_action    — AuditEvent action keyword (default STUDENT_QR_RESET).
    //   revoke_sessions — Also terminate the student's active login sessions.
    //
    // Returns:
    //   dict with rotated_at, old_secret_preview, revoked_offline_badges,
    //   and revoked_sessions.
    //
    // Raises:
    //   ValueError when the supplied profile is not a student.
    """
    if profile is None or profile.role != Profile.ROLE_STUDENT:
        raise ValueError('QR credentials can only be rotated for student profiles.')

    now = timezone.now()

    with transaction.atomic():
        locked = Profile.objects.select_for_update().get(pk=profile.pk)
        old_preview = f'...{locked.qr_secret[-8:]}' if locked.qr_secret else 'None'

        locked.qr_secret = secrets.token_hex(32)  # 32 bytes = 64 hex chars
        locked.qr_rotated_at = now
        locked.save(update_fields=['qr_secret', 'qr_rotated_at', 'updated_at'])

        pending_badges = locked.offline_badges.filter(consumed_at__isnull=True)
        revoked_badges = pending_badges.count()
        pending_badges.delete()

        AuditEvent.objects.create(
            actor=actor,
            action=audit_action,
            object_type='Profile',
            object_id=str(locked.pk),
            old_value=f'Seed rotated from {old_preview}',
            new_value=(
                f'New 64-char seed provisioned at {now.isoformat()}; '
                f'{revoked_badges} unconsumed offline badge(s) revoked'
            ),
            reason=reason or 'Student QR credential rotation',
        )

    # Keep the caller's in-memory instance consistent with the database row.
    profile.qr_secret = locked.qr_secret
    profile.qr_rotated_at = now

    revoked_sessions = 0
    if revoke_sessions:
        revoked_sessions = revoke_user_sessions(locked.user_id)

    return {
        'rotated_at': now,
        'old_secret_preview': old_preview,
        'revoked_offline_badges': revoked_badges,
        'revoked_sessions': revoked_sessions,
    }
