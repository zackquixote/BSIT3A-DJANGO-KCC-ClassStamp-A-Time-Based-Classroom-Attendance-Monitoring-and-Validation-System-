"""
# // ==============================================================================
# // KCC CLASSSTAMP - CSV EXPORT SERVICE
# // ==============================================================================
# // Subsystem: Reporting & Data Ingestion / Extraction Layer
# // Description: Service functions that handle CSV serialization and HTTP download
# //   response streaming for student directories, program rosters, and templates.
# //   Keeps view controllers lightweight and decouples file serialization.
# // ==============================================================================
"""

import csv
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from apps.core.models import Profile


def export_student_directory_csv(filter_params=None):
    """
    // Generates a downloadable CSV containing student masterlist records
    // filtered according to request parameters.
    """
    filter_params = filter_params or {}

    dept_id = str(filter_params.get('department', '') or '').strip()
    prog_id = str(filter_params.get('program', '') or '').strip()
    year_level = str(filter_params.get('year_level', '') or '').strip()
    section = str(filter_params.get('section', '') or '').strip()
    status = str(filter_params.get('status', '') or '').strip()
    q = str(filter_params.get('q', '') or '').strip()

    students_qs = (
        Profile.objects.filter(role=Profile.ROLE_STUDENT)
        .select_related('user', 'program', 'program__department')
        .prefetch_related('enrollments__class_obj')
    )

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
            Q(student_number__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
        )

    students_qs = students_qs.order_by(
        'program__department__code',
        'program__code',
        'year_level',
        'user__last_name',
    )

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


def export_program_students_csv(program):
    """
    // Generates a downloadable CSV containing approved students for a specific program.
    """
    students = (
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            program=program,
            approval_status=Profile.APPROVAL_APPROVED,
            year_level__isnull=False,
        )
        .select_related('department', 'user')
        .order_by('department__name', 'year_level', 'user__first_name', 'user__last_name')
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="program_{program.code}_students_{timezone.now().strftime("%Y%m%d")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Student ID',
        'Student Number',
        'First Name',
        'Last Name',
        'Username',
        'Year Level',
        'Department Code',
        'Department Name',
        'Approval Status',
    ])

    for student in students:
        writer.writerow([
            student.id,
            student.student_number or '',
            student.user.first_name or '',
            student.user.last_name or '',
            student.user.username,
            student.year_level or '',
            student.department.code if student.department else '',
            student.department.name if student.department else '',
            student.approval_status or '',
        ])

    return response


def export_student_import_sample_csv():
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
