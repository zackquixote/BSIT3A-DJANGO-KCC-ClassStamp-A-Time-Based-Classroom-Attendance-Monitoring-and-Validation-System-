"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT ACCOUNT VALIDATION & DOSSIER REVIEW CONTROLLERS
# // ==============================================================================
# // Subsystem: Registrar Identity Verification & Approval Workflow (RBAC: ADMIN ONLY)
# // Description: Administrative queue for reviewing pending self-registered students,
# // inspecting submitted credentials/ID proofs, approving and provisioning dynamic
# // QR secrets, and issuing official rejection notices with audit tracking.
# // Security Reference: docs/02_SECURITY.md
# // ==============================================================================
"""

import logging
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import AuditEvent, Department, Profile, Program
from apps.core.serializers import serialize_student_detail
from apps.core.validators import validate_uploaded_document

logger = logging.getLogger(__name__)
from apps.core.services import (
    approve_student_registration,
    reject_student_registration,
)


def _check_validation_rate_limit(request, max_requests=120, window_seconds=60) -> bool:
    """
    // [Security #16] Rate limiting on validation decisions.
    // Caps individual admin validation calls to 120 / min to prevent accidental rapid double-submissions or loops.
    """
    user_id = getattr(request.user, 'pk', 'anon')
    cache_key = f"val_rl_{user_id}"
    try:
        # add() seeds the window atomically; incr() is atomic, so two concurrent
        # decisions cannot both read the same count and overwrite each other.
        cache.add(cache_key, 0, timeout=window_seconds)
        count = cache.incr(cache_key)
    except ValueError:
        # Window expired between add() and incr(); start a fresh one.
        cache.set(cache_key, 1, timeout=window_seconds)
        count = 1
    except Exception:
        # A cache outage must not block registrar work, but it must not be
        # silent either: losing the throttle is a security-relevant event.
        logger.warning(
            'Validation rate-limit cache unavailable; allowing request for user %s.',
            user_id, exc_info=True,
        )
        return True
    return count <= max_requests


def _redirect_after_validation(request, fallback='validation_pending_queue'):
    """
    // Return to the validation workspace only when the Referer is a local
    // /validation/ path. External hosts and paths are ignored to prevent an
    // open redirect after an administrative decision.
    """
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        parsed = urlparse(referer)
        if parsed.path.startswith('/validation/') and url_has_allowed_host_and_scheme(
            referer,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(referer)
    return redirect(fallback)


# // ==============================================================================
# // VIEW: Account Validation Hub (/validation/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def validation_hub(request):
    """
    // [Admin Controller] Unified Account Validation Workspace
    // Combines the Pending Queue and Reviewed History into a high-performance single workspace with tabs.
    """
    from django.core.paginator import Paginator

    tab = request.GET.get('tab', 'pending').strip()
    query = request.GET.get('q', '').strip()
    selected_dept = request.GET.get('department', '').strip()
    selected_prog = request.GET.get('program', '').strip()
    decision_filter = request.GET.get('decision', '').strip()

    base_pending = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )
    pending_count = base_pending.count()

    # If pending count is 0 and no specific tab was requested in URL, check if user should see reviewed or pending
    if not request.GET.get('tab') and pending_count == 0:
        tab = 'pending'

    # Pre-calculate counts of pending students per department
    departments = Department.objects.filter(is_active=True).annotate(
        pending_count=Count(
            'programs__profiles',
            filter=Q(
                programs__profiles__role=Profile.ROLE_STUDENT,
                programs__profiles__approval_status=Profile.APPROVAL_PENDING,
            )
        )
    ).order_by('name')

    programs = Program.objects.filter(is_active=True).select_related('department').annotate(
        pending_count=Count(
            'profiles',
            filter=Q(
                profiles__role=Profile.ROLE_STUDENT,
                profiles__approval_status=Profile.APPROVAL_PENDING,
            )
        )
    ).order_by('name')

    pending_list = base_pending.select_related('user', 'program', 'program__department').order_by('created_at')

    if selected_dept:
        try:
            pending_list = pending_list.filter(program__department_id=int(selected_dept))
        except (ValueError, TypeError):
            selected_dept = ''

    if selected_prog:
        try:
            pending_list = pending_list.filter(program_id=int(selected_prog))
        except (ValueError, TypeError):
            selected_prog = ''

    if query and tab == 'pending':
        pending_list = pending_list.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query) |
            Q(student_number__icontains=query)
        )

    # Reviewed queryset
    reviewed_qs = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status__in=[Profile.APPROVAL_APPROVED, Profile.APPROVAL_REJECTED],
    ).select_related('user', 'program', 'program__department', 'approved_by').order_by('-approved_at', '-updated_at')

    approved_count = reviewed_qs.filter(approval_status=Profile.APPROVAL_APPROVED).count()
    rejected_count = reviewed_qs.filter(approval_status=Profile.APPROVAL_REJECTED).count()
    reviewed_count = approved_count + rejected_count

    if query and tab == 'reviewed':
        reviewed_qs = reviewed_qs.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(student_number__icontains=query)
        )

    if decision_filter == 'approved':
        reviewed_qs = reviewed_qs.filter(approval_status=Profile.APPROVAL_APPROVED)
    elif decision_filter == 'rejected':
        reviewed_qs = reviewed_qs.filter(approval_status=Profile.APPROVAL_REJECTED)

    paginator = Paginator(reviewed_qs, 20)
    page_number = request.GET.get('page', 1)
    reviewed_page = paginator.get_page(page_number)

    return render(request, 'core/admin/validation_hub.html', {
        'tab': tab,
        'pending': pending_list,
        'pending_count': pending_count,
        'reviewed': reviewed_page,
        'reviewed_count': reviewed_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'departments': departments,
        'programs': programs,
        'selected_department': selected_dept,
        'selected_program': selected_prog,
        'decision_filter': decision_filter,
        'query': query,
    })


# // Alias validation_queue to validation_hub for backwards compatibility
validation_queue = validation_hub


# // ==============================================================================
# // VIEW: Dedicated Pending Registrations Page (/validation/pending/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def validation_pending_queue(request):
    """
    // [Admin Controller] Dedicated Student Validation Queue
    // Lists pending student registrations awaiting administrative identity verification.
    // Supports multi-department filtering, program filtering, and instant search.
    """
    selected_dept = request.GET.get('department', '').strip()
    selected_prog = request.GET.get('program', '').strip()
    query = request.GET.get('q', '').strip()

    base_pending = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )
    total_pending_count = base_pending.count()

    # Pre-calculate counts of pending students per department for quick tabs and filtering
    departments = Department.objects.filter(is_active=True).annotate(
        pending_count=Count(
            'programs__profiles',
            filter=Q(
                programs__profiles__role=Profile.ROLE_STUDENT,
                programs__profiles__approval_status=Profile.APPROVAL_PENDING,
            )
        )
    ).order_by('name')

    # Pre-calculate counts of pending students per program
    programs = Program.objects.filter(is_active=True).select_related('department').annotate(
        pending_count=Count(
            'profiles',
            filter=Q(
                profiles__role=Profile.ROLE_STUDENT,
                profiles__approval_status=Profile.APPROVAL_PENDING,
            )
        )
    ).order_by('name')

    pending = base_pending.select_related('user', 'program', 'program__department').order_by('created_at')

    # Apply backend filters if query parameters are provided
    if selected_dept:
        try:
            pending = pending.filter(program__department_id=int(selected_dept))
        except (ValueError, TypeError):
            selected_dept = ''

    if selected_prog:
        try:
            pending = pending.filter(program_id=int(selected_prog))
        except (ValueError, TypeError):
            selected_prog = ''

    if query:
        pending = pending.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query) |
            Q(student_number__icontains=query)
        )

    return render(request, 'core/admin/pending_registrations.html', {
        'pending': pending,
        'pending_count': total_pending_count,
        'filtered_count': pending.count(),
        'departments': departments,
        'programs': programs,
        'selected_department': selected_dept,
        'selected_program': selected_prog,
        'query': query,
    })


# // ==============================================================================
# // VIEW: Student Dossier Review Detail (/validation/<student_number>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def validation_detail(request, student_number):
    """
    // [Admin Controller] Detailed Student Registration Review
    // Displays full e-registration submission details for an individual student
    // so an administrator can verify credentials against registrar records.
    // Features queue navigation (next/prev student) and duplicate detection.
    """
    # Lookup student profile by student_number or primary key ID
    lookup = Q(student_number=student_number)
    if str(student_number).isdigit():
        lookup |= Q(pk=int(student_number))

    profile = get_object_or_404(
        Profile.objects.select_related('user', 'program', 'program__department', 'approved_by'),
        lookup,
        role=Profile.ROLE_STUDENT,
    )

    # Queue Navigation: resolve prev/next pending students by pk (pk is also
    # accepted by the validation_detail URL pattern via the pk-or-student_number lookup).
    pending_pks = list(
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_PENDING,
        ).order_by('created_at').values_list('pk', flat=True)
    )

    prev_id = None
    next_id = None
    current_index = None
    total_pending = len(pending_pks)

    if profile.pk in pending_pks:
        idx = pending_pks.index(profile.pk)
        current_index = idx + 1
        if idx > 0:
            prev_id = pending_pks[idx - 1]
        if idx < total_pending - 1:
            next_id = pending_pks[idx + 1]

    # Duplicate Detection: Check for potential matching profiles by student number, name, or email
    duplicates = Profile.objects.filter(
        Q(student_number=profile.student_number) |
        (Q(user__first_name__iexact=profile.user.first_name) & Q(user__last_name__iexact=profile.user.last_name)) |
        Q(user__email__iexact=profile.user.email)
    ).exclude(pk=profile.pk).select_related('user', 'program', 'program__department')[:5]

    # Fetch audit events relating to this profile for full transparency
    audit_events = AuditEvent.objects.filter(
        object_type='Profile',
        object_id=str(profile.pk)
    ).select_related('actor').order_by('-created_at')

    return render(request, 'core/admin/validation_detail.html', {
        'student_profile': profile,
        'audit_events': audit_events,
        'prev_id': prev_id,
        'next_id': next_id,
        'current_index': current_index,
        'total_pending': total_pending,
        'duplicates': duplicates,
    })


# // ==============================================================================
# // VIEW: Slide-Over Dossier JSON (A-02) (/validation/dossier/<profile_id>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def validation_dossier_json(request, profile_id):
    """
    // [Admin AJAX Controller] Slide-Over Dossier Preview
    // Returns full registration dossier data for the off-canvas drawer on the
    // validation hub, plus prev/next pending queue navigation targets for
    // keyboard-driven reviewing (J/K navigation, A approve, R reject, Esc close).
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user', 'program', 'program__department', 'approved_by'),
        pk=profile_id,
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )

    pending_pks = list(
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_PENDING,
        ).order_by('created_at').values_list('pk', flat=True)
    )

    prev_id = None
    next_id = None
    current_index = None
    if profile.pk in pending_pks:
        idx = pending_pks.index(profile.pk)
        current_index = idx + 1
        if idx > 0:
            prev_id = pending_pks[idx - 1]
        if idx < len(pending_pks) - 1:
            next_id = pending_pks[idx + 1]

    dossier = serialize_student_detail(profile)
    dossier.update({
        'department_code': profile.program.department.code if profile.program and profile.program.department else None,
        'department_name': profile.program.department.name if profile.program and profile.program.department else None,
        'username': profile.user.username if profile.user else None,
        'gender': profile.gender or None,
        'student_type': profile.student_type or None,
        'phone_number': profile.phone_number or None,
        'privacy_consent_at': profile.privacy_consent_at.isoformat() if profile.privacy_consent_at else None,
        'prev_id': prev_id,
        'next_id': next_id,
        'prev_url': reverse('validation_dossier_json', args=[prev_id]) if prev_id else None,
        'next_url': reverse('validation_dossier_json', args=[next_id]) if next_id else None,
        'current_index': current_index,
        'total_pending': len(pending_pks),
        'approve_url': reverse('approve_student', args=[profile.pk]),
        'reject_url': reverse('reject_student', args=[profile.pk]),
        'detail_url': reverse('validation_detail', args=[profile.pk]),
    })
    return JsonResponse({'ok': True, 'dossier': dossier})


