"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC YEAR & TERM MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Institutional Academic Calendar Administration (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for creating and managing academic
# //   year / semester term windows. Enforces the single-active-term invariant
# //   via atomic transactions in the service layer.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md (Phase 2F)
# // ==============================================================================
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import AcademicYear, Profile
from apps.core.serializers.academic_serializers import serialize_academic_year
from apps.core.services import (
    create_or_update_academic_year,
    delete_or_deactivate_academic_year,
    set_active_academic_year,
)


# // ==============================================================================
# // VIEW: Academic Year & Term Directory (/academic-years/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def academic_year_list(request):
    """
    // [Admin Controller] Academic Year & Term Management
    // Lists all academic terms ordered by date, with class section counts,
    // active status indicator, and CRUD modal controls.
    """
    academic_years_qs = (
        AcademicYear.objects.annotate(
            class_count=Count('classes', distinct=True),
        )
        .order_by('-starts_on')
    )

    paginator = Paginator(academic_years_qs, 15)
    page_number = request.GET.get('page', 1)
    academic_years = paginator.get_page(page_number)

    active_term = AcademicYear.objects.filter(is_active=True).first()
    total_count = AcademicYear.objects.count()
    active_class_count = (
        AcademicYear.objects.filter(is_active=True)
        .annotate(c=Count('classes')).first()
    )
    active_class_count = active_class_count.c if active_class_count else 0

    today = timezone.localdate()
    days_remaining = None
    if active_term and active_term.ends_on:
        delta = active_term.ends_on - today
        days_remaining = max(delta.days, 0)

    return render(request, 'core/admin/academic_years.html', {
        'academic_years': academic_years,
        'active_term': active_term,
        'total_count': total_count,
        'active_class_count': active_class_count,
        'days_remaining': days_remaining,
    })


# // ==============================================================================
# // AJAX: Create / Update Academic Year (/academic-years/save/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_save(request):
    """
    // [AJAX] Create or update an academic year / term.
    // POST params: name, starts_on, ends_on, is_active, ay_id (optional)
    """
    try:
        ay_id = request.POST.get('ay_id') or None
        if ay_id:
            ay_id = int(ay_id)

        result = create_or_update_academic_year(
            actor=request.user,
            name=request.POST.get('name', ''),
            starts_on=request.POST.get('starts_on', ''),
            ends_on=request.POST.get('ends_on', ''),
            is_active=request.POST.get('is_active') == '1',
            ay_id=ay_id,
        )
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'academic_year': serialize_academic_year(result['instance']),
        })
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)


# // ==============================================================================
# // AJAX: Set Active Academic Year (/academic-years/set-active/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_set_active(request, pk: int):
    """
    // [AJAX] Promote the given academic year as the current active institutional term.
    // Atomically deactivates all other terms in the same transaction.
    """
    try:
        result = set_active_academic_year(actor=request.user, pk=pk)
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'academic_year': serialize_academic_year(result['instance']),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Delete / Deactivate Academic Year (/academic-years/delete/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_delete(request, pk: int):
    """
    // [AJAX] Delete or soft-deactivate an academic year term.
    // Protected: If classes are scheduled under this term, deactivates instead.
    """
    try:
        result = delete_or_deactivate_academic_year(actor=request.user, pk=pk)
        return JsonResponse({
            'ok': True,
            'type': result['type'],
            'message': result['message'],
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Get Single Academic Year (/academic-years/get/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def academic_year_get(request, pk: int):
    """
    // [AJAX] Returns serialized academic year for modal pre-population.
    """
    ay = get_object_or_404(
        AcademicYear.objects.annotate(class_count=Count('classes', distinct=True)),
        pk=pk
    )
    return JsonResponse({'ok': True, 'academic_year': serialize_academic_year(ay)})
