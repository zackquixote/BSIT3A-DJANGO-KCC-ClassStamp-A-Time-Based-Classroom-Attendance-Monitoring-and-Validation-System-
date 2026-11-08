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
from apps.core.models import (
    AcademicYear,
    Class,
    Curriculum,
    CurriculumVersion,
    Department,
    Profile,
    Program,
    Subject,
)
from apps.core.serializers import (
    serialize_curriculum_entry,
    serialize_curriculum_version,
    serialize_program,
)
from apps.core.services import (
    approve_curriculum_draft,
    create_curriculum_draft,
    create_or_update_program,
    curriculum_version_state,
    delete_or_deactivate_program,
    export_program_students_csv,
    latest_curriculum_version,
    official_curriculum_filter,
)
from apps.core.views.helpers import get_program_student_stats


# // ==============================================================================
# // VIEW: Degree Program Directory (/programs/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def program_list(request):
    """
# [Admin Controller] Degree Program Directory
# Lists all college programs with parent department, duration, and student count.
    """
    query = request.GET.get('q', '').strip()
    dept_filter = request.GET.get('department', '').strip()
    open_curriculum_id = request.GET.get('open_curriculum', '').strip()

    programs_qs = (
        Program.objects.select_related('department')
        .annotate(
            # Curriculum coverage: the section wizard draws its subject list from
            # the approved (or legacy) curriculum, so a program with zero official
            # entries cannot build a section.
            curriculum_count=Count(
                'curriculum_entries',
                filter=official_curriculum_filter('curriculum_entries__'),
                distinct=True,
            ),
            draft_version_count=Count(
                'curriculum_versions',
                filter=Q(curriculum_versions__status='DRAFT'),
                distinct=True,
            ),
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

    if open_curriculum_id.isdigit():
        programs_qs = programs_qs.filter(pk=open_curriculum_id)
    else:
        open_curriculum_id = ''

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
        'open_curriculum_id': open_curriculum_id,
    })


# // ==============================================================================
# // VIEW: Create / Update Degree Program (/programs/save/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def program_save(request):
    """
# [Admin Controller] Create or Update Academic Program
# Validates program uniqueness, duration bounds, and parent department.
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
# [Admin Controller] Delete or Deactivate Degree Program
# Safeguard: If student profiles exist under program, soft-deactivates to prevent FK collision.
    """
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    try:
        result = delete_or_deactivate_program(actor=request.user, pk=pk)
    except ValueError as exc:
        if is_ajax:
            return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect('program_list')

    if is_ajax:
        return JsonResponse({'status': 'success', 'message': result['message'], 'type': result['type']})

    messages.success(request, result['message'])
    return redirect('program_list')


# // ==============================================================================
# // VIEW: Program Students Per Year (/programs/<id>/students/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def program_students_per_year(request, program_id):
    """
    // [Admin Controller] Students Per Year by Program
    // Displays a list of approved students enrolled in the program,
    // grouped by year level and department, with pagination for large datasets.
    """
    program = get_object_or_404(
        Program.objects.select_related('department'),
        id=program_id,
    )

    stats = get_program_student_stats(program)

    students_queryset = (
        Profile.objects
        .filter(
            role=Profile.ROLE_STUDENT,
            program=program,
            approval_status=Profile.APPROVAL_APPROVED,
            year_level__isnull=False,
        )
        .select_related('department', 'user')
        .order_by('department__name', 'year_level', 'user__first_name', 'user__last_name')
    )

    search_query = request.GET.get('q', '').strip()
    if search_query:
        students_queryset = students_queryset.filter(
            Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(student_number__icontains=search_query)
            | Q(user__username__icontains=search_query)
        )

    paginator = Paginator(students_queryset, 20)
    page_number = request.GET.get('page', 1)
    students_page = paginator.get_page(page_number)

    context = {
        'program': program,
        'students_page': students_page,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': students_page,
        'paginator': paginator,
        'search_query': search_query,
        **stats,
    }

    return render(request, 'core/admin/program_students_per_year.html', context)


# // ==============================================================================
# // AJAX: CSV Export (/programs/export-csv/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def program_students_csv_export(request, program_id):
    """
    // [Admin Controller] Export Students CSV
    // Exports all approved students for the program to CSV format.
    """
    program = get_object_or_404(
        Program.objects.select_related('department'),
        id=program_id,
    )
    return export_program_students_csv(program)