# // ==============================================================================
# // VIEW: Reopen a Rejected Registration (/validation/reopen/<student_number>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def validation_reopen(request, student_number):
    """
    // [Admin Controller] Returns a rejected registration to the review queue.
    //
    // Without this, rejection is terminal: the student cannot sign in, and
    // registering again collides with the student_number/username their old row
    // still owns. The registrar takes the corrected COR in person and attaches it
    // here, so the whole recovery happens on the admin side — no new auth surface.
    """
    profile = get_object_or_404(
        Profile,
        student_number=student_number,
        role=Profile.ROLE_STUDENT,
    )

    if profile.approval_status != Profile.APPROVAL_REJECTED:
        messages.error(request, 'Only a rejected registration can be reopened.')
        return redirect('validation_detail', student_number=profile.student_number)

    upload = request.FILES.get('registration_proof')
    if upload is not None:
        try:
            validate_uploaded_document(upload)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return redirect('validation_detail', student_number=profile.student_number)

    old_note = profile.approval_note or ''
    reason = (request.POST.get('reason') or '').strip()

    profile.approval_status = Profile.APPROVAL_PENDING
    profile.approval_note = None
    profile.approved_by = None
    profile.approved_at = None
    update_fields = ['approval_status', 'approval_note', 'approved_by', 'approved_at']
    if upload is not None:
        profile.registration_proof = upload
        update_fields.append('registration_proof')
    profile.save(update_fields=update_fields)

    AuditEvent.objects.create(
        actor=request.user,
        action='REOPEN_STUDENT_REGISTRATION',
        object_type='Profile',
        object_id=str(profile.pk),
        old_value=f'REJECTED: {old_note[:200]}',
        new_value='PENDING' + (' (document replaced)' if upload is not None else ''),
        reason=reason or 'Reopened for corrected documents',
    )

    messages.success(
        request,
        f'{profile.student_number} is back in the validation queue.',
    )
    return redirect('validation_detail', student_number=profile.student_number)


