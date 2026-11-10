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
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from apps.core.models import Profile


# // ==============================================================================
# // SPREADSHEET FORMULA-INJECTION GUARD (OWASP CSV Injection)
# // ==============================================================================
# // A student can register with a first name of "=HYPERLINK(...)". Written to a
# // CSV verbatim, Excel evaluates that cell the moment a registrar opens the
# // export. Every value handed to a CSV or XLSX writer passes through here.
FORMULA_TRIGGER_PREFIXES = ('=', '+', '@', '\t', '\r', '\n')


def safe_spreadsheet_cell(value):
    """
    // Neutralise a single cell against spreadsheet formula injection.
    // Numbers are returned untouched so numeric columns stay numeric; text that
    // would be parsed as a formula is prefixed with an apostrophe.
    """
    if value is None:
        return ''
    if isinstance(value, (int, float, Decimal)):
        return value

    text = str(value)
    if not text:
        return text

    if text[0] in FORMULA_TRIGGER_PREFIXES:
        return "'" + text

    if text[0] == '-':
        # A plain negative number is data, not a formula.
        try:
            Decimal(text)
        except (InvalidOperation, ValueError):
            return "'" + text

    return text


def safe_spreadsheet_row(values):
    """Apply the injection guard to an entire row."""
    return [safe_spreadsheet_cell(value) for value in values]


class SafeCsvWriter:
    """
    // Drop-in proxy for ``csv.writer(response)``.
    // Sanitises every row so a single exporter cannot forget the guard.
    """

    def __init__(self, response):
        self._writer = csv.writer(response)

    def writerow(self, row):
        return self._writer.writerow(safe_spreadsheet_row(row))

    def writerows(self, rows):
        return self._writer.writerows(safe_spreadsheet_row(row) for row in rows)


def export_student_directory_csv(filter_params=None):
    """
    // Generates a downloadable CSV containing student masterlist records
    // filtered according to request parameters.
    """
    filter_params = filter_params or {}

    dept_id = str(filter_params.get('department', '') or '').strip()
    prog_id = str(filter_params.get('program', '') or '').strip()
    year_level = str(filter_params.get('year_level', '') or '').strip()
    batch = str(filter_params.get('batch', '') or '').strip()
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
    if batch:
        try:
            students_qs = students_qs.filter(entry_year=int(batch))
        except ValueError:
            pass
    if status in [Profile.APPROVAL_APPROVED, Profile.APPROVAL_PENDING, Profile.APPROVAL_REJECTED]:
        students_qs = students_qs.filter(approval_status=status)
    if section:
        students_qs = students_qs.filter(
            Q(enrollments__class_obj__section_code__iexact=section)
            | Q(enrollments__class_obj__class_code__iexact=section)
        ).distinct()
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

    writer = SafeCsvWriter(response)
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
        'Entering Batch',
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
            f"Batch {profile.entry_year}" if profile.entry_year else "N/A",
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

    writer = SafeCsvWriter(response)
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

    writer = SafeCsvWriter(response)
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


def build_attendance_matrix_pdf(class_obj, matrix, generated_by) -> bytes:
    """
    // Task 4.7: PDF twin of the attendance-matrix CSV. Same dataset, one
    // dependency (reportlab). Returns PDF bytes; never writes a partial file
    // to disk.
    """
    try:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError(
            'PDF export requires the reportlab package (see requirements.txt).'
        ) from exc

    session_list = matrix['session_list']
    student_rows = matrix['student_rows']
    overall_rate = matrix['overall_rate']

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        title=f'Attendance Matrix — {class_obj.class_code}',
        author='KCC ClassStamp',
    )
    styles = getSampleStyleSheet()
    story = []

    teacher_name = (
        class_obj.teacher_profile.user.get_full_name()
        if class_obj.teacher_profile else '—'
    )
    story.append(Paragraph(
        f'<b>{class_obj.class_code}</b> — {class_obj.subject.name}',
        styles['Title'],
    ))
    story.append(Paragraph(
        f'Teacher: {teacher_name} · '
        f'Term: {class_obj.academic_year.name if class_obj.academic_year else "—"} · '
        f'Overall rate: {overall_rate}%',
        styles['Normal'],
    ))
    generated_at = timezone.localtime(timezone.now())
    story.append(Paragraph(
        f'Generated {generated_at:%Y-%m-%d %H:%M} by '
        f'{generated_by.get_full_name() or generated_by.get_username()}',
        styles['Normal'],
    ))
    story.append(Spacer(1, 8))

    headers = ['Student ID', 'Student Name', 'Program']
    for s in session_list:
        headers.append(f"{s['display_date']} ({s['weekday']})")
    headers.extend(['P', 'L', 'A', 'E', 'Rate %'])

    data = [headers]
    if not student_rows:
        data.append(['(no enrolled students)'] + [''] * (len(headers) - 1))
    for row in student_rows:
        pdf_row = [row['student_number'], row['name'], row['program']]
        for cell in row['cells']:
            pdf_row.append(cell['status'] or '—')
        pdf_row.extend([
            str(row['present']), str(row['late']), str(row['absent']),
            str(row['excused']), f"{row['rate']}%",
        ])
        data.append(pdf_row)

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#94a3b8')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
    ]))
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
