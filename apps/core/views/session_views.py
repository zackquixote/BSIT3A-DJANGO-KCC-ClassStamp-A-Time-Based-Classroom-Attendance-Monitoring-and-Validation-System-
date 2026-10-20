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

import base64
from datetime import datetime, timedelta
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
import pyotp

from apps.core.decorators import role_required
from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Enrollment,
    Profile,
    StampAttempt,
)


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
        # Check if there is a scheduled slot for today
        weekday = today.weekday()
        slot = class_obj.slots.filter(weekday=weekday, is_active=True).first()
        if not slot:
            # Fall back to any active slot, or dynamically generate a default slot for this section
            slot = class_obj.slots.filter(is_active=True).first()
            if not slot:
                # Create a default slot matching current time window
                now_time = timezone.localtime().time()
                end_time = (timezone.localtime() + timedelta(hours=1, minutes=30)).time()
                slot = ClassSlot.objects.create(
                    class_obj=class_obj,
                    weekday=weekday,
                    starts_at=now_time.replace(microsecond=0),
                    ends_at=end_time.replace(microsecond=0),
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
        for rec in AttendanceRecord.objects.filter(session=session)
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

    try:
        raw_bytes = bytes.fromhex(raw_secret)
        b32_secret = base64.b32encode(raw_bytes).decode('utf-8').rstrip('=')
    except Exception:
        b32_secret = base64.b32encode(raw_secret.encode()).decode('utf-8').rstrip('=')

    totp = pyotp.TOTP(b32_secret, interval=30)
    is_valid_token = totp.verify(token, valid_window=1)

    if not is_valid_token:
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
    session = get_object_or_404(ClassSession, pk=session_id)
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

    student_profile = get_object_or_404(Profile, pk=student_id)

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
    session = get_object_or_404(ClassSession, pk=session_id)
    class_obj = session.slot.class_obj

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
