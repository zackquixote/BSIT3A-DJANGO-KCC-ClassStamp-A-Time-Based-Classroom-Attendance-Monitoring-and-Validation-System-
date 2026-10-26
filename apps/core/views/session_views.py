"""
// ==============================================================================
// KCC CLASSSTAMP - TEACHER ATTENDANCE SESSION & LIVE QR SCANNER CONTROLLERS
// ==============================================================================
// Subsystem: Classroom Attendance Chamber & Validation Engine (RBAC: TEACHER)
// Description:
//   - Opens/closes daily concrete ClassSession instances.
//   - Live interactive Camera QR Scanner Chamber with audio/visual telemetry.
//   - High-performance TOTP validation pipeline (pyotp, grace period check).
//   - Real-time roster grid with instant 1-click manual override.
//   - Concluded session summary & exportable attendance reports.
// References: docs/01_DEV_PLAN.md (Phase 4) | docs/02_SECURITY.md
// ==============================================================================
"""

from datetime import datetime, time, timedelta
import csv
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import role_required
from apps.core.models import (
    AcademicEvent,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Enrollment,
    Profile,
    StampAttempt,
)
from apps.core.services.attendance_service import build_attendance_matrix
from apps.core.services.qr_service import verify_token


def _teacher_can_manage(request, class_obj):
    """
    // Object-level authorization: only the assigned teacher, an ADMIN, or a
    // superuser may manage attendance for a given class section.
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


# // ------------------------------------------------------------------------------
# // Anti-replay & scan abuse-prevention tuning
# // ------------------------------------------------------------------------------
SCAN_RATE_WINDOW_SECONDS = 60
SCAN_RATE_LIMIT_PER_USER = 60
SCAN_RATE_LIMIT_PER_IP = 120
# A consumed token stays unavailable long enough to cover the 30s TOTP interval
# plus the +/-1 window tolerance used by verification.
SCAN_TOKEN_TTL_SECONDS = 120


def _client_ip(request):
    """Best-effort client IP, honoring a single proxy hop."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _bump_counter(key, window):
    """Atomically increment a fixed-window counter, creating it with a TTL."""
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 1, window)
        return 1


def _scan_is_rate_limited(request):
    """
    // Fixed-window throttle keyed by both the acting user and client IP.
    // Returns True once either bucket exceeds its configured allowance.
    """
    user_hits = _bump_counter(
        f'classstamp:scan:rl:user:{request.user.pk}', SCAN_RATE_WINDOW_SECONDS
    )
    ip_hits = _bump_counter(
        f'classstamp:scan:rl:ip:{_client_ip(request)}', SCAN_RATE_WINDOW_SECONDS
    )
    return user_hits > SCAN_RATE_LIMIT_PER_USER or ip_hits > SCAN_RATE_LIMIT_PER_IP


def _consume_scan_token(student_profile, token):
    """
    // Global anti-replay registry: a given (student, token) pair may be
    // consumed exactly once across ALL sessions. cache.add is atomic, so
    // concurrent replay attempts only succeed once.
    """
    key = f'classstamp:scan:token:{student_profile.pk}:{token}'
    return cache.add(key, 1, SCAN_TOKEN_TTL_SECONDS)


