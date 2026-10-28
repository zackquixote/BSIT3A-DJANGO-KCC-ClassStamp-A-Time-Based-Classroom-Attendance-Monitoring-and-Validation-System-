"""
# // ==============================================================================
# // KCC CLASSSTAMP - SUBJECT & CURRICULUM MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Academic Course Catalogue Management (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for the course subject catalogue and
# //   curriculum matrix (program + year level subject mappings).
# //   All state-changing operations are handled via AJAX JSON endpoints for
# //   seamless modal interaction; GET views render the management page.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md (Phase 2D)
# // ==============================================================================
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import AcademicYear, Class, Curriculum, Department, Profile, Program, Subject
from apps.core.serializers import serialize_subject, serialize_subject_summary
from apps.core.serializers.academic_serializers import serialize_curriculum_entry
from apps.core.services import (
    assign_curriculum_subject,
    create_or_update_subject,
    delete_or_deactivate_subject,
    remove_curriculum_entry,
)


# // ==============================================================================
# // VIEW: Subject Catalogue Directory (/subjects/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def subject_list(request):
    """
    // [Admin Controller] Subject Catalogue Management
    // Lists all registered subjects with status filters and create/edit/delete
    // actions. Curriculum (program-year) mappings are managed exclusively on
    // the Programs page matrix builder (A-07).
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    dept_filter = request.GET.get('department', '').strip()
    program_filter = request.GET.get('program', '').strip()

    subjects_qs = (
        Subject.objects.annotate(
            class_count=Count('classes', distinct=True),
            curriculum_count=Count('curriculum_entries', distinct=True),
        )
        .order_by('code')
    )

    if query:
        subjects_qs = subjects_qs.filter(
            Q(code__icontains=query) | Q(name__icontains=query)
        )

    if status_filter == 'active':
        subjects_qs = subjects_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        subjects_qs = subjects_qs.filter(is_active=False)

    if dept_filter:
        subjects_qs = subjects_qs.filter(
            curriculum_entries__program__department_id=dept_filter
        ).distinct()

    if program_filter:
        subjects_qs = subjects_qs.filter(
            curriculum_entries__program_id=program_filter
        ).distinct()

    paginator = Paginator(subjects_qs, 15)
    page_number = request.GET.get('page', 1)
    subjects = paginator.get_page(page_number)

    total_count = Subject.objects.count()
    active_count = Subject.objects.filter(is_active=True).count()
    inactive_count = total_count - active_count
    curriculum_count = Curriculum.objects.count()

    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = (
        Program.objects.filter(is_active=True)
        .select_related('department')
        .order_by('code')
    )

    # Build a dict of subject_id → unique teacher display names for the active AY.
    # One bulk query — no N+1.
    active_ay = AcademicYear.objects.filter(is_active=True).first()
    teachers_by_subject: dict[int, list[str]] = {}
    if active_ay:
        ay_classes = (
            Class.objects
            .filter(academic_year=active_ay, is_active=True)
            .select_related('teacher_profile__user')
            .values_list('subject_id',
                         'teacher_profile__user__first_name',
                         'teacher_profile__user__last_name',
                         'teacher_profile__user__username')
        )
        for sid, fname, lname, uname in ay_classes:
            full = f'{fname or ""} {lname or ""}'.strip() or uname
            teachers_by_subject.setdefault(sid, [])
            if full not in teachers_by_subject[sid]:
                teachers_by_subject[sid].append(full)

    # Attach teacher list directly to each subject object so the template
    # can access it as {{ s.current_teachers }} (avoids dict-subscript limitation).
    for s in subjects:
        s.current_teachers = teachers_by_subject.get(s.id, [])

    return render(request, 'core/admin/subjects.html', {
        'subjects': subjects,
        'query': query,
        'status_filter': status_filter,
        'dept_filter': dept_filter,
        'program_filter': program_filter,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'curriculum_count': curriculum_count,
        'departments': departments,
        'programs': programs,
        'active_ay': active_ay,
    })


# // ==============================================================================
# // AJAX: Create / Update Subject (/subjects/save/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def subject_save(request):
    """
    // [AJAX] Create or update a subject record.
    // POST params: code, name, description, units, is_active, subject_id (optional)
    """
    try:
        subject_id = request.POST.get('subject_id') or None
        if subject_id:
            subject_id = int(subject_id)

        result = create_or_update_subject(
            actor=request.user,
            code=request.POST.get('code', ''),
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            units=request.POST.get('units', '3'),
            is_active=request.POST.get('is_active') == '1',
            subject_id=subject_id,
        )
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'subject': serialize_subject(result['instance']),
        })
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)


# // ==============================================================================
# // AJAX: Delete / Deactivate Subject (/subjects/delete/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def subject_delete(request, pk: int):
    """
    // [AJAX] Delete or soft-deactivate a subject.
    // Protected: If classes or curriculum entries exist, deactivates instead.
    """
    try:
        result = delete_or_deactivate_subject(actor=request.user, pk=pk)
        return JsonResponse({
            'ok': True,
            'type': result['type'],
            'message': result['message'],
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Assign Subject to Program Year Level (/programs/curriculum/assign/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def subject_curriculum_assign(request):
    """
    // [AJAX] Maps a subject to a program + year level + semester in the curriculum
    // matrix. The Programs page matrix builder (A-07) is the only caller.
    // POST params: subject_id, program_id, year_level, semester (optional, default 1)
    """
    try:
        result = assign_curriculum_subject(
            actor=request.user,
            program_id=int(request.POST.get('program_id', 0)),
            year_level=int(request.POST.get('year_level', 0)),
            subject_id=int(request.POST.get('subject_id', 0)),
            semester=int(request.POST.get('semester', 1)),
        )
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'entry': serialize_curriculum_entry(result['instance']),
        })
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)


# // ==============================================================================
# // AJAX: Remove Curriculum Entry (/programs/curriculum/remove/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def subject_curriculum_remove(request, pk: int):
    """
    // [AJAX] Removes a specific curriculum matrix entry.
    """
    try:
        result = remove_curriculum_entry(actor=request.user, pk=pk)
        return JsonResponse({'ok': True, 'message': result['message']})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Subject Lookup for Dropdowns (/api/subjects/lookup/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def subject_lookup_json(request):
    """
    // [AJAX] Returns active subjects as a list for dropdown/autocomplete use.
    """
    subjects = Subject.objects.filter(is_active=True).order_by('code')
    return JsonResponse({
        'subjects': [serialize_subject_summary(s) for s in subjects]
    })
