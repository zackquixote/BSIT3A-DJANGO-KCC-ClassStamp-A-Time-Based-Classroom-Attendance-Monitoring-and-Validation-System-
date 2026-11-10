"""
# // ==============================================================================
# // KCC CLASSSTAMP - EXCUSE SLIP REVIEW SERVICE
# // ==============================================================================
# // Subsystem: Excuse slip adjudication (tasks 4.5 / 4.6 — Req 13)
# // Description:
# //   One shared status transition for single-slip review and bulk approval:
# //   attendance-record correction, slip status, AuditEvent, and the student
# //   notification. The single-review view keeps its endpoint behavior and
# //   calls this operation; the bulk endpoint calls it once per selected slip
# //   so one failure does not prevent the remaining valid approvals.
# // ==============================================================================
"""

from django.db import transaction
from django.utils import timezone

from apps.core.models import AttendanceRecord, AuditEvent, ExcuseSlip
from apps.core.services.notification_service import notify_excuse_decision
from apps.core.services.permission_service import PermissionService


def review_excuse_slip(*, actor, slip, action, note=''):
    """
    // Approve or reject one pending excuse slip.
    //
    // Returns a result dict instead of raising so bulk processing can skip
    // a failed slip and continue:
    //   {'ok': True, 'message': ...}
    //   {'ok': False, 'error': 'not_authorized'|'already_reviewed'|
    //                          'note_required'|'invalid_action', 'message': ...}
    //
    // Permission is re-checked here (not inferred from a selected ID) so the
    // bulk path cannot approve slips the actor does not own.
    """
    class_obj = slip.session.slot.class_obj

    if not PermissionService.can_user_approve_excuse(actor, slip):
        return {
            'ok': False,
            'error': 'not_authorized',
            'message': 'You are not authorized to review this excuse slip.',
        }

    if slip.status != ExcuseSlip.STATUS_PENDING:
        return {
            'ok': False,
            'error': 'already_reviewed',
            'message': 'This excuse slip has already been reviewed.',
        }

    if action == 'approve':
        with transaction.atomic():
            record, created = AttendanceRecord.objects.get_or_create(
                session=slip.session,
                student_profile=slip.student_profile,
                defaults={
                    'status': AttendanceRecord.STATUS_EXCUSED,
                    'method': AttendanceRecord.METHOD_MANUAL,
                    'stamped_at': timezone.now(),
                    'late_minutes': 0,
                    'correction_reason': f'Excuse slip approved: {slip.reason[:200]}',
                    'marked_by': actor,
                },
            )
            if not created:
                record.status = AttendanceRecord.STATUS_EXCUSED
                record.method = AttendanceRecord.METHOD_MANUAL
                record.late_minutes = 0
                record.correction_reason = f'Excuse slip approved: {slip.reason[:200]}'
                record.marked_by = actor
                record.save()

            slip.status = ExcuseSlip.STATUS_APPROVED
            slip.review_note = note or None
            slip.reviewed_by = actor
            slip.reviewed_at = timezone.now()
            slip.save()

            AuditEvent.objects.create(
                actor=actor,
                action='EXCUSE_APPROVED',
                object_type='ExcuseSlip',
                object_id=str(slip.pk),
                old_value=f'ABSENT -> EXCUSED for {slip.student_profile.student_number}',
                new_value=f'Approved: {class_obj.class_code} on {slip.session.session_date}',
            )
            notify_excuse_decision(slip, approved=True, note=note)
        return {
            'ok': True,
            'message': 'Excuse slip approved — attendance marked EXCUSED.',
        }

    if action == 'reject':
        if not (note or '').strip():
            return {
                'ok': False,
                'error': 'note_required',
                'message': 'A review note is required when rejecting a slip.',
            }

        slip.status = ExcuseSlip.STATUS_REJECTED
        slip.review_note = note
        slip.reviewed_by = actor
        slip.reviewed_at = timezone.now()
        slip.save()

        AuditEvent.objects.create(
            actor=actor,
            action='EXCUSE_REJECTED',
            object_type='ExcuseSlip',
            object_id=str(slip.pk),
            old_value=f'ABSENT kept for {slip.student_profile.student_number}',
            new_value=f'Rejected: {note[:200]}',
        )
        notify_excuse_decision(slip, approved=False, note=note)
        return {
            'ok': True,
            'message': 'Excuse slip rejected.',
        }

    return {
        'ok': False,
        'error': 'invalid_action',
        'message': 'Invalid action.',
    }