# // ==============================================================================
# // CONTROLLER: Open / Launch Attendance Session
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def teacher_session_open(request):
    """
    // [Teacher Controller] Launches an active attendance session for a class slot.
    // Idempotent: Reuses existing OPEN session or creates a new one for today.
    """
    class_id = request.POST.get('class_id')
    slot_id = request.POST.get('slot_id')

    teacher_profile = getattr(request.user, 'classstamp_profile', None)

    # Superuser or Admin can open sessions for testing; Teachers can only open for their assigned classes
    if request.user.is_superuser or (teacher_profile and teacher_profile.role == Profile.ROLE_ADMIN):
        class_obj = get_object_or_404(Class, pk=class_id, is_active=True)
    else:
        class_obj = get_object_or_404(Class, pk=class_id, teacher_profile=teacher_profile, is_active=True)

    today = timezone.localdate()

    # Determine or retrieve slot
    slot = None
    if slot_id:
        slot = get_object_or_404(ClassSlot, pk=slot_id, class_obj=class_obj)
    else:
        # Use only today's scheduled slot; otherwise create an ad-hoc slot for today.
        # Falling back to another weekday slot would violate the session-date trigger.
        weekday = today.weekday()
        slot = class_obj.slots.filter(weekday=weekday, is_active=True).first()
        if not slot:
            now_time = timezone.localtime().time().replace(microsecond=0)
            end_time = (timezone.localtime() + timedelta(hours=1, minutes=30)).time().replace(microsecond=0)
            if end_time <= now_time:
                end_time = time(23, 59, 59)
            slot = ClassSlot.objects.create(
                class_obj=class_obj,
                weekday=weekday,
                starts_at=now_time,
                ends_at=end_time,
                room='Assigned Room'
            )

    # Check for existing session today for this slot
    session = ClassSession.objects.filter(slot=slot, session_date=today).first()
    if not session:
        session = ClassSession.objects.create(
            slot=slot,
            session_date=today,
            status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(),
            opened_by=request.user,
            created_by=request.user,
        )
        AuditEvent.objects.create(
            actor=request.user,
            action='OPEN_CLASS_SESSION',
            object_type='ClassSession',
            object_id=str(session.id),
            new_value=f"Opened attendance session for {class_obj.class_code} ({class_obj.subject.code}) on {today}",
        )
    else:
        if session.status != ClassSession.STATUS_OPEN:
            session.status = ClassSession.STATUS_OPEN
            session.opened_at = timezone.now()
            session.opened_by = request.user
            session.closed_at = None
            session.closed_by = None
            session.save(update_fields=['status', 'opened_at', 'opened_by', 'closed_at', 'closed_by'])
            AuditEvent.objects.create(
                actor=request.user,
                action='REOPEN_CLASS_SESSION',
                object_type='ClassSession',
                object_id=str(session.id),
                new_value=f"Reopened attendance session for {class_obj.class_code} on {today}",
            )

    start_of_today = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    end_of_today = timezone.make_aware(datetime.combine(today, datetime.max.time()))

    # Check for official holiday or class suspension conflict advisory
    holiday_conflict = AcademicEvent.objects.filter(
        status=AcademicEvent.STATUS_SCHEDULED,
        start_datetime__lte=end_of_today,
        end_datetime__gte=start_of_today,
        category__in=[AcademicEvent.CATEGORY_HOLIDAY, AcademicEvent.CATEGORY_ACADEMIC_TERM]
    ).first()
    if holiday_conflict:
        messages.warning(
            request,
            f"Calendar Advisory: Today coincides with an official event: '{holiday_conflict.title}'. "
            f"Please verify authorization before conducting required classroom attendance."
        )

    return redirect('teacher_session_scan', session_id=session.id)


