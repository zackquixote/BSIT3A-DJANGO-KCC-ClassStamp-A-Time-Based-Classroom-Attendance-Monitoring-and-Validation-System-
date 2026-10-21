"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT ACCOUNT VALIDATION & DOSSIER REVIEW CONTROLLERS
# // ==============================================================================
# // Subsystem: Registrar Identity Verification & Approval Workflow (RBAC: ADMIN ONLY)
# // Description: Administrative queue for reviewing pending self-registered students,
# // inspecting submitted credentials/ID proofs, approving and provisioning dynamic
# // QR secrets, and issuing official rejection notices with audit tracking.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md (Phase 2A)
# // ==============================================================================
"""

import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import AuditEvent, Department, Profile, Program
from apps.core.services import (
    approve_student_registration,
    reject_student_registration,
)


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
    referer = request.META.get('HTTP_REFERER')
    if referer and '/validation/' in referer:
        return redirect(referer)
    return redirect('validation_hub')


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
        referer = request.META.get('HTTP_REFERER')
        if referer and '/validation/' in referer:
            return redirect(referer)
        return redirect('validation_hub')

    reject_student_registration(profile, request.user, reason)

    messages.success(request, f'{profile.user.get_full_name() or profile.user.get_username()} has been rejected.')
    if next_url == 'detail':
        return redirect('validation_detail', student_number=profile.student_number)
    referer = request.META.get('HTTP_REFERER')
    if referer and '/validation/' in referer:
        return redirect(referer)
    return redirect('validation_hub')


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
