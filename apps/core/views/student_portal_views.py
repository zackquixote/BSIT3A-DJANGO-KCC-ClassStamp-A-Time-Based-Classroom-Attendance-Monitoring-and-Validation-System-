"""
// ==============================================================================
// KCC CLASSSTAMP - STUDENT SELF-SERVICE PORTAL CONTROLLERS
// ==============================================================================
// Subsystem: Student Portal (RBAC: STUDENT, approved accounts only)
// Description:
//   - Dynamic rotating QR badge page (what the teacher scanner reads).
//   - Token JSON endpoint powering the badge auto-refresh.
//   - Personal attendance history grouped by enrolled class.
// Security References: docs/02_SECURITY.md | apps/core/decorators/rbac.py
// ==============================================================================
"""

import hashlib
import secrets
import time

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import approved_required, role_required
from apps.core.models import AttendanceRecord, Enrollment, OfflineBadge, Profile
from apps.core.services.qr_service import (
    TOTP_INTERVAL,
    build_payload,
    current_token,
    qr_png_data_uri,
)


def _seconds_remaining():
    """Seconds left in the current TOTP window."""
    return TOTP_INTERVAL - (int(time.time()) % TOTP_INTERVAL)


# // ==============================================================================
# // VIEW: Student Rotating QR Badge (/student/qr/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_qr_badge(request):
    """Renders the personal rotating badge that teachers scan for attendance."""
    profile = getattr(request.user, 'classstamp_profile', None)
    return render(request, 'core/student/qr_badge.html', {
        'profile': profile,
        'student_number': profile.student_number or request.user.get_username(),
        'has_qr_secret': bool(profile.qr_secret),
        'today': timezone.localdate(),
    })


# // ==============================================================================
# // API: Current QR Token (/api/student/qr-token/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_qr_token_api(request):
    """
    // Returns the caller's current dynamic token + rendered QR image.
    // Students can only ever read their OWN credential (never another student's).
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    if profile is None or not profile.qr_secret:
        return JsonResponse({
            'error': 'Your QR credential has not been activated yet. Please contact the registrar.'
        }, status=400)

    token = current_token(profile)
    if not token:
        return JsonResponse({'error': 'Unable to generate a QR token.'}, status=500)

    payload = build_payload(profile, token)
    return JsonResponse({
        'token': token,
        'payload': payload,
        'qr_data_uri': qr_png_data_uri(payload),
        'student_number': profile.student_number or request.user.get_username(),
        'name': request.user.get_full_name() or request.user.get_username(),
        'seconds_remaining': _seconds_remaining(),
        'interval': TOTP_INTERVAL,
        'server_time': timezone.localtime().strftime('%I:%M:%S %p'),
    })


# // ==============================================================================
# // API: Issue Offline Badge (/api/student/offline-badge/issue/)  (S-07)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
@require_POST
def student_offline_badge_issue(request):
    """
    // [AJAX] Issues a single-use, 48-hour offline QR badge for connectivity-limited
    // students. The raw bearer token is shown once and stored server-side only as
    // a SHA-256 hash; redemption is enforced exactly once at any scanning terminal.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    if profile is None:
        return JsonResponse({'error': 'Student profile not found.'}, status=400)

    raw_token = secrets.token_hex(32)  # 64 hex chars
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    expires_at = timezone.now() + timezone.timedelta(hours=48)

    # A student keeps at most one redeemable offline badge at a time.
    OfflineBadge.objects.filter(
        student_profile=profile,
        consumed_at__isnull=True,
    ).delete()

    OfflineBadge.objects.create(
        student_profile=profile,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    student_number = profile.student_number or request.user.get_username()
    payload = f'classstamp:offline:{student_number}:{raw_token}'

    return JsonResponse({
        'ok': True,
        'payload': payload,
        'qr_data_uri': qr_png_data_uri(payload),
        'student_number': student_number,
        'name': request.user.get_full_name() or request.user.get_username(),
        'expires_at': expires_at.isoformat(),
        'expires_in_seconds': int((expires_at - timezone.now()).total_seconds()),
    })


# // ==============================================================================
# // VIEW: Student Attendance History (/student/attendance/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_attendance_log(request):
    """Personal attendance ledger with per-class compliance breakdown."""
    profile = getattr(request.user, 'classstamp_profile', None)

    records = (
        AttendanceRecord.objects.filter(student_profile=profile)
        .select_related(
            'session',
            'session__slot',
            'session__slot__class_obj',
            'session__slot__class_obj__subject',
            'session__slot__class_obj__teacher_profile__user',
        )
        .order_by('-session__session_date', '-stamped_at')
    )

    summary_map = {}
    for enr in Enrollment.objects.filter(
        student_profile=profile, status=Enrollment.STATUS_ACTIVE
    ).select_related('class_obj', 'class_obj__subject', 'class_obj__teacher_profile__user'):
        summary_map[enr.class_obj_id] = {
            'class_obj': enr.class_obj,
            'present': 0,
            'late': 0,
            'absent': 0,
            'excused': 0,
            'total': 0,
            'compliance_rate': 0,
        }

    status_keys = {
        AttendanceRecord.STATUS_PRESENT: 'present',
        AttendanceRecord.STATUS_LATE: 'late',
        AttendanceRecord.STATUS_ABSENT: 'absent',
        AttendanceRecord.STATUS_EXCUSED: 'excused',
    }
    for rec in records:
        bucket = summary_map.get(rec.session.slot.class_obj_id)
        if bucket is None:
            continue
        key = status_keys.get(rec.status)
        if key:
            bucket[key] += 1
        bucket['total'] += 1

    for bucket in summary_map.values():
        attended = bucket['present'] + bucket['late']
        bucket['compliance_rate'] = (
            round(attended / bucket['total'] * 100, 1) if bucket['total'] else 0
        )

    class_summaries = list(summary_map.values())

    totals = records.aggregate(
        present_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        late_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        absent_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        excused_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
    )
    total_records = records.count()
    attended = (totals['present_count'] or 0) + (totals['late_count'] or 0)
    totals['compliance_rate'] = round(attended / total_records * 100, 1) if total_records else 0

    return render(request, 'core/student/attendance_log.html', {
        'profile': profile,
        'records': records,
        'class_summaries': class_summaries,
        'totals': totals,
        'total_records': total_records,
    })
