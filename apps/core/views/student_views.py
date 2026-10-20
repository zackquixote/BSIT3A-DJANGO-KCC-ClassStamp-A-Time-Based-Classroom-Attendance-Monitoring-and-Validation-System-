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

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.decorators import role_required
from apps.core.models import Class, Department, Profile, Program
from apps.core.services import (
    build_student_queryset,
    import_students_from_csv,
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
    sections = Class.objects.filter(is_active=True).values_list('class_code', flat=True).distinct().order_by('class_code')

    # Aggregate counts across all registered students
    total_students = Profile.objects.filter(role=Profile.ROLE_STUDENT).count()
    approved_count = Profile.objects.filter(role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_APPROVED).count()
    pending_count = Profile.objects.filter(role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_PENDING).count()
    rejected_count = Profile.objects.filter(role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_REJECTED).count()

    filtered_count = students_qs.count()

    # Dynamic year level counts reflecting active department/program/status/search context
    year_count_base = Profile.objects.filter(role=Profile.ROLE_STUDENT)
    if dept_id:
        year_count_base = year_count_base.filter(program__department_id=dept_id)
    if prog_id:
        year_count_base = year_count_base.filter(program_id=prog_id)
    if status in [Profile.APPROVAL_APPROVED, Profile.APPROVAL_PENDING, Profile.APPROVAL_REJECTED]:
        year_count_base = year_count_base.filter(approval_status=status)
    if section:
        year_count_base = year_count_base.filter(enrollments__class_obj__class_code__icontains=section).distinct()
    if q:
        year_count_base = year_count_base.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(student_number__icontains=q)
        )

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
# // VIEW: Student Directory CSV Export (/students/export-csv/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def student_directory_export_csv(request):
    """
    // Exports the currently filtered student masterlist as a downloadable CSV.
    """
    dept_id = request.GET.get('department', '').strip()
    prog_id = request.GET.get('program', '').strip()
    year_level = request.GET.get('year_level', '').strip()
    section = request.GET.get('section', '').strip()
    status = request.GET.get('status', '').strip()
    q = request.GET.get('q', '').strip()

    students_qs = Profile.objects.filter(role=Profile.ROLE_STUDENT)\
        .select_related('user', 'program', 'program__department')\
        .prefetch_related('enrollments__class_obj')

    if dept_id:
        students_qs = students_qs.filter(program__department_id=dept_id)
    if prog_id:
        students_qs = students_qs.filter(program_id=prog_id)
    if year_level:
        try:
            students_qs = students_qs.filter(year_level=int(year_level))
        except ValueError:
            pass
    if status in [Profile.APPROVAL_APPROVED, Profile.APPROVAL_PENDING, Profile.APPROVAL_REJECTED]:
        students_qs = students_qs.filter(approval_status=status)
    if section:
        students_qs = students_qs.filter(enrollments__class_obj__class_code__icontains=section).distinct()
    if q:
        students_qs = students_qs.filter(
            Q(student_number__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q)
        )

    students_qs = students_qs.order_by('program__department__code', 'program__code', 'year_level', 'user__last_name')

    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="KCC_Student_Masterlist_{timestamp}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Student ID Number',
        'Last Name',
        'First Name',
        'Username',
        'Email',
        'Department Code',
        'Department Name',
        'Program Code',
        'Program Name',
        'Year Level',
        'Enrolled Sections',
        'Approval Status',
        'Registration Date',
    ])

    for profile in students_qs:
        user = profile.user
        prog = profile.program
        dept = prog.department if prog else None
        sections_str = ", ".join(e.class_obj.class_code for e in profile.enrollments.all()) or "None"
        writer.writerow([
            profile.student_number or "N/A",
            user.last_name,
            user.first_name,
            user.username,
            user.email,
            dept.code if dept else "N/A",
            dept.name if dept else "N/A",
            prog.code if prog else "N/A",
            prog.name if prog else "N/A",
            f"Year {profile.year_level}" if profile.year_level else "N/A",
            sections_str,
            profile.approval_status or "N/A",
            profile.created_at.strftime('%Y-%m-%d %H:%M') if profile.created_at else "N/A",
        ])

    return response


# // ==============================================================================
# // VIEW: Student Bulk CSV Import (/students/import/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def student_directory_import_csv(request):
    """
    // [Admin Controller] Bulk CSV Student Ingestion
    // Allows importing entire cohort/section rosters (e.g. 40 students per section)
    // in an atomic database transaction. Generates user accounts, creates student
    // profiles with 64-char QR secrets, auto-approves accounts, and links class sections.
    """
    if request.method == 'GET':
        departments = Department.objects.filter(is_active=True).order_by('name')
        programs = Program.objects.filter(is_active=True).select_related('department').order_by('code')
        classes = Class.objects.filter(is_active=True).order_by('class_code')
        return render(request, 'core/admin/student_import.html', {
            'departments': departments,
            'programs': programs,
            'classes': classes,
        })

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.error(request, 'Please select a CSV file to upload.')
        return redirect('student_directory_import_csv')

    if not csv_file.name.lower().endswith('.csv'):
        messages.error(request, 'Uploaded file must have a .csv extension.')
        return redirect('student_directory_import_csv')

    default_password = request.POST.get('default_password', 'KccStudent2026!').strip() or 'KccStudent2026!'
    auto_approve = request.POST.get('auto_approve') == 'on'
    target_class_id = request.POST.get('target_class_id', '').strip()

    target_class = None
    if target_class_id:
        target_class = Class.objects.filter(pk=target_class_id, is_active=True).first()

    try:
        decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
        reader = csv.DictReader(decoded_file)
    except Exception as e:
        messages.error(request, f'Failed to parse CSV file: {str(e)}')
        return redirect('student_directory_import_csv')

    if not reader.fieldnames:
        messages.error(request, 'CSV file contains no columns or header row.')
        return redirect('student_directory_import_csv')

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
        'departments': Department.objects.filter(is_active=True).order_by('name'),
        'programs': Program.objects.filter(is_active=True).select_related('department').order_by('code'),
        'classes': Class.objects.filter(is_active=True).order_by('class_code'),
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
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="KCC_Student_Import_Template.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'student_number',
        'first_name',
        'last_name',
        'email',
        'program',
        'year_level',
        'section',
        'username',
        'password',
    ])
    writer.writerow([
        '2024-0001',
        'Juan',
        'Dela Cruz',
        'juan.delacruz@kcc.edu.ph',
        'BSIT',
        '3',
        'BSIT-3A',
        'jdelacruz',
        'KccPass123!',
    ])
    writer.writerow([
        '2024-0002',
        'Maria',
        'Santos',
        'maria.santos@kcc.edu.ph',
        'BSIT',
        '3',
        'BSIT-3A',
        'msantos',
        'KccPass123!',
    ])
    writer.writerow([
        '2024-0003',
        'Pedro',
        'Penduko',
        'pedro.penduko@kcc.edu.ph',
        'BSIT',
        '3',
        'BSIT-3A',
        'ppenduko',
        'KccPass123!',
    ])
    return response