# // ==============================================================================
# // VIEW: Live Attendance Scanner Chamber (/teacher/session/<id>/scan/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
def teacher_session_scan(request, session_id):
    """
    // [Teacher Studio View] Split-screen Live Attendance Scanner Chamber.
    // Features camera QR scanning, grace countdown telemetry, audio feedback,
    // and live synchronized roster checkoff.
    """
    teacher_profile = getattr(request.user, 'classstamp_profile', None)
    session = get_object_or_404(
        ClassSession.objects.select_related(
            'slot',
            'slot__class_obj',
            'slot__class_obj__subject',
            'slot__class_obj__teacher_profile__user',
            'slot__class_obj__academic_year'
        ),
        pk=session_id
    )

    class_obj = session.slot.class_obj

    # Access control: Must be assigned teacher or Admin
    if not request.user.is_superuser and teacher_profile.role != Profile.ROLE_ADMIN:
        if class_obj.teacher_profile != teacher_profile:
            messages.error(request, "You are not authorized to manage attendance for this class section.")
            return redirect('teacher_dashboard')

    # Enrolled students roster
    enrollments = (
        Enrollment.objects.filter(class_obj=class_obj, status=Enrollment.STATUS_ACTIVE)
        .select_related('student_profile', 'student_profile__user', 'student_profile__program')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )

    # Existing attendance records for this session
    attendance_records = {
        rec.student_profile_id: rec
        for rec in AttendanceRecord.objects.filter(session=session).select_related('student_profile__user', 'student_profile__program')
    }

    # Build student roster status items
    roster_list = []
    present_count = 0
    late_count = 0
    absent_count = 0
    excused_count = 0

    for enr in enrollments:
        sp = enr.student_profile
        rec = attendance_records.get(sp.id)
        status = rec.status if rec else 'PENDING'

        if status == AttendanceRecord.STATUS_PRESENT:
            present_count += 1
        elif status == AttendanceRecord.STATUS_LATE:
            late_count += 1
        elif status == AttendanceRecord.STATUS_ABSENT:
            absent_count += 1
        elif status == AttendanceRecord.STATUS_EXCUSED:
            excused_count += 1

        roster_list.append({
            'enrollment_id': enr.id,
            'student_id': sp.id,
            'student_number': sp.student_number or sp.user.username,
            'full_name': sp.user.get_full_name() or sp.student_number or sp.user.username,
            'initials': sp.initials,
            'program_code': sp.program.code if sp.program else '—',
            'year_level': sp.year_level or 1,
            'student_type': sp.get_student_type_display() if hasattr(sp, 'get_student_type_display') else 'Regular',
            'status': status,
            'stamped_at': rec.stamped_at.strftime('%I:%M %p') if (rec and rec.stamped_at) else None,
            'late_minutes': rec.late_minutes if rec else 0,
            'method': rec.method if rec else None,
        })

    total_enrolled = len(enrollments)
    pending_count = total_enrolled - (present_count + late_count + excused_count + absent_count)

    # Compute scheduled start and grace period cutoff in ISO format for client countdown
    slot = session.slot
    scheduled_start_dt = timezone.make_aware(
        datetime.combine(session.session_date, slot.starts_at)
    )
    grace_cutoff_dt = scheduled_start_dt + timedelta(minutes=class_obj.grace_minutes)

    sess_date = session.session_date
    start_of_sess = timezone.make_aware(datetime.combine(sess_date, datetime.min.time()))
    end_of_sess = timezone.make_aware(datetime.combine(sess_date, datetime.max.time()))

    calendar_conflict = AcademicEvent.objects.filter(
        status=AcademicEvent.STATUS_SCHEDULED,
        start_datetime__lte=end_of_sess,
        end_datetime__gte=start_of_sess,
        category__in=[AcademicEvent.CATEGORY_HOLIDAY, AcademicEvent.CATEGORY_ACADEMIC_TERM]
    ).first()

    context = {
        'session': session,
        'class_obj': class_obj,
        'slot': slot,
        'total_enrolled': total_enrolled,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'pending_count': max(0, pending_count),
        'roster_list': roster_list,
        'grace_cutoff_iso': grace_cutoff_dt.isoformat(),
        'grace_minutes': class_obj.grace_minutes,
        'is_open': session.status == ClassSession.STATUS_OPEN,
        'calendar_conflict': calendar_conflict,
    }
    return render(request, 'core/teacher/scanner.html', context)


