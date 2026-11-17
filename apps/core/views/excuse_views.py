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

from datetime import date, timedelta

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
    ClassSlot,
    Enrollment,
    ExcuseSlip,
    Profile,
)
from apps.core.services.excuse_service import review_excuse_slip
from apps.core.services.permission_service import PermissionService
from apps.core.services.notification_service import notify_excuse_decision
from apps.core.services.in_app_notification_service import create_notification
from apps.core.validators import validate_uploaded_document

# A student can file ahead of a meeting (medical appointment known in advance) or
# after it. The windows keep the queue meaningful without letting anyone excuse a
# meeting from a term that has already closed.
EXCUSE_ADVANCE_DAYS = 14
EXCUSE_BACKFILL_DAYS = 30


def _upcoming_excuse_occurrences(profile, *, today, advance_days):
    """
    // The weekly timetable is the source of truth for "file ahead": a slot
    // already defines the weekday and time, so the next meeting dates can be
    // offered even before the instructor has created a ClassSession row.
    // Existing make-up sessions are merged in, and anything already marked or
    // already excused is skipped.
    """
    window_end = today + timedelta(days=advance_days)
    slots = list(
        ClassSlot.objects.filter(
            class_obj__enrollments__student_profile=profile,
            class_obj__enrollments__status=Enrollment.STATUS_ACTIVE,
            class_obj__is_active=True,
            class_obj__academic_year__is_active=True,
            is_active=True,
        )
        .select_related('class_obj', 'class_obj__subject')
        .distinct()
    )
    if not slots:
        return []

    slot_ids = [slot.pk for slot in slots]
    sessions = {
        (session.slot_id, session.session_date): session
        for session in ClassSession.objects.filter(
            slot_id__in=slot_ids,
            session_date__gte=today,
            session_date__lte=window_end,
        ).select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')
    }

    blocked_session_ids = set(
        ExcuseSlip.objects.filter(student_profile=profile)
        .values_list('session_id', flat=True)
    )
    if sessions:
        blocked_session_ids.update(
            AttendanceRecord.objects.filter(
                student_profile=profile,
                session_id__in=[session.pk for session in sessions.values()],
            ).values_list('session_id', flat=True)
        )

    occurrences = []
    now_time = timezone.localtime().time()
    for slot in slots:
        first_date = today + timedelta(days=(slot.weekday - today.weekday()) % 7)
        for week in range(0, advance_days + 1, 7):
            session_date = first_date + timedelta(days=week)
            if session_date < today or session_date > window_end:
                continue
            session = sessions.get((slot.pk, session_date))
            if session is not None:
                if session.status == ClassSession.STATUS_CANCELED:
                    continue
                if session.pk in blocked_session_ids:
                    continue
            elif session_date == today and slot.ends_at and slot.ends_at < now_time:
                # Today's meeting already ended; the ABSENT-record flow is the
                # right entry point for it, not an advance excuse.
                continue
            occurrences.append({
                'slot': slot,
                'class_obj': slot.class_obj,
                'session_date': session_date,
                'starts_at': slot.starts_at,
                'ends_at': slot.ends_at,
                'session': session,
            })

    # Make-up sessions can sit on a date the weekly slot does not normally meet.
    seen = {(row['slot'].pk, row['session_date']) for row in occurrences}
    for (slot_id, session_date), session in sessions.items():
        if (slot_id, session_date) in seen:
            continue
        if session.status == ClassSession.STATUS_CANCELED:
            continue
        if session.pk in blocked_session_ids:
            continue
        slot = session.slot
        occurrences.append({
            'slot': slot,
            'class_obj': slot.class_obj,
            'session_date': session_date,
            'starts_at': slot.starts_at,
            'ends_at': slot.ends_at,
            'session': session,
        })

    occurrences.sort(
        key=lambda row: (row['session_date'], row['starts_at'], row['class_obj'].class_code)
    )
    return occurrences


