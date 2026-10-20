"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT ACCOUNT APPROVAL SERVICE
# // ==============================================================================
# // Subsystem: Admin Validation Workflow Business Logic
# // Description: Encapsulates the approve/reject decision pipeline for student
# //   account registrations. Extracted from validation_views.py so the workflow
# //   can be reused by batch operations, API endpoints, or management commands.
# //
# // Live DB Trigger Contracts Satisfied:
# //   trg_cs_profile_bu:
# //     - Only an ADMIN user may set approved_by (enforced at application layer).
# //     - approved_at must be set when approval_status changes from PENDING.
# //   chk_cs_profile_shape:
# //     - An APPROVED student must have a 64-character qr_secret.
# //   AuditEvent:
# //     - Every approve/reject action emits an immutable APPROVE_STUDENT /
# //       REJECT_STUDENT event with actor, timestamp, and snapshot.
# // ==============================================================================
"""

import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.core.models import AuditEvent, Profile

logger = logging.getLogger(__name__)


def _send_validation_email(profile: Profile, approved: bool, reason: str = ''):
    """
    // [Notification] Transactional email alert dispatched upon registration approval or rejection (#17).
    // Fails silently if SMTP is unreachable so core DB transactions never fail.
    """
    user = getattr(profile, 'user', None)
    if not user or not user.email:
        return

    student_name = user.get_full_name() or user.username
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@classstamp.local')

    if approved:
        subject = f'[KCC ClassStamp] Account Approved — {profile.student_number}'
        message = (
            f"Hello {student_name},\n\n"
            f"Your student registration account for KCC ClassStamp has been approved!\n"
            f"Student Number: {profile.student_number}\n\n"
            f"You can now sign in to your dashboard to generate dynamic attendance QR stamps "
            f"and monitor your classroom attendance records.\n\n"
            f"— KCC ClassStamp Registrar & Administrative Services"
        )
    else:
        subject = f'[KCC ClassStamp] Registration Status Notice — {profile.student_number}'
        message = (
            f"Hello {student_name},\n\n"
            f"Your student registration account for KCC ClassStamp has been evaluated.\n"
            f"Status: REJECTED\n"
            f"Reason: {reason}\n\n"
            f"If you believe this was in error, please correct your submitted documents "
            f"or visit the Registrar's Office for assistance.\n\n"
            f"— KCC ClassStamp Registrar & Administrative Services"
        )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning('Failed to dispatch validation email to %s: %s', user.email, exc)


def approve_student_registration(profile: Profile, actor) -> Profile:
    """
    // [Service] Approve Student Registration
    // Transitions the student profile from PENDING → APPROVED and provisions a
    // fresh 64-char QR TOTP secret. Emits an immutable AuditEvent.
    //
    // Arguments:
    //   profile (Profile): The student Profile to approve (must be PENDING).
    //   actor   (User):    The admin User performing the approval action.
    //
    // Returns:
    //   Updated Profile instance (already saved).
    //
    // Raises:
    //   ValueError — if the profile is not in PENDING status.
    """
    if profile.approval_status != Profile.APPROVAL_PENDING:
        raise ValueError(
            f'Profile {profile.pk} is not PENDING (current: {profile.approval_status}).'
        )

    # // [Decision Fields] satisfy trg_cs_profile_bu contract
    profile.approval_status = Profile.APPROVAL_APPROVED
    profile.approved_by = actor
    profile.approved_at = timezone.now()
    profile.approval_note = None

    # // [Cryptographic QR Seed Rotation]
    # // Generates a fresh 64-char hex secret for dynamic QR attendance stamping.
    profile.qr_secret = secrets.token_hex(32)
    profile.qr_rotated_at = timezone.now()
    profile.save()

    # // [Immutable Audit Logging]
    AuditEvent.objects.create(
        actor=actor,
        action='APPROVE_STUDENT',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'Approved {profile.student_number} ({profile.user.get_username()})',
    )

    # // [Transactional Email Notification (#17)]
    _send_validation_email(profile, approved=True)

    return profile


def reject_student_registration(profile: Profile, actor, reason: str) -> Profile:
    """
    // [Service] Reject Student Registration
    // Transitions the student profile from PENDING → REJECTED with a mandatory
    // non-empty reason (enforced by DB trigger approval_note constraint).
    // Emits an immutable AuditEvent.
    //
    // Arguments:
    //   profile (Profile): The student Profile to reject (must be PENDING).
    //   actor   (User):    The admin User performing the rejection.
    //   reason  (str):     Non-empty rejection justification stored in approval_note.
    //
    // Returns:
    //   Updated Profile instance (already saved).
    //
    // Raises:
    //   ValueError — if the profile is not PENDING, or if reason is empty.
    """
    if profile.approval_status != Profile.APPROVAL_PENDING:
        raise ValueError(
            f'Profile {profile.pk} is not PENDING (current: {profile.approval_status}).'
        )

    if not reason or not reason.strip():
        raise ValueError('A non-empty rejection reason is required.')

    # // [Decision Fields] satisfy trg_cs_profile_bu contract
    profile.approval_status = Profile.APPROVAL_REJECTED
    profile.approved_by = actor
    profile.approved_at = timezone.now()
    profile.approval_note = reason.strip()
    profile.save()

    # // [Immutable Audit Logging]
    AuditEvent.objects.create(
        actor=actor,
        action='REJECT_STUDENT',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'Rejected {profile.student_number} ({profile.user.get_username()})',
        reason=reason.strip(),
    )

    # // [Transactional Email Notification (#17)]
    _send_validation_email(profile, approved=False, reason=reason.strip())

    return profile