# // ==============================================================================
# // API / AJAX: Real-Time Attendance QR Scan Endpoint
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def attendance_scan_api(request):
    """
    // [AJAX Validation Engine] Validates dynamic TOTP QR scans in real time.
    // Checks session state, enrollment, cryptographic TOTP validity, grace window,
    // and logs immutable StampAttempt audit entries.
    """
    session_id = request.POST.get('session_id')
    qr_payload = request.POST.get('qr_payload', '').strip()

    if not session_id or not qr_payload:
        return JsonResponse({'error': 'Missing session_id or qr_payload.'}, status=400)

    session = get_object_or_404(
        ClassSession.objects.select_related('slot', 'slot__class_obj'),
        pk=session_id
    )
    class_obj = session.slot.class_obj

    # 0. Object-level authorization
    if not _teacher_can_manage(request, class_obj):
        return JsonResponse({
            'error': 'You are not authorized to manage attendance for this class section.'
        }, status=403)

    # 0b. Abuse throttle (per-operator and per-IP). Applied before any DB writes.
    if _scan_is_rate_limited(request):
        return JsonResponse({
            'error': 'Too many scan attempts. Please wait a moment and try again.',
            'outcome': 'RATE_LIMITED'
        }, status=429)

    # 1. Verify session is currently OPEN
    if session.status != ClassSession.STATUS_OPEN:
        StampAttempt.objects.create(
            session=session,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_SESSION_CLOSED
        )
        return JsonResponse({
            'error': 'This classroom attendance session is closed.',
            'outcome': StampAttempt.OUTCOME_SESSION_CLOSED
        }, status=400)

    # 1b. Reject scans against a session that is not for today
    if session.session_date != timezone.localdate():
        return JsonResponse({
            'error': 'This session is not scheduled for today. Only today\'s open session can accept stamps.',
            'outcome': StampAttempt.OUTCOME_INVALID
        }, status=400)

    # 2. Parse QR payload: Format "classstamp:<student_number>:<token>"
    match = re.match(r'^classstamp:([A-Za-z0-9\-]+):(\d{6})$', qr_payload)
    if not match:
        StampAttempt.objects.create(
            session=session,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_INVALID
        )
        return JsonResponse({
            'error': 'Invalid ClassStamp QR code format. Please ensure student displays their dynamic badge.',
            'outcome': StampAttempt.OUTCOME_INVALID
        }, status=400)

    student_number = match.group(1).strip()
    token = match.group(2).strip()

    # 3. Locate Student Profile
    student_profile = (
        Profile.objects.filter(
            Q(student_number=student_number) | Q(user__username=student_number),
            role=Profile.ROLE_STUDENT,
        )
        .select_related('user', 'program')
        .first()
    )

    if not student_profile:
        StampAttempt.objects.create(
            session=session,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_INVALID
        )
        return JsonResponse({
            'error': f"Student ID '{student_number}' does not exist in the institutional directory.",
            'outcome': StampAttempt.OUTCOME_INVALID
        }, status=404)

    # 4. Verify Active Enrollment in this Class
    is_enrolled = Enrollment.objects.filter(
        class_obj=class_obj,
        student_profile=student_profile,
        status=Enrollment.STATUS_ACTIVE
    ).exists()

    if not is_enrolled:
        StampAttempt.objects.create(
            session=session,
            student_profile=student_profile,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_INELIGIBLE
        )
        student_display = student_profile.user.get_full_name() or student_number
        return JsonResponse({
            'error': f"{student_display} is NOT enrolled in this class section ({class_obj.class_code}).",
            'outcome': StampAttempt.OUTCOME_INELIGIBLE
        }, status=400)

    # 5. Cryptographic TOTP Token Verification
    raw_secret = student_profile.qr_secret or ''
    if not raw_secret:
        return JsonResponse({'error': 'Student has not activated their QR credential.'}, status=400)

    if not verify_token(student_profile, token, valid_window=1):
        StampAttempt.objects.create(
            session=session,
            student_profile=student_profile,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_EXPIRED
        )
        return JsonResponse({
            'error': 'QR Code has expired or failed cryptographic verification. Please ask the student to refresh.',
            'outcome': StampAttempt.OUTCOME_EXPIRED
        }, status=400)

    # 6. Anti-Replay & Duplicate Stamp Check
    existing_record = AttendanceRecord.objects.filter(
        session=session,
        student_profile=student_profile
    ).first()

    if existing_record:
        StampAttempt.objects.create(
            session=session,
            student_profile=student_profile,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_DUPLICATE
        )
        stamped_time_str = existing_record.stamped_at.strftime('%I:%M %p') if existing_record.stamped_at else 'earlier'
        return JsonResponse({
            'error': f"{student_profile.user.get_full_name() or student_number} was ALREADY stamped as {existing_record.status} at {stamped_time_str}.",
            'outcome': StampAttempt.OUTCOME_DUPLICATE,
            'existing_status': existing_record.status,
            'stamped_at': stamped_time_str,
            'student_name': student_profile.user.get_full_name() or student_number
        }, status=400)

    # 6b. Global anti-replay: consume the (student, token) pair exactly once
    # across every session so a captured code cannot be reused in another class
    # meeting inside its validity window.
    if not _consume_scan_token(student_profile, token):
        StampAttempt.objects.create(
            session=session,
            student_profile=student_profile,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_DUPLICATE
        )
        return JsonResponse({
            'error': 'This QR code was already used for another attendance check-in. '
                     'Please ask the student to refresh their badge.',
            'outcome': StampAttempt.OUTCOME_DUPLICATE
        }, status=400)

    # 7. Time Window & Grace Period Determination
    now = timezone.now()
    slot = session.slot
    scheduled_start_dt = timezone.make_aware(
        datetime.combine(session.session_date, slot.starts_at)
    )
    grace_cutoff_dt = scheduled_start_dt + timedelta(minutes=class_obj.grace_minutes)

    if now <= grace_cutoff_dt:
        final_status = AttendanceRecord.STATUS_PRESENT
        late_minutes = 0
    else:
        final_status = AttendanceRecord.STATUS_LATE
        diff = now - grace_cutoff_dt
        late_minutes = max(1, int(diff.total_seconds() // 60))

    # 8. Atomic Record Persistence
    with transaction.atomic():
        AttendanceRecord.objects.create(
            session=session,
            student_profile=student_profile,
            status=final_status,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=now,
            late_minutes=late_minutes,
            marked_by=request.user,
        )
        StampAttempt.objects.create(
            session=session,
            student_profile=student_profile,
            scanned_by=request.user,
            method=StampAttempt.METHOD_QR,
            outcome=StampAttempt.OUTCOME_ACCEPTED,
        )

    # Calculate updated attendance counts
    counts = AttendanceRecord.objects.filter(session=session).aggregate(
        present=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        excused=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
    )
    total_enrolled = Enrollment.objects.filter(class_obj=class_obj, status=Enrollment.STATUS_ACTIVE).count()
    stamped_total = (counts['present'] or 0) + (counts['late'] or 0) + (counts['absent'] or 0) + (counts['excused'] or 0)
    pending_total = max(0, total_enrolled - stamped_total)

    display_name = student_profile.user.get_full_name() or student_profile.student_number

    return JsonResponse({
        'status': 'success',
        'record_status': final_status,
        'student_id': student_profile.id,
        'student_number': student_profile.student_number,
        'student_name': display_name,
        'initials': student_profile.initials,
        'program_code': student_profile.program.code if student_profile.program else '—',
        'year_level': student_profile.year_level or 1,
        'late_minutes': late_minutes,
        'stamped_at': now.strftime('%I:%M:%S %p'),
        'counts': {
            'present': counts['present'] or 0,
            'late': counts['late'] or 0,
            'absent': counts['absent'] or 0,
            'excused': counts['excused'] or 0,
            'pending': pending_total,
            'total': total_enrolled
        }
    })


# // ==============================================================================
# // API / AJAX: Manual Override Attendance Status
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def teacher_manual_override_ajax(request, session_id):
    """
    // [AJAX Mutation] Manual instructor override for student attendance status.
    // Handles excused absences, medical excuses, or offline manual entry.
    """
    session = get_object_or_404(ClassSession.objects.select_related('slot__class_obj'), pk=session_id)
    class_obj = session.slot.class_obj

    if not _teacher_can_manage(request, class_obj):
        return JsonResponse({
            'error': 'You are not authorized to manage attendance for this class section.'
        }, status=403)

    student_id = request.POST.get('student_id')
    new_status = request.POST.get('status', '').strip().upper()
    reason = request.POST.get('reason', '').strip()

    valid_statuses = [
        AttendanceRecord.STATUS_PRESENT,
        AttendanceRecord.STATUS_LATE,
        AttendanceRecord.STATUS_ABSENT,
        AttendanceRecord.STATUS_EXCUSED,
    ]
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Invalid status choice.'}, status=400)

    student_profile = get_object_or_404(Profile, pk=student_id, role=Profile.ROLE_STUDENT)

    is_enrolled = Enrollment.objects.filter(
        class_obj=class_obj,
        student_profile=student_profile,
        status=Enrollment.STATUS_ACTIVE,
    ).exists()
    if not is_enrolled:
        return JsonResponse({
            'error': 'Student is not actively enrolled in this class section.'
        }, status=400)

    record, created = AttendanceRecord.objects.get_or_create(
        session=session,
        student_profile=student_profile,
        defaults={
            'status': new_status,
            'method': AttendanceRecord.METHOD_MANUAL,
            'stamped_at': timezone.now(),
            'correction_reason': reason or 'Manual instructor adjudication',
            'marked_by': request.user,
        }
    )

    if not created:
        record.status = new_status
        record.method = AttendanceRecord.METHOD_MANUAL
        record.correction_reason = reason or 'Manual instructor update'
        record.marked_by = request.user
        record.stamped_at = timezone.now()
        record.save(update_fields=['status', 'method', 'correction_reason', 'marked_by', 'stamped_at'])

    AuditEvent.objects.create(
        actor=request.user,
        action='OVERRIDE_ATTENDANCE',
        object_type='AttendanceRecord',
        object_id=str(record.id),
        new_value=f"Manual override to {new_status} for {student_profile.user.get_full_name() or student_profile.student_number}: {reason}",
    )

    # Recalculate counts
    counts = AttendanceRecord.objects.filter(session=session).aggregate(
        present=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        excused=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
    )
    total_enrolled = Enrollment.objects.filter(class_obj=session.slot.class_obj, status=Enrollment.STATUS_ACTIVE).count()
    stamped_total = (counts['present'] or 0) + (counts['late'] or 0) + (counts['absent'] or 0) + (counts['excused'] or 0)

    return JsonResponse({
        'status': 'success',
        'student_id': student_profile.id,
        'new_status': new_status,
        'stamped_at': record.stamped_at.strftime('%I:%M %p'),
        'counts': {
            'present': counts['present'] or 0,
            'late': counts['late'] or 0,
            'absent': counts['absent'] or 0,
            'excused': counts['excused'] or 0,
            'pending': max(0, total_enrolled - stamped_total)
        }
    })


# // ==============================================================================
# // CONTROLLER: Conclude / Close Attendance Session
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
@require_POST
def teacher_session_close(request, session_id):
    """
    // [Teacher Controller] Finalizes an active session.
    // Automatically marks all unscanned active enrolled students as ABSENT.
    """
    session = get_object_or_404(ClassSession.objects.select_related('slot__class_obj'), pk=session_id)
    class_obj = session.slot.class_obj

    if not _teacher_can_manage(request, class_obj):
        messages.error(request, "You are not authorized to manage attendance for this class section.")
        return redirect('teacher_dashboard')

    with transaction.atomic():
        session.status = ClassSession.STATUS_CLOSED
        session.closed_at = timezone.now()
        session.closed_by = request.user
        session.save(update_fields=['status', 'closed_at', 'closed_by'])

        # Auto-mark missing students as ABSENT
        enrolled_profiles = Profile.objects.filter(
            enrollments__class_obj=class_obj,
            enrollments__status=Enrollment.STATUS_ACTIVE
        )
        stamped_ids = set(session.attendance_records.values_list('student_profile_id', flat=True))
        missing_profiles = enrolled_profiles.exclude(id__in=stamped_ids)

        new_absent_records = [
            AttendanceRecord(
                session=session,
                student_profile=p,
                status=AttendanceRecord.STATUS_ABSENT,
                method=AttendanceRecord.METHOD_SYSTEM,
                stamped_at=timezone.now(),
                marked_by=request.user,
                correction_reason='Auto-marked absent at session close',
            )
            for p in missing_profiles
        ]
        if new_absent_records:
            AttendanceRecord.objects.bulk_create(new_absent_records)

        AuditEvent.objects.create(
            actor=request.user,
            action='CLOSE_CLASS_SESSION',
            object_type='ClassSession',
            object_id=str(session.id),
            new_value=f"Closed session for {class_obj.class_code} ({len(new_absent_records)} auto-marked absent)",
        )

    messages.success(request, f"Session for {class_obj.class_code} successfully concluded.")
    return redirect('teacher_session_summary', session_id=session.id)


# // ==============================================================================
# // VIEW: Session Attendance Summary & Report (/teacher/session/<id>/summary/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
def teacher_session_summary(request, session_id):
    """
    // [Teacher Report View] Printable official attendance roll for a concluded meeting.
    // Computes compliance percentages, breakdown list, and provides CSV export.
    """
    session = get_object_or_404(
        ClassSession.objects.select_related(
            'slot',
            'slot__class_obj',
            'slot__class_obj__subject',
            'slot__class_obj__teacher_profile__user',
            'slot__class_obj__academic_year'
        ),
        pk=session_id
    )
    class_obj = session.slot.class_obj

    if not _teacher_can_manage(request, class_obj):
        messages.error(request, "You are not authorized to view attendance for this class section.")
        return redirect('teacher_dashboard')

    records = (
        AttendanceRecord.objects.filter(session=session)
        .select_related('student_profile', 'student_profile__user', 'student_profile__program')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )

    total_count = records.count()
    present_count = records.filter(status=AttendanceRecord.STATUS_PRESENT).count()
    late_count = records.filter(status=AttendanceRecord.STATUS_LATE).count()
    absent_count = records.filter(status=AttendanceRecord.STATUS_ABSENT).count()
    excused_count = records.filter(status=AttendanceRecord.STATUS_EXCUSED).count()

    attended_count = present_count + late_count
    compliance_rate = round((attended_count / total_count * 100), 1) if total_count > 0 else 0

    return render(request, 'core/teacher/summary.html', {
        'session': session,
        'class_obj': class_obj,
        'records': records,
        'total_count': total_count,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'compliance_rate': compliance_rate,
    })


# // ==============================================================================
# // HELPER: Session History Filtering & Aggregation
# // ==============================================================================
def _parse_iso_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _teacher_session_history_queryset(profile, params):
    """
    // Builds the teacher-scoped session history queryset and normalizes the
    // accepted filter values so the view and CSV export stay consistent.
    """
    qs = (
        ClassSession.objects.filter(slot__class_obj__teacher_profile=profile)
        .select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')
        .annotate(
            present_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_PRESENT)),
            late_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_LATE)),
            absent_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_ABSENT)),
            excused_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_EXCUSED)),
            total_records=Count('attendance_records'),
        )
    )

    class_code = (params.get('class_code') or '').strip()
    status = (params.get('status') or '').strip().upper()
    date_from = _parse_iso_date(params.get('date_from'))
    date_to = _parse_iso_date(params.get('date_to'))

    if class_code:
        qs = qs.filter(slot__class_obj__class_code=class_code)
    if status in dict(ClassSession.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(session_date__gte=date_from)
    if date_to:
        qs = qs.filter(session_date__lte=date_to)

    return qs.order_by('-session_date', '-slot__starts_at'), {
        'class_code': class_code,
        'status': status,
        'date_from': date_from.isoformat() if date_from else '',
        'date_to': date_to.isoformat() if date_to else '',
    }


def _apply_attendance_rate(sessions):
    for session in sessions:
        attended = session.present_count + session.late_count
        session.attendance_rate = (
            round(attended / session.total_records * 100, 1)
            if session.total_records else 0
        )
    return sessions


# // ==============================================================================
# // VIEW: Teacher Session History & Reports
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER)
def teacher_session_history(request):
    """
    // [Teacher Report View] Paginated, filterable history of every class meeting
    // the teacher has conducted, with per-session attendance aggregates and CSV export.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    queryset, filters = _teacher_session_history_queryset(profile, request.GET)

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    sessions = _apply_attendance_rate(list(page_obj.object_list))

    class_choices = (
        Class.objects.filter(teacher_profile=profile)
        .order_by('class_code')
        .values_list('class_code', flat=True)
    )

    query_string = urlencode({key: value for key, value in filters.items() if value})

    return render(request, 'core/teacher/session_history.html', {
        'page_obj': page_obj,
        'sessions': sessions,
        'filters': filters,
        'status_choices': ClassSession.STATUS_CHOICES,
        'class_choices': class_choices,
        'total_matching': paginator.count,
        'query_string': query_string,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER)
def teacher_session_history_export(request):
    """
    // [Teacher Report View] Streams the filtered session history as CSV.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    queryset, _filters = _teacher_session_history_queryset(profile, request.GET)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_session_history.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Meeting Date', 'Start Time', 'End Time', 'Class Code', 'Subject Code',
        'Subject Name', 'Room', 'Status', 'Present', 'Late', 'Absent', 'Excused',
        'Total Records', 'Attendance Rate (%)', 'Opened At', 'Closed At',
    ])

    for session in _apply_attendance_rate(list(queryset.iterator())):
        class_obj = session.slot.class_obj
        writer.writerow([
            session.session_date.isoformat(),
            session.slot.starts_at.strftime('%H:%M'),
            session.slot.ends_at.strftime('%H:%M'),
            class_obj.class_code,
            class_obj.subject.code,
            class_obj.subject.name,
            session.slot.room or '',
            session.status,
            session.present_count,
            session.late_count,
            session.absent_count,
            session.excused_count,
            session.total_records,
            session.attendance_rate,
            session.opened_at.isoformat() if session.opened_at else '',
            session.closed_at.isoformat() if session.closed_at else '',
        ])

    return response


