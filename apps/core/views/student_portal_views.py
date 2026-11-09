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
from datetime import date

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.decorators import approved_required, role_required
from apps.core.forms import StudentAvatarForm, StudentProfileForm
from apps.core.models import (
    AcademicYear,
    AttendanceDispute,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    Enrollment,
    OfflineBadge,
    Profile,
)
from apps.core.services.class_join_service import hash_join_code, normalize_join_code
from apps.core.services.in_app_notification_service import create_notification
from apps.core.services.schedule_service import student_overlap_conflicts
from apps.core.services.qr_service import (
    TOTP_INTERVAL,
    build_payload,
    current_token,
    qr_png_data_uri,
)
from apps.core.services.section_service import student_section_summary


def _seconds_remaining():
    """Seconds left in the current TOTP window."""
    return TOTP_INTERVAL - (int(time.time()) % TOTP_INTERVAL)


@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
@require_http_methods(['GET', 'POST'])
def student_join_class(request):
    """Request enrollment in an active class using its private join code."""
    profile = request.user.classstamp_profile
    error_message = ''

    if request.method == 'POST':
        throttle_key = f'class-join-attempts:{profile.pk}'
        attempts = cache.get(throttle_key, 0)
        request_created = False
        if attempts >= 8:
            error_message = 'Too many attempts. Please wait 15 minutes before trying again.'
        else:
            try:
                if not cache.add(throttle_key, 1, timeout=900):
                    cache.incr(throttle_key)
            except ValueError:
                cache.set(throttle_key, attempts + 1, timeout=900)

            submitted_code = normalize_join_code(request.POST.get('join_code', ''))
            allowed_characters = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
            if len(submitted_code) != 12 or any(
                character not in allowed_characters for character in submitted_code
            ):
                error_message = 'That code could not be used. Check it with your teacher or contact an administrator.'
            else:
                digest = hash_join_code(submitted_code)
                class_obj = (
                    Class.objects.filter(
                        join_code_digest=digest,
                        join_code_active=True,
                        is_active=True,
                        academic_year__is_active=True,
                    )
                    .select_related('academic_year', 'subject', 'program', 'teacher_profile__user')
                    .first()
                )
                if class_obj is None:
                    error_message = 'That code could not be used. Check it with your teacher or contact an administrator.'
                elif class_obj.program_id and class_obj.program_id != profile.program_id:
                    error_message = 'That code could not be used. Check it with your teacher or contact an administrator.'
                else:
                    with transaction.atomic():
                        class_obj = Class.objects.select_for_update().get(pk=class_obj.pk)
                        existing = Enrollment.objects.select_for_update().filter(
                            class_obj=class_obj,
                            student_profile=profile,
                        ).first()
                        if (
                            not class_obj.is_active
                            or not class_obj.academic_year.is_active
                            or not class_obj.join_code_active
                            or class_obj.join_code_digest != digest
                        ):
                            error_message = 'That code could not be used. Check it with your teacher or contact an administrator.'
                        elif existing and existing.status == Enrollment.STATUS_ACTIVE:
                            error_message = 'You are already enrolled in this class.'
                        elif existing and existing.status == Enrollment.STATUS_PENDING:
                            # Legacy PENDING from join code — auto-upgrade to ACTIVE
                            existing.status = Enrollment.STATUS_ACTIVE
                            existing.approved_at = timezone.now()
                            existing.save(update_fields=['status', 'approved_at', 'updated_at'])
                            error_message = ''  # treat as success below
                            request_created = True  # will trigger success message
                            AuditEvent.objects.create(
                                actor=request.user,
                                action='CLASS_JOIN_ENROLL',
                                object_type='Enrollment',
                                object_id=str(existing.pk),
                                reason='Student re-submitted join code; legacy PENDING auto-approved.',
                            )
                        elif existing and existing.status == Enrollment.STATUS_COMPLETED:
                            error_message = 'Contact an administrator to restore access to this class.'
                        else:
                            reserved = Enrollment.objects.filter(
                                class_obj=class_obj,
                                status=Enrollment.STATUS_ACTIVE,
                            ).count()
                            if class_obj.capacity and reserved >= class_obj.capacity:
                                error_message = 'This class has no remaining seats.'
                            else:
                                conflicts = student_overlap_conflicts(profile, class_obj)
                                if conflicts:
                                    error_message = (
                                        'Your schedule conflicts with another enrolled class. '
                                        'Contact an administrator for help.'
                                    )
                                else:
                                    if existing and existing.status == Enrollment.STATUS_WITHDRAWN:
                                        enrollment = existing
                                        enrollment.status = Enrollment.STATUS_ACTIVE
                                        enrollment.approved_by = None
                                        enrollment.approved_at = timezone.now()
                                        enrollment.save(update_fields=[
                                            'status', 'approved_by', 'approved_at', 'updated_at',
                                        ])
                                        request_created = True
                                    else:
                                        enrollment, request_created = Enrollment.objects.get_or_create(
                                            class_obj=class_obj,
                                            student_profile=profile,
                                            defaults={'status': Enrollment.STATUS_ACTIVE},
                                        )
                                    if request_created:
                                        AuditEvent.objects.create(
                                            actor=request.user,
                                            action='CLASS_JOIN_ENROLL',
                                            object_type='Enrollment',
                                            object_id=str(enrollment.pk),
                                            reason='Student enrolled via join code (auto-approved).',
                                        )
                                        if class_obj.teacher_profile_id:
                                            create_notification(
                                                class_obj.teacher_profile.user,
                                                'enrollment',
                                                'Student enrolled via join code',
                                                (
                                                    f'{profile.user.get_full_name() or profile.student_number} '
                                                    f'joined {class_obj.class_code} using the class join code.'
                                                ),
                                                '/teacher/classes/',
                                            )
                                        create_notification(
                                            request.user,
                                            'enrollment',
                                            'Class enrollment confirmed',
                                            f'You are now enrolled in {class_obj.class_code}.',
                                            '/student/classes/',
                                        )
                                    else:
                                        error_message = 'Your enrollment status changed. Refresh and check your class list.'

                if not error_message:
                    if request_created:
                        cache.delete(throttle_key)
                        messages.success(
                            request,
                            f'You are now enrolled in {class_obj.class_code}. Check your class list.',
                        )
                    else:
                        messages.success(request, 'Your class enrollment request was processed.')
                    return redirect('student_join_class')

        if error_message:
            messages.error(request, error_message)
            return redirect('student_join_class')

    active_year = AcademicYear.objects.filter(is_active=True).first()
    enrollments = Enrollment.objects.filter(
        student_profile=profile,
        status__in=[Enrollment.STATUS_ACTIVE, Enrollment.STATUS_PENDING],
        class_obj__is_active=True,
    )
    if active_year:
        enrollments = enrollments.filter(class_obj__academic_year=active_year)
    else:
        enrollments = enrollments.none()
    enrollments = enrollments.select_related(
        'class_obj__subject', 'class_obj__teacher_profile__user', 'class_obj__academic_year',
    ).order_by('class_obj__subject__code')

    return render(request, 'core/student/join_class.html', {
        'enrollments': enrollments,
        'active_year': active_year,
    })


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

    # Inclusive date range. Malformed input is ignored rather than erroring —
    # a half-typed date in the URL should not blank the ledger.
    def _parse_date(raw):
        try:
            return date.fromisoformat((raw or '').strip())
        except (ValueError, TypeError):
            return None

    date_from = _parse_date(request.GET.get('from'))
    date_to = _parse_date(request.GET.get('to'))
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    if date_from:
        records = records.filter(session__session_date__gte=date_from)
    if date_to:
        records = records.filter(session__session_date__lte=date_to)

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
        'date_from': date_from.isoformat() if date_from else '',
        'date_to': date_to.isoformat() if date_to else '',
        'filter_classes': filter_classes,
        'disputable_records': list(
            records.exclude(status=AttendanceRecord.STATUS_EXCUSED)
            .select_related('session', 'session__slot', 'session__slot__class_obj__subject')
            [:50]
        ),
        'disputes': list(
            AttendanceDispute.objects.filter(student_profile=profile)
            .select_related(
                'record', 'record__session', 'record__session__slot',
                'record__session__slot__class_obj__subject', 'resolved_by',
            )
            .order_by('-created_at')[:20]
        ),
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
        # Section membership is derived from active enrollments, never stored on
        # the profile: an irregular student legitimately has more than one.
        'section_summary': student_section_summary(profile),
        'student_number': profile.student_number or user.get_username(),
        'is_approved': profile.approval_status == Profile.APPROVAL_APPROVED,
    })