def _can_review_excuse(request, class_obj) -> bool:
    """
    // Object-level authorization: only the assigned instructor, an ADMIN, or a
    // superuser may adjudicate excuse slips for a class section.
    //
    // Kept as a thin adapter for dispute_resolve, which holds an
    // AttendanceDispute rather than an ExcuseSlip. Single-slip review now
    // calls PermissionService.can_user_approve_excuse directly.
    """
    if request.user.is_superuser:
        return True
    return PermissionService.can_user_access_class(request.user, class_obj)


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
        reason = request.POST.get('reason', '').strip()
        session_id = request.POST.get('session_id', '').strip()
        occurrence = request.POST.get('occurrence', '').strip()
        if not reason:
            messages.error(request, 'A reason is required to file an excuse slip.')
            return redirect('student_excuse_slips')

        session = None
        if session_id:
            try:
                session_id = int(session_id)
            except (TypeError, ValueError):
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
        elif occurrence:
            # The file-ahead form sends "slot_id|YYYY-MM-DD". Materialize the
            # session if the instructor has not opened it yet, so the slip has
            # the same anchor as an attendance session.
            try:
                slot_id, date_value = occurrence.split('|', 1)
                slot_id = int(slot_id)
                session_date = date.fromisoformat(date_value)
            except (TypeError, ValueError):
                messages.error(request, 'Invalid class meeting selected.')
                return redirect('student_excuse_slips')

            slot = (
                ClassSlot.objects
                .select_related('class_obj', 'class_obj__subject')
                .filter(
                    pk=slot_id,
                    is_active=True,
                    class_obj__is_active=True,
                    class_obj__academic_year__is_active=True,
                )
                .first()
            )
            if slot is None:
                messages.error(request, 'That class meeting could not be found.')
                return redirect('student_excuse_slips')
            if not PermissionService.can_user_access_class(request.user, slot.class_obj):
                messages.error(request, 'You are not enrolled in that class section.')
                return redirect('student_excuse_slips')

            today = timezone.localdate()
            existing_session = ClassSession.objects.filter(
                slot=slot, session_date=session_date,
            ).first()

            # A manually created make-up session may sit on a different weekday;
            # it is still fileable. A brand-new date must match the weekly slot.
            if existing_session is None and session_date.weekday() != slot.weekday:
                messages.error(request, 'That date does not match the class schedule.')
                return redirect('student_excuse_slips')
            if not (today <= session_date <= today + timedelta(days=EXCUSE_ADVANCE_DAYS)):
                messages.error(
                    request,
                    f'Advance excuses can be filed up to {EXCUSE_ADVANCE_DAYS} days ahead.',
                )
                return redirect('student_excuse_slips')

            if existing_session is not None:
                session = existing_session
            else:
                try:
                    session, _ = ClassSession.objects.get_or_create(
                        slot=slot,
                        session_date=session_date,
                        defaults={'status': ClassSession.STATUS_SCHEDULED},
                    )
                except IntegrityError:
                    session = ClassSession.objects.filter(
                        slot=slot, session_date=session_date,
                    ).first()
                    if session is None:
                        messages.error(request, 'That class meeting could not be prepared.')
                        return redirect('student_excuse_slips')
            if session.status == ClassSession.STATUS_CANCELED:
                messages.error(request, 'That class meeting was canceled.')
                return redirect('student_excuse_slips')
        else:
            messages.error(request, 'Choose a class meeting to excuse.')
            return redirect('student_excuse_slips')

        # Only a meeting the student is actually enrolled in can be excused.
        if not PermissionService.can_user_access_class(request.user, session.slot.class_obj):
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
        if attachment is None:
            messages.error(
                request,
                'Proof is required: attach the letter, medical certificate, or photo for that day.',
            )
            return redirect('student_excuse_slips')
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

    # Upcoming meetings come from the weekly slots, so a student can file ahead
    # even before any ClassSession row exists for the date.
    today = timezone.localdate()
    upcoming_occurrences = _upcoming_excuse_occurrences(
        profile, today=today, advance_days=EXCUSE_ADVANCE_DAYS,
    )
    upcoming_sessions = [
        row['session'] for row in upcoming_occurrences if row['session'] is not None
    ]
    has_enrolled_classes = Enrollment.objects.filter(
        student_profile=profile,
        status=Enrollment.STATUS_ACTIVE,
        class_obj__is_active=True,
        class_obj__academic_year__is_active=True,
    ).exists()

    slips = (
        ExcuseSlip.objects.filter(student_profile=profile)
        .select_related('session', 'session__slot', 'session__slot__class_obj', 'session__slot__class_obj__subject', 'reviewed_by')
        .order_by('-created_at')
    )

    return render(request, 'core/student/excuse_slips.html', {
        'fileable_records': fileable_records,
        'upcoming_sessions': upcoming_sessions,
        'upcoming_occurrences': upcoming_occurrences,
        'has_enrolled_classes': has_enrolled_classes,
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

    if not PermissionService.can_user_approve_excuse(request.user, slip):
        return JsonResponse({'ok': False, 'error': 'You are not authorized to review this excuse slip.'}, status=403)

    if slip.status != ExcuseSlip.STATUS_PENDING:
        return JsonResponse({'ok': False, 'error': 'This excuse slip has already been reviewed.'}, status=400)

    action = request.POST.get('action', '').strip()
    note = request.POST.get('note', '').strip()

    # Task 4.5: the single-slip endpoint keeps its contract but no longer
    # owns the status transition; the shared service does.
    result = review_excuse_slip(
        actor=request.user, slip=slip, action=action, note=note,
    )
    if not result['ok']:
        status_map = {
            'not_authorized': 403,
            'already_reviewed': 400,
            'note_required': 400,
            'invalid_action': 400,
        }
        return JsonResponse(
            {'ok': False, 'error': result['message']},
            status=status_map.get(result['error'], 400),
        )
    return JsonResponse({'ok': True, 'message': result['message']})


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


# // ==============================================================================
# // AJAX: Bulk Approve Excuse Slips (/teacher/excuse-slips/bulk-approve/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def teacher_excuse_bulk_approve(request):
    """
    // [AJAX Mutation] Bulk-approve selected pending excuse slips (Req 13).
    // POST params: slip_ids (multi-value or comma-separated)
    //
    // Every slip is reviewed through the shared service (permission is
    // re-checked per slip — never inferred from a selected ID). Slips are
    // processed independently so one failure does not prevent the remaining
    // valid approvals. Individual student notifications are sent by the
    // service; a bulk AuditEvent records approved/error counts.
    """
    ids = []
    for chunk in request.POST.getlist('slip_ids'):
        for piece in str(chunk).split(','):
            piece = piece.strip()
            if piece.isdigit():
                ids.append(int(piece))
    ids = list(dict.fromkeys(ids))
    if not ids:
        return JsonResponse(
            {'ok': False, 'error': 'Select at least one excuse slip.'},
            status=400,
        )
    if len(ids) > 100:
        return JsonResponse(
            {'ok': False, 'error': 'Approve at most 100 slips at a time.'},
            status=400,
        )

    approved = 0
    failed = 0
    results = []
    for slip_id in ids:
        slip = (
            ExcuseSlip.objects
            .select_related(
                'session',
                'session__slot',
                'session__slot__class_obj',
                'student_profile',
                'student_profile__user',
            )
            .filter(pk=slip_id)
            .first()
        )
        if slip is None:
            failed += 1
            results.append({
                'slip_id': slip_id,
                'ok': False,
                'message': 'Excuse slip not found.',
            })
            continue
        result = review_excuse_slip(
            actor=request.user, slip=slip, action='approve', note='',
        )
        if result['ok']:
            approved += 1
        else:
            failed += 1
        results.append({'slip_id': slip_id, **result})

    AuditEvent.objects.create(
        actor=request.user,
        action='EXCUSE_BULK_APPROVED',
        object_type='ExcuseSlip',
        object_id='BULK',
        new_value=f'approved={approved}; errors={failed}; requested={len(ids)}',
        reason='Bulk excuse approval',
    )

    return JsonResponse({
        'ok': True,
        'approved': approved,
        'failed': failed,
        'results': results,
        'message': f'Approved {approved} excuse slip(s); {failed} not approved.',
    })