# // ==============================================================================
# // VIEW: Single Session Official Roll CSV Export
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
def teacher_session_export(request, session_id):
    """
    // [Teacher Report View] Exports the official per-student attendance roll
    // for one concluded meeting as CSV.
    """
    session = get_object_or_404(
        ClassSession.objects.select_related(
            'slot', 'slot__class_obj', 'slot__class_obj__subject'
        ),
        pk=session_id
    )
    class_obj = session.slot.class_obj

    if not _teacher_can_manage(request, class_obj):
        messages.error(request, "You are not authorized to export attendance for this class section.")
        return redirect('teacher_dashboard')

    records = (
        AttendanceRecord.objects.filter(session=session)
        .select_related('student_profile', 'student_profile__user', 'student_profile__program')
        .order_by('student_profile__user__last_name', 'student_profile__user__first_name')
    )

    filename = f'attendance_{class_obj.class_code}_{session.session_date.isoformat()}.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Student Number', 'Last Name', 'First Name', 'Program', 'Year Level',
        'Status', 'Method', 'Late Minutes', 'Stamped At', 'Correction Reason',
    ])

    for record in records.iterator():
        student = record.student_profile
        writer.writerow([
            student.student_number or '',
            student.user.last_name,
            student.user.first_name,
            student.program.code if student.program_id else '',
            student.year_level,
            record.status,
            record.method,
            record.late_minutes,
            record.stamped_at.isoformat() if record.stamped_at else '',
            record.correction_reason or '',
        ])

    return response