# // ==============================================================================
# // VIEW: Approve Student Registration Action (/validation/approve/<student_number>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def approve_student(request, student_number):
    """
    // [Admin Action] Approve Student Registration
    //
    // Security & Trigger Specifications:
    // - Confirms the student's identity against school registrar records.
    // - Satisfies DB trigger `trg_cs_profile_bu`: sets approved_by and approved_at.
    // - Rotates and seals a new 64-character QR secret for dynamic attendance stamping.
    // - Records immutable APPROVE_STUDENT entry into AuditEvent.
    """
    if not _check_validation_rate_limit(request):
        messages.error(request, 'Validation rate limit reached. Please wait a moment before processing further decisions.')
        return redirect('validation_pending_queue')

    lookup = Q(student_number=student_number)
    if str(student_number).isdigit():
        lookup |= Q(pk=int(student_number))

    profile = get_object_or_404(
        Profile,
        lookup,
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )

    approve_student_registration(profile, request.user)

    messages.success(request, f'{profile.user.get_full_name() or profile.user.get_username()} has been approved.')
    next_url = request.POST.get('next')
    if next_url == 'detail':
        return redirect('validation_detail', student_number=profile.pk)
    return _redirect_after_validation(request)


# // ==============================================================================
# // VIEW: Reject Student Registration Action (/validation/reject/<student_number>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def reject_student(request, student_number):
    """
    // [Admin Action] Reject Student Registration
    //
    // Security & Trigger Specifications:
    // - Mandates non-empty `approval_note` (reason) as required by database triggers.
    // - Records timestamps and administrative reviewer ID.
    // - Emits REJECT_STUDENT record to AuditEvent.
    """
    if not _check_validation_rate_limit(request):
        messages.error(request, 'Validation rate limit reached. Please wait a moment before processing further decisions.')
        return redirect('validation_pending_queue')

    lookup = Q(student_number=student_number)
    if str(student_number).isdigit():
        lookup |= Q(pk=int(student_number))

    profile = get_object_or_404(
        Profile,
        lookup,
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )

    next_url = request.POST.get('next')
    reason = (request.POST.get('reason') or request.POST.get('rejection_reason', '')).strip()
    if not reason:
        messages.error(request, 'A rejection reason is required.')
        if next_url == 'detail':
            return redirect('validation_detail', student_number=profile.student_number)
        return _redirect_after_validation(request)

    reject_student_registration(profile, request.user, reason)

    messages.success(request, f'{profile.user.get_full_name() or profile.user.get_username()} has been rejected.')
    if next_url == 'detail':
        return redirect('validation_detail', student_number=profile.student_number)
    return _redirect_after_validation(request)


