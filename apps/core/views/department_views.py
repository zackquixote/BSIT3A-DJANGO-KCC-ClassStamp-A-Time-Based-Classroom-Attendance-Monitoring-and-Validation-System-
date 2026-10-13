"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC DEPARTMENT MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Institutional Organisational Hierarchy (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for managing collegiate departments.
# // Handles listing, search filtering, AJAX creation/editing with code uniqueness,
# // and protected soft-deactivation when child programs or faculty exist.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md (Phase 2B)
# // ==============================================================================
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import Department, Profile
from apps.core.serializers import serialize_department
from apps.core.services import (
    create_or_update_department,
    delete_or_deactivate_department,
)


# // ==============================================================================
# // VIEW: Academic Department Directory (/departments/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def department_list(request):
    """
    // [Admin Controller] Department Directory
    // Lists all college departments with program counts, faculty loads, and active status.
    """
    query = request.GET.get('q', '').strip()
    departments_qs = (
        Department.objects.annotate(
            program_count=Count('programs', distinct=True),
            faculty_count=Count('profiles', distinct=True),
        )
        .order_by('name')
    )

    if query:
        departments_qs = departments_qs.filter(
            Q(code__icontains=query) | Q(name__icontains=query)
        )

    paginator = Paginator(departments_qs, 10)
    page_number = request.GET.get('page', 1)
    departments = paginator.get_page(page_number)

    total_count = Department.objects.count()
    active_count = Department.objects.filter(is_active=True).count()
    inactive_count = total_count - active_count

    return render(request, 'core/admin/departments.html', {
        'departments': departments,
        'query': query,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
    })


# // ==============================================================================
# // VIEW: Create / Update Academic Department (/departments/save/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def department_save(request):
    """
    // [Admin Controller] Create or Update Academic Department
    // Handles validation for unique department code and name. Emits audit trail.
    """
    dept_id = request.POST.get('id', '').strip()
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    is_active = request.POST.get('is_active') in ['true', 'on', '1', True]

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if not code:
        err = 'Department code is required (e.g. CCS, CITCS).'
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('department_list')

    if not name:
        err = 'Department name is required.'
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('department_list')

    try:
        result = create_or_update_department(
            actor=request.user,
            code=code,
            name=name,
            is_active=is_active,
            dept_id=int(dept_id) if dept_id else None,
        )
    except ValueError as e:
        err = str(e)
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('department_list')

    dept = result['instance']
    msg = result['message']

    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'message': msg,
            'department': serialize_department(dept),
        })

    messages.success(request, msg)
    return redirect('department_list')


# // ==============================================================================
# // VIEW: Delete / Soft-Deactivate Department (/departments/delete/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def department_delete(request, pk):
    """
    // [Admin Controller] Delete or Deactivate Department
    // Safeguard: If programs or teachers are attached, soft-deactivates rather than hard-delete.
    """
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    result = delete_or_deactivate_department(actor=request.user, pk=pk)

    if is_ajax:
        return JsonResponse({'status': 'success', 'message': result['message'], 'type': result['type']})

    messages.success(request, result['message'])
    return redirect('department_list')

