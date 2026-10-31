"""
// ==============================================================================
// KCC CLASSSTAMP - EXCUSE SLIP WORKFLOW CONTROLLERS (S-08)
// ==============================================================================
// Subsystem: Attendance Exception Management (RBAC: STUDENT submit, TEACHER review)
// Description:
//   - Students file online excuse slips against ABSENT attendance records.
//   - Instructors approve (absence converts to EXCUSED) or reject with a note.
//   - Every transition emits an immutable AuditEvent.
// ==============================================================================
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import approved_required, role_required
from apps.core.models import (
    AttendanceRecord,
    AuditEvent,
    ExcuseSlip,
    Profile,
)
from apps.core.validators import validate_uploaded_document


def _can_review_excuse(request, class_obj) -> bool:
    """
    // Object-level authorization: only the assigned instructor, an ADMIN, or a
    // superuser may adjudicate excuse slips for a class section.
    """
    if request.user.is_superuser:
        return True
    profile = getattr(request.user, 'classstamp_profile', None)
    if profile is None:
        return False
    if profile.role == Profile.ROLE_ADMIN:
        return True
    return (
        profile.role == Profile.ROLE_TEACHER
        and class_obj.teacher_profile_id == profile.id
    )


# // ==============================================================================
# // VIEW: Student Excuse Slips (/student/excuse-slips/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_excuse_slips(request):
    """
    // [Student Controller] Lists ABSENT sessions eligible for excuse filing,
    // plus the student's own slip history with review outcomes.
    """
    profile = getattr(request.user, 'classstamp_profile', None)

    if request.method == 'POST':
        session_id = request.POST.get('session_id', '').strip()
        reason = request.POST.get('reason', '').strip()
        if not session_id or not reason:
            messages.error(request, 'A reason is required to file an excuse slip.')
            return redirect('student_excuse_slips')

        try:
            session_id = int(session_id)
        except ValueError:
            messages.error(request, 'Invalid session selected.')
            return redirect('student_excuse_slips')

        record = AttendanceRecord.objects.filter(
            student_profile=profile,
            session_id=session_id,
            status=AttendanceRecord.STATUS_ABSENT,
        ).select_related('session').first()

        if not record:
            messages.error(request, 'That session is not an absently-marked meeting for you.')
            return redirect('student_excuse_slips')

        attachment = request.FILES.get('attachment')
        if attachment is not None:
            try:
                validate_uploaded_document(attachment)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
                return redirect('student_excuse_slips')

        slip = ExcuseSlip(
            student_profile=profile,
            session=record.session,
            reason=reason,
            attachment=attachment,
        )
        try:
            with transaction.atomic():
                slip.save()
                AuditEvent.objects.create(
                    actor=request.user,
                    action='EXCUSE_SUBMITTED',
                    object_type='ExcuseSlip',
                    object_id=str(slip.pk),
                    new_value=(
                        f'{profile.student_number} filed excuse for '
                        f'{record.session.slot.class_obj.class_code} on '
                        f'{record.session.session_date}'
                    ),
                )
        except IntegrityError:
            messages.error(request, 'An excuse slip already exists for that session.')
            return redirect('student_excuse_slips')

        messages.success(request, 'Excuse slip submitted and routed to your instructor for review.')
        return redirect('student_excuse_slips')

    absent_records = (
        AttendanceRecord.objects.filter(
            student_profile=profile,
            status=AttendanceRecord.STATUS_ABSENT,
        )
        .select_related('session', 'session__slot', 'session__slot__class_obj', 'session__slot__class_obj__subject')
        .order_by('-session__session_date')
    )

    existing_session_ids = set(
        ExcuseSlip.objects.filter(student_profile=profile).values_list('session_id', flat=True)
    )
    fileable_records = [r for r in absent_records if r.session_id not in existing_session_ids]

    slips = (
        ExcuseSlip.objects.filter(student_profile=profile)
        .select_related('session', 'session__slot', 'session__slot__class_obj', 'session__slot__class_obj__subject', 'reviewed_by')
        .order_by('-created_at')
    )

    return render(request, 'core/student/excuse_slips.html', {
        'fileable_records': fileable_records,
        'slips': slips,
    })


# // ==============================================================================
# // VIEW: Instructor Excuse Slip Review Queue (/teacher/excuse-slips/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
def teacher_excuse_slips(request):
    """
    // [Teacher Controller] Review queue of excuse slips for classes the
    // instructor teaches (admins see the institutional-wide queue).
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    qs = (
        ExcuseSlip.objects
        .select_related(
            'student_profile',
            'student_profile__user',
            'student_profile__program',
            'session',
            'session__slot',
            'session__slot__class_obj',
            'session__slot__class_obj__subject',
            'reviewed_by',
        )
        .order_by('-created_at')
    )

    if not (request.user.is_superuser or (profile and profile.role == Profile.ROLE_ADMIN)):
        qs = qs.filter(session__slot__class_obj__teacher_profile=profile)

    pending_slips = [s for s in qs if s.status == ExcuseSlip.STATUS_PENDING]
    resolved_slips = [s for s in qs if s.status != ExcuseSlip.STATUS_PENDING]

    return render(request, 'core/teacher/excuse_slips.html', {
        'pending_slips': pending_slips,
        'resolved_slips': resolved_slips,
    })