# // ==============================================================================
# // VIEW: Recently Reviewed Student Accounts (/validation/reviewed/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def recently_reviewed_list(request):
    """
    // [Admin Controller] Dedicated page listing all reviewed (approved/rejected)
    // student registration accounts with full pagination.
    """
    from django.core.paginator import Paginator

    query = request.GET.get('q', '').strip()
    decision_filter = request.GET.get('decision', '').strip()

    reviewed_qs = (
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status__in=[Profile.APPROVAL_APPROVED, Profile.APPROVAL_REJECTED],
        )
        .select_related('user', 'program', 'program__department', 'approved_by')
        .order_by('-approved_at')
    )

    if query:
        reviewed_qs = reviewed_qs.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(student_number__icontains=query)
        )

    if decision_filter == 'approved':
        reviewed_qs = reviewed_qs.filter(approval_status=Profile.APPROVAL_APPROVED)
    elif decision_filter == 'rejected':
        reviewed_qs = reviewed_qs.filter(approval_status=Profile.APPROVAL_REJECTED)

    paginator = Paginator(reviewed_qs, 20)
    page_number = request.GET.get('page', 1)
    reviewed = paginator.get_page(page_number)

    total_approved = Profile.objects.filter(
        role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_APPROVED
    ).count()
    total_rejected = Profile.objects.filter(
        role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_REJECTED
    ).count()

    return render(request, 'core/admin/recently_reviewed.html', {
        'reviewed': reviewed,
        'query': query,
        'decision_filter': decision_filter,
        'total_approved': total_approved,
        'total_rejected': total_rejected,
    })


