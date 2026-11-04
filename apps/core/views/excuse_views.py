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

from datetime import timedelta

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
    AttendanceDispute,
    AttendanceRecord,
    AuditEvent,
    ClassSession,
    Enrollment,
    ExcuseSlip,
    Profile,
)
from apps.core.services.notification_service import notify_excuse_decision
from apps.core.services.in_app_notification_service import create_notification
from apps.core.validators import validate_uploaded_document

# A student can file ahead of a meeting (medical appointment known in advance) or
# after it. The windows keep the queue meaningful without letting anyone excuse a
# meeting from a term that has already closed.
EXCUSE_ADVANCE_DAYS = 14
EXCUSE_BACKFILL_DAYS = 30


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

        session = (
            ClassSession.objects
            .select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')
            .filter(pk=session_id)
            .first()
        )
        if session is None:
            messages.error(request, 'That class meeting could not be found.')
            return redirect('student_excuse_slips')

        # Only a meeting the student is actually enrolled in can be excused.
        enrolled = Enrollment.objects.filter(
            student_profile=profile,
            class_obj=session.slot.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        ).exists()
        if not enrolled:
            messages.error(request, 'You are not enrolled in that class section.')
            return redirect('student_excuse_slips')

        today = timezone.localdate()
        earliest = today - timedelta(days=EXCUSE_BACKFILL_DAYS)
        latest = today + timedelta(days=EXCUSE_ADVANCE_DAYS)
        if not (earliest <= session.session_date <= latest):
            messages.error(
                request,
                f'Excuse slips can be filed for meetings between {earliest:%b %d, %Y} '
                f'and {latest:%b %d, %Y}.',
            )
            return redirect('student_excuse_slips')

        if ExcuseSlip.objects.filter(student_profile=profile, session=session).exists():
            messages.error(request, 'An excuse slip already exists for that session.')
            return redirect('student_excuse_slips')

        # Only an absence (recorded or still to come) can be excused. A meeting
        # already marked PRESENT/LATE/EXCUSED has nothing left to justify, and
        # approving it would quietly downgrade the student's own record.
        existing_record = (
            AttendanceRecord.objects.filter(student_profile=profile, session=session)
            .only('status')
            .first()
        )
        if existing_record and existing_record.status != AttendanceRecord.STATUS_ABSENT:
            messages.error(
                request,
                f'That meeting is already recorded as {existing_record.get_status_display().upper()}; '
                f'only an absence can be excused.',
            )
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
            session=session,
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
                        f'{session.slot.class_obj.class_code} on '
                        f'{session.session_date}'
                    ),
                )
                class_obj = session.slot.class_obj
                if class_obj.teacher_profile_id:
                    create_notification(
                        class_obj.teacher_profile.user,
                        'excuse_slip',
                        'New excuse slip submitted',
                        (
                            f'{profile.user.get_full_name() or profile.student_number} '
                            f'submitted an excuse slip for {class_obj.class_code} '
                            f'on {session.session_date}.'
                        ),
                        '/teacher/excuse-slips/',
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

    # Meetings that have not happened yet (or happen today) in the classes this
    # student is enrolled in. Lets a known-in-advance absence be filed before the
    # instructor has to mark it ABSENT.
    today = timezone.localdate()
    upcoming_sessions = (
        ClassSession.objects.filter(
            slot__class_obj__enrollments__student_profile=profile,
            slot__class_obj__enrollments__status=Enrollment.STATUS_ACTIVE,
            session_date__gte=today,
            session_date__lte=today + timedelta(days=EXCUSE_ADVANCE_DAYS),
        )
        .exclude(status=ClassSession.STATUS_CANCELED)
        .exclude(pk__in=existing_session_ids)
        .select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')
        .distinct()
        .order_by('session_date', 'slot__starts_at')
    )

    slips = (
        ExcuseSlip.objects.filter(student_profile=profile)
        .select_related('session', 'session__slot', 'session__slot__class_obj', 'session__slot__class_obj__subject', 'reviewed_by')
        .order_by('-created_at')
    )

    return render(request, 'core/student/excuse_slips.html', {
        'fileable_records': fileable_records,
        'upcoming_sessions': upcoming_sessions,
        'advance_days': EXCUSE_ADVANCE_DAYS,
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

    disputes_qs = (
        AttendanceDispute.objects
        .filter(status=AttendanceDispute.STATUS_PENDING)
        .select_related(
            'record', 'record__session', 'record__session__slot',
            'record__session__slot__class_obj', 'record__session__slot__class_obj__subject',
            'student_profile', 'student_profile__user',
        )
        .order_by('-created_at')
    )
    if not (request.user.is_superuser or (profile and profile.role == Profile.ROLE_ADMIN)):
        disputes_qs = disputes_qs.filter(
            record__session__slot__class_obj__teacher_profile=profile
        )

    return render(request, 'core/teacher/excuse_slips.html', {
        'pending_slips': pending_slips,
        'resolved_slips': resolved_slips,
        'pending_disputes': disputes_qs,
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
            notify_excuse_decision(slip, approved=True, note=note)
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
        notify_excuse_decision(slip, approved=False, note=note)
        return JsonResponse({'ok': True, 'message': 'Excuse slip rejected.'})

    return JsonResponse({'ok': False, 'error': 'Invalid action.'}, status=400)


# // ==============================================================================
# // ACTION: Resolve an Attendance Dispute (/teacher/disputes/<id>/resolve/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def dispute_resolve(request, dispute_id):
    """
    // Uphold the recorded status, or correct it to what actually happened.
    // A correction rewrites the record and is audited with the instructor's note.
    """
    dispute = get_object_or_404(
        AttendanceDispute.objects.select_related(
            'record', 'record__session', 'record__session__slot',
            'record__session__slot__class_obj', 'student_profile__user',
        ),
        pk=dispute_id,
    )
    class_obj = dispute.record.session.slot.class_obj
    if not _can_review_excuse(request, class_obj):
        messages.error(request, 'You can only review disputes for your own class sections.')
        return redirect('teacher_excuse_slips')

    if dispute.status != AttendanceDispute.STATUS_PENDING:
        messages.error(request, 'That dispute has already been resolved.')
        return redirect('teacher_excuse_slips')

    action = request.POST.get('action', '').strip()
    note = request.POST.get('note', '').strip()

    if action not in ('uphold', 'correct'):
        messages.error(request, 'Choose whether to uphold or correct the record.')
        return redirect('teacher_excuse_slips')

    with transaction.atomic():
        if action == 'uphold':
            dispute.status = AttendanceDispute.STATUS_UPHELD
            outcome = 'upheld'
        else:
            new_status = request.POST.get('status', '').strip().upper()
            if new_status not in (
                AttendanceRecord.STATUS_PRESENT,
                AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_EXCUSED,
            ):
                messages.error(request, 'Pick the corrected status.')
                return redirect('teacher_excuse_slips')

            record = dispute.record
            previous = record.status
            record.status = new_status
            record.method = AttendanceRecord.METHOD_MANUAL
            record.marked_by = request.user
            record.correction_reason = f'Dispute #{dispute.pk} corrected from {previous}: {note or "no note"}'
            record.save(update_fields=['status', 'method', 'marked_by', 'correction_reason', 'updated_at'])
            dispute.status = AttendanceDispute.STATUS_CORRECTED
            outcome = f'corrected to {new_status}'

        dispute.resolution_note = note or None
        dispute.resolved_by = request.user
        dispute.resolved_at = timezone.now()
        dispute.save(update_fields=['status', 'resolution_note', 'resolved_by', 'resolved_at'])

        AuditEvent.objects.create(
            actor=request.user,
            action='ATTENDANCE_DISPUTE_RESOLVED',
            object_type='AttendanceDispute',
            object_id=str(dispute.pk),
            new_value=outcome,
            reason=note or 'No note provided',
        )

    create_notification(
        dispute.student_profile.user,
        'attendance_dispute',
        'Attendance dispute resolved',
        f'Your dispute for {class_obj.class_code} on {dispute.record.session.session_date} was {outcome}.',
        '/student/attendance/',
    )
    messages.success(request, f'Dispute {outcome}.')
    return redirect('teacher_excuse_slips')
