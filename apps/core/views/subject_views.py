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
from django.db import transaction
from django.db.models import Count, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    Curriculum,
    Department,
    Profile,
    Program,
    Subject,
)
from apps.core.serializers import serialize_subject, serialize_subject_summary
from apps.core.serializers.academic_serializers import serialize_curriculum_entry
from apps.core.services import (
    assign_curriculum_subject,
    create_or_update_subject,
    delete_or_deactivate_subject,
    official_curriculum_filter,
    remove_curriculum_entry,
    set_curriculum_major,
    ensure_draft_version,
    curriculum_version_state,
)


# // ==============================================================================
# // VIEW: Subject Catalogue Directory (/subjects/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def subject_list(request):
    """
    // [Admin Controller] Subject Catalogue Management
    // Lists registered subjects with status filters and create/edit/delete
    // actions. New subjects receive an initial program/year placement here;
    // ongoing curriculum changes are managed in the Programs matrix builder.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    dept_filter = request.GET.get('department', '').strip()
    program_filter = request.GET.get('program', '').strip()
    semester_filter = request.GET.get('semester', '').strip()
    year_filter = request.GET.get('year_level', '').strip()
    sort_mode = request.GET.get('sort', '').strip()
    selected_program = None
    curriculum_scope_filter = official_curriculum_filter('curriculum_entries__')
    program_version_label = ''
    curriculum_scope_version_id = None
    program_curriculum_rows = Curriculum.objects.all()

    if program_filter.isdigit():
        selected_program = Program.objects.filter(
            pk=int(program_filter),
            is_active=True,
        ).first()
        if selected_program:
            display_version = curriculum_version_state(selected_program)['display']
            if display_version:
                scope_entries = Curriculum.objects.filter(
                    program=selected_program,
                    version=display_version,
                )
                if not scope_entries.exists():
                    legacy_entries = Curriculum.objects.filter(
                        program=selected_program,
                        version__isnull=True,
                    )
                    if legacy_entries.exists():
                        curriculum_scope_version_id = None
                        program_curriculum_rows = Curriculum.objects.filter(
                            program=selected_program,
                            version__isnull=True,
                        )
                        curriculum_scope_filter = (
                            Q(curriculum_entries__program_id=selected_program.pk)
                            & Q(curriculum_entries__version__isnull=True)
                        )
                    else:
                        curriculum_scope_version_id = display_version.pk
                        program_curriculum_rows = Curriculum.objects.filter(
                            program=selected_program,
                            version=display_version,
                        )
                        curriculum_scope_filter = (
                            Q(curriculum_entries__program_id=selected_program.pk)
                            & Q(curriculum_entries__version_id=display_version.pk)
                        )
                else:
                    curriculum_scope_version_id = display_version.pk
                    program_curriculum_rows = Curriculum.objects.filter(
                        program=selected_program,
                        version=display_version,
                    )
                    curriculum_scope_filter = (
                        Q(curriculum_entries__program_id=selected_program.pk)
                        & Q(curriculum_entries__version_id=display_version.pk)
                    )
                program_version_label = (
                    f'Draft v{display_version.version_number}'
                    if display_version.status == 'DRAFT'
                    else f'Approved v{display_version.version_number}'
                )
            else:
                curriculum_scope_version_id = None
                program_curriculum_rows = Curriculum.objects.filter(
                    program=selected_program,
                    version__isnull=True,
                )
                curriculum_scope_filter = (
                    Q(curriculum_entries__program_id=selected_program.pk)
                    & Q(curriculum_entries__version__isnull=True)
                )
            program_filter = str(selected_program.pk)
        else:
            program_filter = ''
    elif program_filter:
        program_filter = ''

    if selected_program is None:
        program_curriculum_rows = Curriculum.objects.filter(official_curriculum_filter())
    elif not program_curriculum_rows.exists() and curriculum_scope_version_id is None:
        program_curriculum_rows = Curriculum.objects.filter(
            program=selected_program,
            version__isnull=True,
        )

    if dept_filter:
        program_curriculum_rows = program_curriculum_rows.filter(
            program__department_id=dept_filter,
        )
    curriculum_count = program_curriculum_rows.count()

    placement_rows = program_curriculum_rows
    if semester_filter.isdigit():
        placement_rows = placement_rows.filter(semester=int(semester_filter))
    if year_filter.isdigit():
        placement_rows = placement_rows.filter(year_level=int(year_filter))

    active_filter_labels = []
    if query:
        active_filter_labels.append(f'Search: {query}')
    if dept_filter:
        department = Department.objects.filter(pk=dept_filter).first()
        active_filter_labels.append(
            f'Department: {department.code}' if department else f'Department: {dept_filter}'
        )
    if selected_program:
        active_filter_labels.append(f'Program: {selected_program.code}')
    if year_filter.isdigit():
        active_filter_labels.append(f'Year {int(year_filter)}')
    if semester_filter.isdigit():
        semester_label = dict(Curriculum.SEMESTER_CHOICES).get(int(semester_filter))
        if semester_label:
            active_filter_labels.append(semester_label)
    if status_filter in {'active', 'inactive'}:
        active_filter_labels.append(f'Status: {status_filter.title()}')

    subjects_qs = (
        Subject.objects
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

    # Apply placement filters to one scoped Curriculum queryset so program,
    # year, and semester must all match the same curriculum row.
    if dept_filter or program_filter or semester_filter.isdigit() or year_filter.isdigit():
        subjects_qs = subjects_qs.filter(
            pk__in=placement_rows.values('subject_id')
        )

    # Curriculum order (program -> year -> semester) is how a registrar reads the
    # catalogue; alphabetical order is how you look up a code you already know.
    # Aggregates must live in annotate() before order_by() can reference them.
    if sort_mode == 'placement':
        subjects_qs = subjects_qs.annotate(
            _program_code=Min(
                'curriculum_entries__program__code',
                filter=curriculum_scope_filter,
            ),
            _year_level=Min(
                'curriculum_entries__year_level',
                filter=curriculum_scope_filter,
            ),
            _semester=Min(
                'curriculum_entries__semester',
                filter=curriculum_scope_filter,
            ),
        ).order_by('_program_code', '_year_level', '_semester', 'code')

    paginator = Paginator(subjects_qs, 15)
    page_number = request.GET.get('page', 1)
    subjects = paginator.get_page(page_number)
    previous_page_query = request.GET.copy()
    next_page_query = request.GET.copy()
    if subjects.has_previous():
        previous_page_query['page'] = subjects.previous_page_number()
    if subjects.has_next():
        next_page_query['page'] = subjects.next_page_number()

    # Where each subject on this page sits in the curriculum (program / year /
    # semester). One query for the whole page, not one per row.
    page_subjects = list(subjects)
    placements = {}
    if page_subjects:
        displayed_placements = placement_rows.filter(
            subject_id__in=[s.pk for s in page_subjects]
        )
        for row in (
            displayed_placements
            .values('subject_id', 'program__code', 'year_level', 'semester', 'is_major')
            .order_by('program__code', 'year_level', 'semester')
        ):
            placements.setdefault(row['subject_id'], []).append(row)
    for subject_obj in page_subjects:
        subject_obj.placements = placements.get(subject_obj.pk, [])
        subject_obj.curriculum_count = len(subject_obj.placements)

    total_count = Subject.objects.count()
    active_count = Subject.objects.filter(is_active=True).count()
    inactive_count = total_count - active_count
    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = (
        Program.objects.filter(is_active=True)
        .select_related('department')
        .order_by('code')
    )
    max_year_level = max((program.years_total for program in programs), default=1)

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
        'semester_filter': semester_filter,
        'year_filter': year_filter,
        'sort': sort_mode,
        'active_filter_labels': active_filter_labels,
        'previous_page_query': previous_page_query.urlencode(),
        'next_page_query': next_page_query.urlencode(),
        'placements': placements,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'curriculum_count': curriculum_count,
        'departments': departments,
        'programs': programs,
        'selected_program': selected_program,
        'program_version_label': program_version_label,
        'max_year_level': max_year_level,
        'year_filter_choices': range(1, max_year_level + 1),
        'semester_choices': Curriculum.SEMESTER_CHOICES,
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

        program_id = request.POST.get('curriculum_program_id', '').strip()
        year_level_value = request.POST.get('curriculum_year_level', '').strip()
        semester_value = request.POST.get('curriculum_semester', '').strip()
        major_value = request.POST.get('curriculum_is_major', '').strip()
        is_major = major_value == '1'
        wants_mapping = bool(program_id or year_level_value or semester_value or major_value)

        if not subject_id and not (program_id and year_level_value and semester_value and major_value in {'0', '1'}):
            return JsonResponse({
                'ok': False,
                'error': 'Choose a program, year level, semester, and whether the subject is major or non-major.',
            }, status=400)
        if wants_mapping and not (program_id and year_level_value and semester_value):
            return JsonResponse({
                'ok': False,
                'error': 'Choose a program, year level, and semester to place this subject in a curriculum.',
            }, status=400)
        if wants_mapping and major_value not in {'0', '1'}:
            return JsonResponse({
                'ok': False,
                'error': 'Choose whether this subject is major or non-major.',
            }, status=400)
        if wants_mapping and subject_id:
            return JsonResponse({
                'ok': False,
                'error': 'Curriculum placement can only be added while creating a new subject. Use the curriculum matrix to place an existing subject.',
            }, status=400)

        curriculum_entry = None
        with transaction.atomic():
            if wants_mapping:
                try:
                    program_id_int = int(program_id)
                    year_level = int(year_level_value)
                    semester = int(semester_value)
                except ValueError:
                    return JsonResponse({
                        'ok': False,
                        'error': 'Choose a valid program, year level, and semester.',
                    }, status=400)
                program = get_object_or_404(
                    Program,
                    pk=program_id_int,
                    is_active=True,
                )
                if year_level < 1 or year_level > program.years_total:
                    return JsonResponse({
                        'ok': False,
                        'error': f'Year level must be between 1 and {program.years_total} for {program.code}.',
                    }, status=400)
                if semester not in dict(Curriculum.SEMESTER_CHOICES):
                    return JsonResponse({
                        'ok': False,
                        'error': 'Choose a valid semester.',
                    }, status=400)
                ensure_draft_version(request.user, program)

            result = create_or_update_subject(
                actor=request.user,
                code=request.POST.get('code', ''),
                name=request.POST.get('name', ''),
                description=request.POST.get('description', ''),
                units=request.POST.get('units', '3'),
                is_active=request.POST.get('is_active') == '1',
                subject_id=subject_id,
            )
            if wants_mapping:
                curriculum_result = assign_curriculum_subject(
                    actor=request.user,
                    program_id=program_id_int,
                    year_level=year_level,
                    subject_id=result['instance'].pk,
                    semester=semester,
                    is_major=is_major,
                )
                curriculum_entry = curriculum_result['instance']

        response_message = result['message']
        if curriculum_entry:
            response_message += (
                f' Added to {program.code} Year {year_level}, '
                f'{dict(Curriculum.SEMESTER_CHOICES)[semester]} curriculum'
                f'{" as a major subject" if is_major else ""}.'
            )
        return JsonResponse({
            'ok': True,
            'message': response_message,
            'warning': result.get('warning', ''),
            'subject': serialize_subject(result['instance']),
            'curriculum_entry': (
                serialize_curriculum_entry(curriculum_entry)
                if curriculum_entry else None
            ),
        })
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        import logging

        logging.getLogger(__name__).exception('Unexpected error saving subject')
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
# // AJAX: Toggle Subject Active/Inactive (/subjects/toggle/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def subject_toggle(request, pk: int):
    """
    // [AJAX] Flips the is_active flag of a subject.
    // Safe: can always re-activate; deactivation is blocked while the subject
    // still has active classes in the active academic year. Every state change
    // is written to the audit trail with the previous and new state.
    """
    try:
        subject = get_object_or_404(Subject, pk=pk)
        new_state = not subject.is_active

        if not new_state:
            live_classes = Class.objects.filter(
                subject=subject,
                is_active=True,
                academic_year__is_active=True,
            ).count()
            if live_classes:
                return JsonResponse({
                    'ok': False,
                    'error': (
                        f'{subject.code} still has {live_classes} active class section(s) '
                        'in the active academic year. Deactivate or reassign those sections '
                        'before deactivating the subject.'
                    ),
                }, status=400)

        previous_state = subject.is_active
        subject.is_active = new_state
        subject.save(update_fields=['is_active'])
        action = 'activated' if new_state else 'deactivated'
        AuditEvent.objects.create(
            actor=request.user,
            action='SUBJECT_ACTIVATED' if new_state else 'SUBJECT_DEACTIVATED',
            object_type='Subject',
            object_id=str(subject.pk),
            old_value=f'is_active={previous_state}',
            new_value=f'is_active={new_state}',
            reason=f'Subject {subject.code} {action} by administrator',
        )
        return JsonResponse({
            'ok': True,
            'is_active': new_state,
            'message': f'Subject {subject.code} has been {action}.',
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)




# // ==============================================================================
# // AJAX: Get Single Subject Details (/subjects/get/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def subject_get(request, pk: int):
    """
    // [AJAX] Returns serialized subject details for modal pre-population.
    """
    subject = get_object_or_404(
        Subject.objects.annotate(
            class_count=Count('classes', distinct=True),
            curriculum_count=Count(
                'curriculum_entries',
                filter=official_curriculum_filter('curriculum_entries__'),
                distinct=True,
            ),
        ),
        pk=pk
    )
    return JsonResponse({'ok': True, 'subject': serialize_subject(subject)})


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
            is_major=request.POST.get('is_major') in {'true', '1', 'on'},
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


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def subject_curriculum_major_update(request, pk: int):
    """Update a draft or legacy curriculum entry's major/non-major marker."""
    value = request.POST.get('is_major', '').strip().lower()
    if value not in {'true', 'false', '1', '0', 'on', 'off'}:
        return JsonResponse({
            'ok': False,
            'error': 'Choose whether this curriculum subject is major or non-major.',
        }, status=400)
    is_major = value in {'true', '1', 'on'}
    try:
        result = set_curriculum_major(request.user, pk, is_major)
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'entry': serialize_curriculum_entry(result['instance']),
        })
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


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
