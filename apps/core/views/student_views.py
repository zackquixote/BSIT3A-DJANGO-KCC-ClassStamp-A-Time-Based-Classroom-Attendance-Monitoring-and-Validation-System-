"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT DIRECTORY & BATCH ROSTER INGESTION CONTROLLERS
# // ==============================================================================
# // Subsystem: Student Masterlist, Section Roster Directory & Bulk CSV Import
# // Description: Administrative controllers for exploring registered students with
# // multi-attribute filters (Department, Program, Standing Year, Class Section),
# // scalable page sizing (e.g. 40-student section roster view), CSV exports,
# // and atomic bulk CSV roster ingestion with automatic 64-char QR secret creation.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md
# // ==============================================================================
"""

import csv
import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import role_required
from apps.core.models import AcademicYear, AuditEvent, Class, Department, Profile, Program
from apps.core.services import (
    build_student_queryset,
    export_student_directory_csv,
    export_student_import_sample_csv,
    import_students_from_csv,
    promote_students,
)

User = get_user_model()


# // ==============================================================================
# // VIEW: Student Directory & Masterlist (/students/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def student_directory(request):
    """
    // [Admin Controller] Registered Students Directory & Masterlist
    // Provides a comprehensive, filterable roster of all registered students
    // across College Departments, Programs/Courses, Year Levels, and Class Sections.
    // Supports dynamic page sizing (e.g., 40 per page for full section view).
    """
    dept_id = request.GET.get('department', '').strip()
    prog_id = request.GET.get('program', '').strip()
    year_level = request.GET.get('year_level', '').strip()
    section = request.GET.get('section', '').strip()
    status = request.GET.get('status', '').strip()
    q = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', '-created_at').strip()

    filter_params = {
        'department': dept_id,
        'program': prog_id,
        'year_level': year_level,
        'section': section,
        'status': status,
        'q': q,
        'sort': sort,
    }
    students_qs = build_student_queryset(filter_params)

    # Filter dropdown choices
    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = Program.objects.filter(is_active=True).select_related('department').order_by('code')
    active_ay = AcademicYear.objects.filter(is_active=True).first()
    sections_qs = Class.objects.filter(is_active=True)
    if active_ay:
        sections_qs = sections_qs.filter(academic_year=active_ay)
    sections = sections_qs.values_list('class_code', flat=True).distinct().order_by('class_code')

    # Aggregate counts across all registered students
    total_students = Profile.objects.filter(role=Profile.ROLE_STUDENT).count()
    approved_count = Profile.objects.filter(role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_APPROVED).count()
    pending_count = Profile.objects.filter(role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_PENDING).count()
    rejected_count = Profile.objects.filter(role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_REJECTED).count()

    filtered_count = students_qs.count()

    # Dynamic year level counts follow the same filters as the listing itself
    year_count_base = students_qs
    count_all_years = year_count_base.count()
    count_y1 = year_count_base.filter(year_level=1).count()
    count_y2 = year_count_base.filter(year_level=2).count()
    count_y3 = year_count_base.filter(year_level=3).count()
    count_y4 = year_count_base.filter(year_level=4).count()

    per_page_param = request.GET.get('per_page', '15').strip()
    try:
        per_page = int(per_page_param)
        if per_page not in [15, 25, 40, 50, 100, 200]:
            per_page = 15
    except ValueError:
        if per_page_param.lower() == 'all':
            per_page = 1000
        else:
            per_page = 15

    paginator = Paginator(students_qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'students': page_obj,
        'page_obj': page_obj,
        'departments': departments,
        'programs': programs,
        'sections': sections,
        'year_levels': [1, 2, 3, 4],
        'selected_dept': dept_id,
        'selected_prog': prog_id,
        'selected_year': year_level,
        'selected_section': section,
        'selected_status': status,
        'query': q,
        'selected_sort': sort,
        'per_page': per_page,
        'per_page_param': per_page_param,
        'total_students': total_students,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'filtered_count': filtered_count,
        'count_all_years': count_all_years,
        'count_y1': count_y1,
        'count_y2': count_y2,
        'count_y3': count_y3,
        'count_y4': count_y4,
    }
    return render(request, 'core/admin/student_directory.html', context)


# // ==============================================================================
# // AJAX: In-Place Student Profile Editor (A-03)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def student_profile_update_ajax(request):
    """
    // [AJAX] Edit student masterlist fields without CLI access (A-03).
    // Editable: student number, full name, department, program, year level.
    // Optional: reset the student's TOTP QR secret seed (security rotation).
    """
    try:
        profile = Profile.objects.select_related('user', 'program__department').get(
            pk=request.POST.get('student_id'), role=Profile.ROLE_STUDENT,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'errors': {'student_id': 'Student not found.'}}, status=404)

    student_number = request.POST.get('student_number', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    dept_id = request.POST.get('department', '').strip()
    prog_id = request.POST.get('program', '').strip()
    year_level = request.POST.get('year_level', '').strip()
    reset_qr = request.POST.get('reset_qr') == '1'

    errors = {}

    if not student_number:
        errors['student_number'] = 'Student number is required.'
    elif Profile.objects.filter(
        role=Profile.ROLE_STUDENT, student_number=student_number
    ).exclude(pk=profile.pk).exists():
        errors['student_number'] = 'Student number is already in use by another student.'

    if not first_name or not last_name:
        errors['full_name'] = 'First name and last name are both required.'

    try:
        year = int(year_level)
        if year < 1 or year > 4:
            raise ValueError
    except (ValueError, TypeError):
        errors['year_level'] = 'Year level must be between 1 and 4.'
        year = None

    program = None
    if prog_id:
        try:
            program = Program.objects.get(pk=prog_id, is_active=True)
        except (Program.DoesNotExist, ValueError, TypeError):
            errors['program'] = 'Selected program does not exist.'

    department = None
    if dept_id:
        try:
            department = Department.objects.get(pk=dept_id, is_active=True)
        except (Department.DoesNotExist, ValueError, TypeError):
            errors['department'] = 'Selected department does not exist.'

    if program and department and program.department_id != department.pk:
        errors['program'] = 'Selected program does not belong to the selected department.'
    if program and year is not None and year > program.years_total:
        errors['year_level'] = f'Year level cannot exceed {program.years_total} for {program.code}.'

    if errors:
        return JsonResponse({'status': 'error', 'errors': errors}, status=400)

    user = profile.user
    old_snapshot = (
        f'student_number={profile.student_number}, name={user.get_full_name()}, '
        f'program={profile.program.code if profile.program else "-"}, year={profile.year_level}'
    )

    user.first_name = first_name
    user.last_name = last_name
    user.save(update_fields=['first_name', 'last_name'])

    profile.student_number = student_number
    if department is not None:
        profile.department = department
    if program is not None:
        profile.program = program
    if year is not None:
        profile.year_level = year

    qr_reset = False
    if reset_qr:
        profile.qr_secret = secrets.token_hex(32)
        qr_reset = True
        AuditEvent.objects.create(
            actor=request.user,
            action='STUDENT_QR_RESET',
            object_type='Profile',
            object_id=str(profile.pk),
            new_value=f'TOTP QR secret rotated for {student_number}',
            reason='Security reset requested by administrator via student directory',
        )

    profile.save(update_fields=['student_number', 'department', 'program', 'year_level', 'qr_secret'])

    AuditEvent.objects.create(
        actor=request.user,
        action='STUDENT_PROFILE_UPDATE',
        object_type='Profile',
        object_id=str(profile.pk),
        old_value=old_snapshot,
        new_value=(
            f'student_number={profile.student_number}, name={user.get_full_name()}, '
            f'program={profile.program.code if profile.program else "-"}, year={profile.year_level}'
        ),
        reason='In-place edit via student directory (A-03)',
    )

    return JsonResponse({
        'status': 'success',
        'student_number': profile.student_number,
        'full_name': user.get_full_name() or profile.student_number,
        'department_code': profile.program.department.code if profile.program and profile.program.department else None,
        'program_code': profile.program.code if profile.program else None,
        'program_name': profile.program.name if profile.program else None,
        'year_level': profile.year_level,
        'qr_reset': qr_reset,
    })


# // ==============================================================================
# // AJAX: End-of-Year Batch Student Promotion (A-06)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def student_promote_all(request):
    """
    // [AJAX] 1-click batch advance of all approved students to the next year
    // level, capped at each program's duration. Fully audited.
    """
    result = promote_students(request.user)
    return JsonResponse({
        'status': 'success',
        'promoted_count': result['promoted_count'],
        'message': result['message'],
    })


# // ==============================================================================
# // AJAX: Student TOTP QR Secret Reset (A-13)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def student_qr_reset_ajax(request):
    """
    // [AJAX] Rotates a single student's TOTP QR seed. Invalidates any issued
    // offline badges and the student's current QR badge immediately.
    """
    try:
        profile = Profile.objects.select_related('user').get(
            pk=request.POST.get('student_id'), role=Profile.ROLE_STUDENT,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'error': 'Student not found.'}, status=404)

    profile.qr_secret = secrets.token_hex(32)
    profile.save(update_fields=['qr_secret', 'updated_at'])
    profile.offline_badges.filter(consumed_at__isnull=True).delete()

    AuditEvent.objects.create(
        actor=request.user,
        action='STUDENT_QR_RESET',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'TOTP QR secret rotated for {profile.student_number}',
        reason='Security reset requested by administrator (A-13)',
    )

    return JsonResponse({
        'status': 'success',
        'message': f'QR secret rotated for {profile.student_number}. The old badge is now invalid.',
    })


# // ==============================================================================
# // VIEW: Student Directory CSV Export (/students/export-csv/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def student_directory_export_csv(request):
    """
    // Exports the currently filtered student masterlist as a downloadable CSV.
    """
    return export_student_directory_csv(request.GET)


# // ==============================================================================
# // VIEW: Student Bulk CSV Import (/students/import/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def student_directory_import_csv(request):
    """
    // [Admin Controller] Bulk CSV Student Ingestion (A-10 3-step: upload → preview → confirm)
    // Allows importing entire cohort/section rosters (e.g. 40 students per section)
    // in an atomic database transaction. Generates user accounts, creates student
    // profiles with 64-char QR secrets, auto-approves accounts, and links class sections.
    """
    base_context = {
        'departments': Department.objects.filter(is_active=True).order_by('name'),
        'programs': Program.objects.filter(is_active=True).select_related('department').order_by('code'),
        'classes': Class.objects.filter(is_active=True).order_by('class_code'),
    }

    if request.method == 'GET':
        return render(request, 'core/admin/student_import.html', base_context)

    default_password = request.POST.get('default_password', 'KccStudent2026!').strip() or 'KccStudent2026!'
    auto_approve = request.POST.get('auto_approve') == 'on'
    target_class_id = request.POST.get('target_class_id', '').strip()

    target_class = None
    if target_class_id:
        target_class = Class.objects.filter(pk=target_class_id, is_active=True).first()

    is_confirm = request.POST.get('confirm') == '1'
    is_preview = request.POST.get('preview') == '1'

    # // Step 3: confirm executes the import on the previewed CSV text
    if is_confirm:
        csv_text = request.POST.get('csv_text', '')
        if not csv_text.strip():
            messages.error(request, 'Import preview expired. Please re-upload the CSV file.')
            return redirect('student_directory_import_csv')
        decoded_file = csv_text.splitlines()
    else:
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Please select a CSV file to upload.')
            return redirect('student_directory_import_csv')
        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'Uploaded file must have a .csv extension.')
            return redirect('student_directory_import_csv')
        try:
            csv_text = csv_file.read().decode('utf-8-sig')
        except Exception as e:
            messages.error(request, f'Failed to parse CSV file: {str(e)}')
            return redirect('student_directory_import_csv')
        decoded_file = csv_text.splitlines()

    try:
        reader = csv.DictReader(decoded_file)
        fieldnames = reader.fieldnames
    except Exception as e:
        messages.error(request, f'Failed to parse CSV file: {str(e)}')
        return redirect('student_directory_import_csv')

    if not fieldnames:
        messages.error(request, 'CSV file contains no columns or header row.')
        return redirect('student_directory_import_csv')

    # // Step 2: dry-run preview — validate every row, write nothing
    if is_preview:
        result = import_students_from_csv(
            reader=reader,
            actor=request.user,
            default_password=default_password,
            auto_approve=auto_approve,
            target_class=target_class,
            dry_run=True,
        )
        return render(request, 'core/admin/student_import.html', {
            **base_context,
            'preview': {
                'rows': result['rows'],
                'csv_text': csv_text,
                'default_password': default_password,
                'auto_approve': auto_approve,
                'target_class_id': target_class_id,
                'valid_count': result['created_count'],
                'invalid_count': result['skipped_count'],
            },
        })

    result = import_students_from_csv(
        reader=reader,
        actor=request.user,
        default_password=default_password,
        auto_approve=auto_approve,
        target_class=target_class,
    )
    created_count = result['created_count']
    skipped_count = result['skipped_count']
    errors = result['errors']

    if created_count > 0:
        messages.success(
            request,
            f'Bulk Import Successful! Provisioned {created_count} student accounts.'
        )
    if errors:
        messages.warning(
            request,
            f'{skipped_count} row(s) were skipped due to existing records or validation warnings.'
        )

    return render(request, 'core/admin/student_import.html', {
        **base_context,
        'summary': {
            'created_count': created_count,
            'skipped_count': skipped_count,
            'errors': errors[:50],
        }
    })


# // ==============================================================================
# // VIEW: Download Sample Student CSV Import Template
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def student_import_sample_csv(request):
    """
    // Generates a downloadable CSV template with sample section rows for bulk import.
    """
    return export_student_import_sample_csv()
