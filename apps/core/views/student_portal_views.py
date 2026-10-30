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

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import approved_required, role_required
from apps.core.forms import StudentAvatarForm, StudentProfileForm
from apps.core.models import AttendanceRecord, AuditEvent, Enrollment, OfflineBadge, Profile
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

    proof = profile.registration_proof
    proof_is_image = False
    if proof:
        ext = (proof.name or '').lower().rsplit('.', 1)[-1]
        proof_is_image = ext in {'jpg', 'jpeg', 'png', 'webp', 'gif'}

    return render(request, 'core/student/qr_badge.html', {
        'profile': profile,
        'student_number': profile.student_number or request.user.get_username(),
        'has_qr_secret': bool(profile.qr_secret),
        'proof': proof,
        'proof_is_image': proof_is_image,
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
    """Personal attendance ledger with per-class compliance breakdown (S-06 filters)."""
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

    # S-06: filterable ledger — status and class filters, applied server-side
    selected_status = request.GET.get('status', '').strip().upper()
    if selected_status in dict(AttendanceRecord.STATUS_CHOICES):
        records = records.filter(status=selected_status)
    else:
        selected_status = ''

    selected_class_id = request.GET.get('class_id', '').strip()
    filter_classes = list(
        Enrollment.objects.filter(
            student_profile=profile, status=Enrollment.STATUS_ACTIVE,
        )
        .select_related('class_obj', 'class_obj__subject')
        .order_by('class_obj__subject__code')
    )
    if selected_class_id:
        try:
            selected_class_id = int(selected_class_id)
            records = records.filter(session__slot__class_obj_id=selected_class_id)
        except (ValueError, TypeError):
            selected_class_id = ''

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
        'selected_status': selected_status,
        'selected_class_id': selected_class_id,
        'filter_classes': filter_classes,
    })


def _styled_password_form(form):
    """Applies the shared form-control styling to Django's PasswordChangeForm."""
    form.fields['old_password'].widget.attrs.update({
        'class': 'form-control', 'autocomplete': 'current-password',
    })
    # Django autofocuses this field; that would scroll phones straight past the page header.
    form.fields['old_password'].widget.attrs.pop('autofocus', None)
    form.fields['new_password1'].widget.attrs.update({
        'class': 'form-control', 'autocomplete': 'new-password',
    })
    form.fields['new_password2'].widget.attrs.update({
        'class': 'form-control', 'autocomplete': 'new-password',
    })
    return form


# // ==============================================================================
# // VIEW: My Profile (/student/profile/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_profile(request):
    """
    // [Student Portal] Self-service profile maintenance: display name, email,
    // mobile number, gender and password. Institutional fields (student number,
    // program, year level, approval state) remain registrar-controlled.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    if profile is None:
        messages.error(request, 'Student profile not found. Please contact the registrar.')
        return redirect('student_dashboard')

    user = request.user
    profile_form = StudentProfileForm(instance=profile, user=user)
    avatar_form = StudentAvatarForm()
    password_form = _styled_password_form(PasswordChangeForm(user=user))

    if request.method == 'POST':
        if request.POST.get('form_type') == 'password':
            password_form = _styled_password_form(PasswordChangeForm(user=user, data=request.POST))
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                AuditEvent.objects.create(
                    actor=user,
                    action='CHANGE_OWN_PASSWORD',
                    object_type='User',
                    object_id=str(user.pk),
                )
                messages.success(request, 'Password updated successfully.')
                return redirect('student_profile')
        elif request.POST.get('form_type') == 'avatar':
            if request.POST.get('avatar_action') == 'remove':
                if profile.avatar:
                    profile.avatar.delete(save=False)
                    profile.avatar = None
                    profile.save(update_fields=['avatar'])
                    AuditEvent.objects.create(
                        actor=user,
                        action='REMOVE_OWN_AVATAR',
                        object_type='Profile',
                        object_id=str(profile.pk),
                    )
                    messages.success(request, 'Profile photo removed.')
                return redirect('student_profile')
            avatar_form = StudentAvatarForm(request.POST, request.FILES)
            if avatar_form.is_valid():
                if profile.avatar:
                    profile.avatar.delete(save=False)
                profile.avatar = avatar_form.cleaned_data['avatar']
                profile.save(update_fields=['avatar'])
                AuditEvent.objects.create(
                    actor=user,
                    action='UPDATE_OWN_AVATAR',
                    object_type='Profile',
                    object_id=str(profile.pk),
                )
                messages.success(request, 'Profile photo updated.')
                return redirect('student_profile')
        else:
            before = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone_number': profile.phone_number or '',
                'gender': profile.gender or '',
            }
            profile_form = StudentProfileForm(request.POST, instance=profile, user=user)
            if profile_form.is_valid():
                profile_form.save()
                after = {
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'phone_number': profile.phone_number or '',
                    'gender': profile.gender or '',
                }
                changed = [key for key in before if before[key] != after[key]]
                if changed:
                    AuditEvent.objects.create(
                        actor=user,
                        action='UPDATE_OWN_PROFILE',
                        object_type='Profile',
                        object_id=str(profile.pk),
                        old_value=', '.join(f'{k}={before[k]}' for k in changed),
                        new_value=', '.join(f'{k}={after[k]}' for k in changed),
                    )
                messages.success(request, 'Profile updated successfully.')
                return redirect('student_profile')

    return render(request, 'core/student/profile.html', {
        'profile': profile,
        'profile_form': profile_form,
        'avatar_form': avatar_form,
        'password_form': password_form,
        'student_number': profile.student_number or user.get_username(),
        'is_approved': profile.approval_status == Profile.APPROVAL_APPROVED,
    })
