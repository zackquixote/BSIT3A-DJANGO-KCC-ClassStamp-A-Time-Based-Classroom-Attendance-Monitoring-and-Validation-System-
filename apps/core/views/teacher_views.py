"""
# // ==============================================================================
# // KCC CLASSSTAMP - TEACHER & FACULTY MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Faculty Roster Administration (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for managing faculty accounts,
# //   provisioning new teacher accounts directly, and viewing teaching loads.
# //   Admin bypasses public registration by directly creating approved accounts.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md (Phase 2E)
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import AcademicYear, Class, Department, Profile, Subject
from apps.core.serializers.teacher_serializers import serialize_teacher, serialize_teacher_summary
from apps.core.services import (
    delete_or_deactivate_teacher,
    provision_teacher_account,
    toggle_teacher_active,
    update_teacher_profile,
)

User = get_user_model()


# // ==============================================================================
# // VIEW: Teacher & Faculty Roster Directory (/teachers/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def teacher_list(request):
    """
    // [Admin Controller] Teacher & Faculty Management
    // Lists all faculty members with department affiliation, class loads,
    // and account controls. Supports search and department filtering.
    """
    query = request.GET.get('q', '').strip()
    dept_filter = request.GET.get('department', '').strip()
    status_filter = request.GET.get('status', '').strip()

    teachers_qs = (
        Profile.objects.filter(role=Profile.ROLE_TEACHER)
        .select_related('user', 'department')
        .annotate(class_count=Count('taught_classes', distinct=True))
        .prefetch_related('taught_classes__subject', 'taught_classes__academic_year')
        .order_by('user__last_name', 'user__first_name')
    )

    if query:
        teachers_qs = teachers_qs.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
        )

    if dept_filter:
        teachers_qs = teachers_qs.filter(department_id=dept_filter)

    if status_filter == 'active':
        teachers_qs = teachers_qs.filter(user__is_active=True)
    elif status_filter == 'inactive':
        teachers_qs = teachers_qs.filter(user__is_active=False)

    paginator = Paginator(teachers_qs, 15)
    page_number = request.GET.get('page', 1)
    teachers = paginator.get_page(page_number)

    total_count = Profile.objects.filter(role=Profile.ROLE_TEACHER).count()
    active_count = Profile.objects.filter(role=Profile.ROLE_TEACHER, user__is_active=True).count()
    inactive_count = total_count - active_count
    dept_count = (
        Profile.objects.filter(role=Profile.ROLE_TEACHER, department__isnull=False)
        .values('department').distinct().count()
    )
    active_load_count = (
        Profile.objects.filter(role=Profile.ROLE_TEACHER)
        .annotate(c=Count('taught_classes'))
        .filter(c__gt=0)
        .count()
    )

    departments = Department.objects.filter(is_active=True).order_by('code')
    all_subjects = Subject.objects.filter(is_active=True).order_by('code')
    all_academic_years = AcademicYear.objects.all().order_by('-starts_on')

    return render(request, 'core/admin/teachers.html', {
        'teachers': teachers,
        'query': query,
        'dept_filter': dept_filter,
        'status_filter': status_filter,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'dept_count': dept_count,
        'active_load_count': active_load_count,
        'departments': departments,
        'all_subjects': all_subjects,
        'all_academic_years': all_academic_years,
    })


# // ==============================================================================
# // AJAX: Provision New Teacher Account (/teachers/create/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def teacher_create(request):
    """
    // [AJAX] Admin directly provisions a Teacher account (bypasses registration queue).
    // POST params: username, email, first_name, last_name, dept_id, password (optional)
    """
    try:
        result = provision_teacher_account(
            actor=request.user,
            username=request.POST.get('username', ''),
            email=request.POST.get('email', ''),
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            dept_id=int(request.POST.get('dept_id', 0)),
            password=request.POST.get('password') or None,
            is_active=True,
        )
        resp = {
            'ok': True,
            'message': result['message'],
            'teacher': serialize_teacher_summary(result['profile']),
        }
        if result.get('generated_password'):
            resp['generated_password'] = result['generated_password']
        return JsonResponse(resp)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)


# // ==============================================================================
# // AJAX: Update Teacher Profile (/teachers/update/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def teacher_update(request, pk: int):
    """
    // [AJAX] Update faculty name, email, department, active status, and optional password.
    // POST params: first_name, last_name, email, dept_id, is_active, password (optional)
    """
    try:
        result = update_teacher_profile(
            actor=request.user,
            profile_id=pk,
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            email=request.POST.get('email', ''),
            dept_id=int(request.POST.get('dept_id', 0)),
            is_active=request.POST.get('is_active') == '1',
            password=request.POST.get('password') or None,
        )
        return JsonResponse({
            'ok': True,
            'message': result['message'],
        })
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)


# // ==============================================================================
# // AJAX: Toggle Teacher Active Status (/teachers/toggle/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def teacher_toggle(request, pk: int):
    """
    // [AJAX] Quickly enable or disable a faculty account.
    """
    try:
        result = toggle_teacher_active(actor=request.user, profile_id=pk)
        return JsonResponse({
            'ok': True,
            'is_active': result['is_active'],
            'message': result['message'],
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Delete / Deactivate Teacher (/teachers/delete/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def teacher_delete(request, pk: int):
    """
    // [AJAX] Delete or soft-deactivate a teacher account.
    // Protected: If assigned classes exist, deactivates instead.
    """
    try:
        result = delete_or_deactivate_teacher(actor=request.user, profile_id=pk)
        return JsonResponse({
            'ok': True,
            'type': result['type'],
            'message': result['message'],
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Get Single Teacher Details (/teachers/get/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def teacher_get(request, pk: int):
    """
    // [AJAX] Returns detailed teacher profile including assigned class sections.
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user', 'department')
        .annotate(class_count=Count('taught_classes', distinct=True)),
        pk=pk,
        role=Profile.ROLE_TEACHER,
    )
    return JsonResponse({'ok': True, 'teacher': serialize_teacher(profile)})


