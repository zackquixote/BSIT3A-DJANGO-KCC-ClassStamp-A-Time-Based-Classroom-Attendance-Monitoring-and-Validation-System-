"""
# // ==============================================================================
# // KCC CLASSSTAMP - DEGREE PROGRAM MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Degree Programs & Curriculum Affiliation (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for managing collegiate programs/courses.
# // Handles listing, department cascading filters, AJAX creation/editing with
# // duration validation (1–8 years), and protected soft-deactivation.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md (Phase 2C)
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
from apps.core.models import Department, Profile, Program
from apps.core.serializers import serialize_program
from apps.core.services import (
    create_or_update_program,
    delete_or_deactivate_program,
)


# // ==============================================================================
# // VIEW: Degree Program Directory (/programs/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def program_list(request):
    """
    // [Admin Controller] Degree Program Directory
    // Lists all college programs with parent department, duration, and student count.
    """
    query = request.GET.get('q', '').strip()
    dept_filter = request.GET.get('department', '').strip()

    programs_qs = (
        Program.objects.select_related('department')
        .annotate(
            student_count=Count('profiles', filter=Q(profiles__role=Profile.ROLE_STUDENT), distinct=True),
            y1_count=Count('profiles', filter=Q(profiles__role=Profile.ROLE_STUDENT, profiles__year_level=1), distinct=True),
            y2_count=Count('profiles', filter=Q(profiles__role=Profile.ROLE_STUDENT, profiles__year_level=2), distinct=True),
            y3_count=Count('profiles', filter=Q(profiles__role=Profile.ROLE_STUDENT, profiles__year_level=3), distinct=True),
            y4_count=Count('profiles', filter=Q(profiles__role=Profile.ROLE_STUDENT, profiles__year_level=4), distinct=True),
        )
        .order_by('department__name', 'code')
    )

    if query:
        programs_qs = programs_qs.filter(
            Q(code__icontains=query) |
            Q(name__icontains=query) |
            Q(department__name__icontains=query) |
            Q(department__code__icontains=query)
        )

    if dept_filter:
        programs_qs = programs_qs.filter(department_id=dept_filter)

    paginator = Paginator(programs_qs, 10)
    page_number = request.GET.get('page', 1)
    programs = paginator.get_page(page_number)

    departments = Department.objects.filter(is_active=True).order_by('name')
    total_count = Program.objects.count()
    active_count = Program.objects.filter(is_active=True).count()

    return render(request, 'core/admin/programs.html', {
        'programs': programs,
        'departments': departments,
        'query': query,
        'dept_filter': dept_filter,
        'total_count': total_count,
        'active_count': active_count,
    })


# // ==============================================================================
# // VIEW: Create / Update Degree Program (/programs/save/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def program_save(request):
    """
    // [Admin Controller] Create or Update Academic Program
    // Validates program uniqueness, duration bounds, and parent department.
    """
    prog_id = request.POST.get('id', '').strip()
    dept_id = request.POST.get('department_id', '').strip()
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    years_total = request.POST.get('years_total', '4').strip()
    is_active = request.POST.get('is_active') in ['true', 'on', '1', True]

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if not dept_id:
        err = 'Please select a parent department.'
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('program_list')

    if not code:
        err = 'Program code is required (e.g. BSIT, BSCS).'
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('program_list')

    if not name:
        err = 'Program descriptive name is required.'
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('program_list')

    try:
        years = int(years_total)
    except (ValueError, TypeError):
        err = 'Program duration must be between 1 and 8 years.'
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('program_list')

    try:
        result = create_or_update_program(
            actor=request.user,
            dept_id=int(dept_id),
            code=code,
            name=name,
            years_total=years,
            is_active=is_active,
            prog_id=int(prog_id) if prog_id else None,
        )
    except (ValueError, Department.DoesNotExist) as e:
        err = str(e)
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('program_list')

    prog = result['instance']
    msg = result['message']

    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'message': msg,
            'program': serialize_program(prog),
        })

    messages.success(request, msg)
    return redirect('program_list')


# // ==============================================================================
# // VIEW: Delete / Soft-Deactivate Program (/programs/delete/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def program_delete(request, pk):
    """
    // [Admin Controller] Delete or Deactivate Degree Program
    // Safeguard: If student profiles exist under program, soft-deactivates to prevent FK collision.
    """
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    result = delete_or_deactivate_program(actor=request.user, pk=pk)

    if is_ajax:
        return JsonResponse({'status': 'success', 'message': result['message'], 'type': result['type']})

    messages.success(request, result['message'])
    return redirect('program_list')