# // ==============================================================================
# // VIEW: Teacher Read-Only Attendance Matrix
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER, Profile.ROLE_ADMIN)
def teacher_attendance_matrix(request, class_id):
    """
    // [Teacher Report View] Read-only 2D attendance grid (students x sessions)
    // for a class section the requesting teacher is assigned to.
    // Supports CSV export via ?format=csv.
    """
    class_obj = get_object_or_404(
        Class.objects.select_related('subject', 'academic_year', 'teacher_profile__user'),
        pk=class_id,
    )

    if not _teacher_can_manage(request, class_obj):
        messages.error(request, "You are not authorized to view attendance for this class section.")
        return redirect('teacher_dashboard')

    matrix = build_attendance_matrix(class_obj)

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f"attendance_matrix_{class_obj.class_code}_{timezone.localdate().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        headers = ['Student ID', 'Student Name', 'Program']
        for session in matrix['session_list']:
            headers.append(f"{session['display_date']} ({session['weekday']})")
        headers.extend(['Present', 'Late', 'Absent', 'Excused', 'Attendance Rate %'])
        writer.writerow(headers)

        for row in matrix['student_rows']:
            csv_row = [row['student_number'], row['name'], row['program']]
            for cell in row['cells']:
                csv_row.append(cell['status'])
            csv_row.extend([
                row['present'], row['late'], row['absent'], row['excused'], f"{row['rate']}%",
            ])
            writer.writerow(csv_row)

        return response

    return render(request, 'core/teacher/matrix.html', {
        'class_obj': class_obj,
        **matrix,
    })