# // ==============================================================================
# // AJAX: Assign Class Section / Teaching Load (/teachers/<pk>/assign-class/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def teacher_assign_class_ajax(request, pk: int):
    """
    // [AJAX] Assigns a class section offering to a teacher's teaching load.
    // Creates a new Class record or reassigns an existing Class section.
    """
    teacher_profile = get_object_or_404(Profile, pk=pk, role=Profile.ROLE_TEACHER)

    academic_year_id = request.POST.get('academic_year_id')
    subject_id = request.POST.get('subject_id')
    class_code = request.POST.get('class_code', '').strip().upper()
    grace_minutes = request.POST.get('grace_minutes', 10)
    capacity = request.POST.get('capacity', 45)

    if not academic_year_id or not subject_id or not class_code:
        return JsonResponse({'ok': False, 'error': 'Academic Term, Subject, and Section Code are required.'}, status=400)

    academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)
    subject = get_object_or_404(Subject, pk=subject_id)

    try:
        grace_minutes = int(grace_minutes)
    except (ValueError, TypeError):
        grace_minutes = 10

    try:
        capacity = int(capacity) if capacity else 45
    except (ValueError, TypeError):
        capacity = 45

    # Check if this class code already exists in this academic year
    existing_class = Class.objects.filter(academic_year=academic_year, class_code=class_code).first()
    teacher_name = teacher_profile.user.get_full_name() or teacher_profile.user.username

    if existing_class:
        if existing_class.teacher_profile == teacher_profile:
            return JsonResponse({'ok': False, 'error': f'Class {class_code} is already assigned to {teacher_name}.'}, status=400)
        old_teacher = existing_class.teacher_profile.user.get_full_name() or existing_class.teacher_profile.user.username
        existing_class.teacher_profile = teacher_profile
        existing_class.subject = subject
        existing_class.grace_minutes = grace_minutes
        existing_class.capacity = capacity
        existing_class.is_active = True
        existing_class.save()
        msg = f"Class {class_code} ({subject.code}) reassigned from {old_teacher} to {teacher_name}."
        target_class = existing_class
    else:
        target_class = Class.objects.create(
            academic_year=academic_year,
            subject=subject,
            teacher_profile=teacher_profile,
            class_code=class_code,
            grace_minutes=grace_minutes,
            capacity=capacity,
            is_active=True
        )
        msg = f"Class {class_code} ({subject.code}) successfully assigned to {teacher_name}."

    return JsonResponse({
        'ok': True,
        'message': msg,
        'class': {
            'id': target_class.id,
            'class_code': target_class.class_code,
            'subject_code': subject.code,
            'subject_name': subject.name,
            'academic_year': academic_year.name,
        }
    })


# // ==============================================================================
# // AJAX: Unassign / Remove Class from Teaching Load (/teachers/<pk>/unassign-class/<class_id>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def teacher_unassign_class_ajax(request, pk: int, class_id: int):
    """
    // [AJAX] Removes a class from a faculty member's active teaching load.
    // Safeguard: If attendance sessions exist, archives the class section rather than deleting.
    """
    teacher_profile = get_object_or_404(Profile, pk=pk, role=Profile.ROLE_TEACHER)
    class_obj = get_object_or_404(Class, pk=class_id, teacher_profile=teacher_profile)

    has_sessions = class_obj.slots.filter(sessions__isnull=False).exists()
    has_enrollments = class_obj.enrollments.exists()

    if has_sessions or has_enrollments:
        class_obj.is_active = False
        class_obj.save(update_fields=['is_active'])
        return JsonResponse({
            'ok': True,
            'message': f"Class section {class_obj.class_code} was archived/deactivated because it already has attendance or enrollment records."
        })
    else:
        code = class_obj.class_code
        class_obj.delete()
        return JsonResponse({
            'ok': True,
            'message': f"Class {code} removed from faculty teaching load."
        })