# // ==============================================================================
# // VIEW: Printable Term Attendance Record (/student/record/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_term_record(request):
    """
    // A student's own attendance record for the active term, built for paper.
    // The screen version is readable; @media print drops the app chrome so it can
    // be filed as a PDF without adding a PDF library.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    active_year = AcademicYear.objects.filter(is_active=True).first()

    enrollments = (
        Enrollment.objects
        .filter(student_profile=profile, status=Enrollment.STATUS_ACTIVE)
        .select_related(
            'class_obj', 'class_obj__subject',
            'class_obj__teacher_profile__user', 'class_obj__academic_year',
        )
        .order_by('class_obj__subject__code')
    )
    if active_year is not None:
        enrollments = enrollments.filter(class_obj__academic_year=active_year)
    enrollments = list(enrollments)

    class_ids = [enrollment.class_obj_id for enrollment in enrollments]

    status_counts = {}
    session_counts = {}
    if class_ids:
        for row in (
            AttendanceRecord.objects
            .filter(student_profile=profile, session__slot__class_obj_id__in=class_ids)
            .exclude(session__status=ClassSession.STATUS_CANCELED)
            .values('session__slot__class_obj_id', 'status')
            .annotate(n=Count('id'))
        ):
            status_counts.setdefault(row['session__slot__class_obj_id'], {})[row['status']] = row['n']

        session_counts = dict(
            ClassSession.objects
            .filter(slot__class_obj_id__in=class_ids)
            .exclude(status=ClassSession.STATUS_CANCELED)
            .values('slot__class_obj_id')
            .annotate(n=Count('id'))
            .values_list('slot__class_obj_id', 'n')
        )

    rows = []
    totals = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0, 'meetings': 0, 'attended': 0}

    for enrollment in enrollments:
        class_obj = enrollment.class_obj
        counts = status_counts.get(class_obj.id, {})
        present = counts.get(AttendanceRecord.STATUS_PRESENT, 0)
        late = counts.get(AttendanceRecord.STATUS_LATE, 0)
        absent = counts.get(AttendanceRecord.STATUS_ABSENT, 0)
        excused = counts.get(AttendanceRecord.STATUS_EXCUSED, 0)
        meetings = session_counts.get(class_obj.id, 0)
        attended = present + late

        rows.append({
            'subject_code': class_obj.subject.code if class_obj.subject_id else '—',
            'subject_name': class_obj.subject.name if class_obj.subject_id else '',
            'section_code': class_obj.section_code or class_obj.class_code,
            'teacher': (
                class_obj.teacher_profile.user.get_full_name()
                or class_obj.teacher_profile.user.get_username()
            ) if class_obj.teacher_profile_id else 'Unassigned',
            'meetings': meetings,
            'present': present,
            'late': late,
            'absent': absent,
            'excused': excused,
            'attended': attended,
            'rate': round((attended / meetings) * 100, 1) if meetings else None,
        })

        totals['present'] += present
        totals['late'] += late
        totals['absent'] += absent
        totals['excused'] += excused
        totals['meetings'] += meetings
        totals['attended'] += attended

    overall = (
        round((totals['attended'] / totals['meetings']) * 100, 1)
        if totals['meetings'] else None
    )

    return render(request, 'core/student/term_record.html', {
        'profile': profile,
        'rows': rows,
        'totals': totals,
        'overall': overall,
        'active_year': active_year,
        'generated_on': timezone.localdate(),
    })


# // ==============================================================================
# // ACTION: File an Attendance Dispute (/student/attendance/dispute/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
@require_POST
def student_dispute_open(request):
    """
    // "The record itself is wrong." Excuse slips explain an absence; a dispute
    // contests the stamped status (a scan that never registered, a late mark on an
    // early arrival). One dispute per record, reviewed by the instructor.
    """
    from django.db import IntegrityError, transaction

    profile = getattr(request.user, 'classstamp_profile', None)
    record_id = request.POST.get('record_id', '').strip()
    reason = request.POST.get('reason', '').strip()

    if not record_id.isdigit():
        messages.error(request, 'Choose the record you want to dispute.')
        return redirect('student_attendance_log')
    if len(reason) < 10:
        messages.error(request, 'Please describe what went wrong (at least 10 characters).')
        return redirect('student_attendance_log')

    record = (
        AttendanceRecord.objects
        .filter(pk=int(record_id), student_profile=profile)
        .select_related('session__slot__class_obj')
        .first()
    )
    if record is None:
        messages.error(request, 'That record does not belong to your account.')
        return redirect('student_attendance_log')

    if record.status == AttendanceRecord.STATUS_EXCUSED:
        messages.error(request, 'That meeting is already marked excused — nothing to dispute.')
        return redirect('student_attendance_log')

    try:
        # Nested atomic: a duplicate-key failure must roll back only the insert,
        # not poison the surrounding request transaction.
        with transaction.atomic():
            dispute = AttendanceDispute.objects.create(
                record=record,
                student_profile=profile,
                reason=reason,
            )
    except IntegrityError:
        messages.error(request, 'You already filed a dispute for that record.')
        return redirect('student_attendance_log')

    AuditEvent.objects.create(
        actor=request.user,
        action='ATTENDANCE_DISPUTE_FILED',
        object_type='AttendanceDispute',
        object_id=str(dispute.pk),
        new_value=(
            f'{profile.student_number} disputed {record.status} for '
            f'{record.session.slot.class_obj.class_code} on {record.session.session_date}'
        ),
        reason=reason[:200],
    )
    class_obj = record.session.slot.class_obj
    if class_obj.teacher_profile_id:
        create_notification(
            class_obj.teacher_profile.user,
            'attendance_dispute',
            'Attendance dispute submitted',
            (
                f'{profile.user.get_full_name() or profile.student_number} disputed the '
                f'{record.status.lower()} record for {class_obj.class_code} on '
                f'{record.session.session_date}.'
            ),
            '/teacher/excuse-slips/',
        )
    messages.success(request, 'Dispute submitted — your instructor will review it.')
    return redirect('student_attendance_log')