# // ==============================================================================
# // AJAX: Program Curriculum Matrix JSON (/programs/<id>/curriculum/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def program_curriculum_list(request, program_id):
    """
    // [Admin AJAX Controller] A-07 Program-Centric Curriculum Matrix
    // Returns the full Year x Semester curriculum grid for one program plus the
    // pool of active subjects available for assignment. The grid shows the
    // current draft when one exists, otherwise the newest approved version.
    """
    program = get_object_or_404(Program.objects.select_related('department'), pk=program_id)

    requested_version = request.GET.get('version_id', '').strip()

    version_state = curriculum_version_state(program)
    display_version = version_state['display']

    # Every version (draft, approved, archived) is a selectable "batch": its
    # effective_from term is the cohort's entering school year. Let the admin
    # view any batch's matrix, not just the current display version.
    all_versions = list(
        CurriculumVersion.objects.filter(program=program)
        .select_related('effective_from', 'program', 'created_by', 'approved_by')
        .order_by('-version_number')
    )
    if requested_version.isdigit():
        wanted = int(requested_version)
        for candidate in all_versions:
            if candidate.pk == wanted:
                display_version = candidate
                break

    is_legacy = display_version is None

    entries_qs = Curriculum.objects.filter(program=program)
    if display_version is not None:
        entries_qs = entries_qs.filter(version=display_version)
        # A partially migrated program may have official rows without a version
        # while its version snapshot is empty. Treat those as the grid source.
        if not entries_qs.exists():
            legacy_qs = Curriculum.objects.filter(
                program=program,
                version__isnull=True,
            )
            if legacy_qs.exists():
                entries_qs = legacy_qs
                is_legacy = True

    entries = (
        entries_qs.select_related('subject', 'program', 'version')
        .order_by('year_level', 'semester', 'subject__code')
    )
    subjects = (
        Subject.objects.filter(is_active=True)
        .order_by('code')
    )
    terms = AcademicYear.objects.order_by('-starts_on')

    active_ay = AcademicYear.objects.filter(is_active=True).first()
    teachers_by_subject = {}
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

    return JsonResponse({
        'ok': True,
        'program': serialize_program(program),
        'years_total': program.years_total,
        'semesters': [{'value': v, 'label': l} for v, l in Curriculum.SEMESTER_CHOICES],
        'entries': [
            serialize_curriculum_entry(e, teachers=teachers_by_subject.get(e.subject_id, []))
            for e in entries
        ],
        'subjects': [
            {'id': s.id, 'code': s.code, 'name': s.name}
            for s in subjects
        ],
        'version': (
            serialize_curriculum_version(display_version)
            if display_version is not None else None
        ),
        'draft_version': (
            serialize_curriculum_version(version_state['draft'])
            if version_state['draft'] is not None else None
        ),
        'approved_version': (
            serialize_curriculum_version(version_state['approved'])
            if version_state['approved'] is not None else None
        ),
        'versions': [serialize_curriculum_version(v) for v in all_versions],
        'selected_version_id': (
            display_version.pk if display_version is not None else None
        ),
        'can_edit': display_version is None or display_version.status == CurriculumVersion.STATUS_DRAFT,
        'is_legacy': is_legacy,
        'terms': [
            {'id': term.id, 'name': term.name, 'is_active': term.is_active}
            for term in terms
        ],
    })


# // ==============================================================================
# // AJAX: Create Curriculum Draft (/programs/<id>/curriculum/draft/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def program_curriculum_draft_create(request, program_id):
    """Clone the latest approved curriculum into a new editable draft."""
    program = get_object_or_404(Program.objects.select_related('department'), pk=program_id)
    try:
        result = create_curriculum_draft(request.user, program)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    return JsonResponse({
        'ok': True,
        'created': result['created'],
        'message': result['message'],
        'version': serialize_curriculum_version(result['instance']),
    })


# // ==============================================================================
# // AJAX: Approve Curriculum Draft (/programs/<id>/curriculum/approve/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def program_curriculum_approve(request, program_id):
    """Approve the program's draft and archive the outgoing approved version."""
    program = get_object_or_404(Program.objects.select_related('department'), pk=program_id)
    version_id = request.POST.get('version_id', '').strip()
    effective_from = request.POST.get('effective_from', '').strip()

    version = latest_curriculum_version(
        program,
        statuses=(CurriculumVersion.STATUS_DRAFT,),
    )
    if version_id:
        version = get_object_or_404(
            CurriculumVersion,
            pk=version_id,
            program=program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
    if version is None:
        return JsonResponse(
            {'ok': False, 'error': 'This program has no draft curriculum to approve.'},
            status=400,
        )

    effective_from_id = None
    if effective_from:
        if not effective_from.isdigit():
            return JsonResponse(
                {'ok': False, 'error': 'Select a valid effective academic term.'},
                status=400,
            )
        effective_from_id = int(effective_from)

    try:
        result = approve_curriculum_draft(
            request.user,
            version,
            effective_from=effective_from_id,
        )
    except (ValueError, AcademicYear.DoesNotExist) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    return JsonResponse({
        'ok': True,
        'message': result['message'],
        'version': serialize_curriculum_version(result['instance']),
    })
