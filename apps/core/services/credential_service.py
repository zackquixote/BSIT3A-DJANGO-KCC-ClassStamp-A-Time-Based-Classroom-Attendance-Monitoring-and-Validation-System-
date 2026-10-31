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

from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditEvent, Profile


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