# // ==============================================================================
# // VIEW: Batch Approve / Reject — Multiple Students (#3)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def batch_validation_action(request):
    """
    // [Admin Batch Action] Approve or reject multiple pending students at once.
    // POST body: action=approve|reject, ids[]=pk, ids[]=pk, ... reason=<str>
    // Returns JSON: {approved: N, rejected: N, skipped: N, errors: [...]}
    """
    try:
        if not _check_validation_rate_limit(request, max_requests=60, window_seconds=60):
            return JsonResponse({'error': 'Rate limit exceeded. Please wait a moment before sending more batch actions.'}, status=429)

        action = request.POST.get('action', '').strip()
        raw_ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')
        reason = request.POST.get('reason', '').strip()

        if action not in ('approve', 'reject'):
            return JsonResponse({'error': 'Invalid action. Expected approve or reject.'}, status=400)

        if not raw_ids:
            return JsonResponse({'error': 'No student IDs provided for batch processing.'}, status=400)

        if action == 'reject' and not reason:
            return JsonResponse({'error': 'A rejection reason is required for batch rejection.'}, status=400)

        pks = []
        for raw in raw_ids:
            try:
                pks.append(int(raw))
            except (ValueError, TypeError):
                pass

        if not pks:
            return JsonResponse({'error': 'Invalid student IDs provided.'}, status=400)

        profiles = list(Profile.objects.filter(
            pk__in=pks,
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_PENDING,
        ).select_related('user'))

        if not profiles:
            return JsonResponse({
                'approved': 0,
                'rejected': 0,
                'skipped': len(pks),
                'errors': [],
                'message': 'No pending student accounts matched the selection (they may have already been validated).'
            })

        approved_count = 0
        rejected_count = 0
        skipped_count = 0
        errors = []

        # // [Atomicity] Process registrations safely and emit audit events
        with transaction.atomic():
            for profile in profiles:
                try:
                    if action == 'approve':
                        approve_student_registration(profile, request.user)
                        approved_count += 1
                    else:
                        reject_student_registration(profile, request.user, reason)
                        rejected_count += 1
                except Exception as exc:
                    errors.append({'id': profile.pk, 'name': profile.user.get_full_name(), 'error': str(exc)})
                    skipped_count += 1

            if approved_count or rejected_count:
                AuditEvent.objects.create(
                    actor=request.user,
                    action='BATCH_VALIDATION',
                    object_type='Profile',
                    object_id='batch',
                    new_value=(
                        f'Batch {action} on {approved_count + rejected_count} profile(s): '
                        f'{approved_count} approved, {rejected_count} rejected, {skipped_count} skipped'
                    ),
                    reason=reason if reason else ('Batch administrative approval' if action == 'approve' else 'Batch rejection'),
                )

        return JsonResponse({
            'ok': True,
            'approved': approved_count,
            'rejected': rejected_count,
            'skipped': skipped_count,
            'errors': errors,
        })
    except Exception as exc:
        logger.exception('Batch validation error: %s', exc)
        return JsonResponse({'error': f'Batch processing error: {str(exc)}'}, status=500)