# // ==============================================================================
# // AJAX: Adjudicate Excuse Slip (/teacher/excuse-slips/<pk>/review/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def excuse_slip_review_ajax(request, slip_id):
    """
    // [AJAX Mutation] Approve or reject a pending excuse slip.
    // POST params: action ('approve' | 'reject'), note
    // Approve: attendance record becomes EXCUSED (upserted).
    // Reject: slip closes with a mandatory instructor note.
    """
    slip = get_object_or_404(
        ExcuseSlip.objects.select_related(
            'session',
            'session__slot',
            'session__slot__class_obj',
            'student_profile',
            'student_profile__user',
        ),
        pk=slip_id,
    )
    class_obj = slip.session.slot.class_obj

    if not _can_review_excuse(request, class_obj):
        return JsonResponse({'ok': False, 'error': 'You are not authorized to review this excuse slip.'}, status=403)

    if slip.status != ExcuseSlip.STATUS_PENDING:
        return JsonResponse({'ok': False, 'error': 'This excuse slip has already been reviewed.'}, status=400)

    action = request.POST.get('action', '').strip()
    note = request.POST.get('note', '').strip()

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
                    'marked_by': request.user,
                },
            )
            if not created:
                record.status = AttendanceRecord.STATUS_EXCUSED
                record.method = AttendanceRecord.METHOD_MANUAL
                record.late_minutes = 0
                record.correction_reason = f'Excuse slip approved: {slip.reason[:200]}'
                record.marked_by = request.user
                record.save()

            slip.status = ExcuseSlip.STATUS_APPROVED
            slip.review_note = note or None
            slip.reviewed_by = request.user
            slip.reviewed_at = timezone.now()
            slip.save()

            AuditEvent.objects.create(
                actor=request.user,
                action='EXCUSE_APPROVED',
                object_type='ExcuseSlip',
                object_id=str(slip.pk),
                old_value=f'ABSENT -> EXCUSED for {slip.student_profile.student_number}',
                new_value=f'Approved: {class_obj.class_code} on {slip.session.session_date}',
            )
        return JsonResponse({'ok': True, 'message': 'Excuse slip approved — attendance marked EXCUSED.'})

    if action == 'reject':
        if not note:
            return JsonResponse({'ok': False, 'error': 'A review note is required when rejecting a slip.'}, status=400)

        slip.status = ExcuseSlip.STATUS_REJECTED
        slip.review_note = note
        slip.reviewed_by = request.user
        slip.reviewed_at = timezone.now()
        slip.save()

        AuditEvent.objects.create(
            actor=request.user,
            action='EXCUSE_REJECTED',
            object_type='ExcuseSlip',
            object_id=str(slip.pk),
            old_value=f'ABSENT kept for {slip.student_profile.student_number}',
            new_value=f'Rejected: {note[:200]}',
        )
        return JsonResponse({'ok': True, 'message': 'Excuse slip rejected.'})

    return JsonResponse({'ok': False, 'error': 'Invalid action.'}, status=400)
