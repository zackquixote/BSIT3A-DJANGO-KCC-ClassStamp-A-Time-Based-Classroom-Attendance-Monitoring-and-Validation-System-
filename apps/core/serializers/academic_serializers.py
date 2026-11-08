"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC SERIALIZERS
# // ==============================================================================
# // Subsystem: Academic Domain Data Serialization
# // Description: Transforms Department and Program model instances into structured
# //   dictionaries for JSON API responses, AJAX forms, and client components.
# // ==============================================================================
"""


def serialize_department(department) -> dict:
    """
    // Serializes a Department model instance with its full attribute graph.
    """
    if not department:
        return {}

    return {
        'id': department.id,
        'code': department.code,
        'name': department.name,
        'is_active': department.is_active,
        'program_count': getattr(department, 'program_count', department.programs.count() if hasattr(department, 'programs') else 0),
        'faculty_count': getattr(department, 'faculty_count', department.profiles.count() if hasattr(department, 'profiles') else 0),
    }


def serialize_program(program) -> dict:
    """
    // Serializes a Program model instance including nested department information.
    """
    if not program:
        return {}

    return {
        'id': program.id,
        'department_id': program.department_id,
        'department_code': program.department.code if program.department else None,
        'department_name': program.department.name if program.department else None,
        'code': program.code,
        'name': program.name,
        'years_total': program.years_total,
        'is_active': program.is_active,
    }


def serialize_subject(subject) -> dict:
    """
    // Serializes a Subject model instance with usage counts and curriculum mappings.
    """
    if not subject:
        return {}

    return {
        'id': subject.id,
        'code': subject.code,
        'name': subject.name,
        'description': subject.description or '',
        'units': subject.units,
        'is_active': subject.is_active,
        'class_count': getattr(subject, 'class_count', subject.classes.count() if hasattr(subject, 'classes') else 0),
        'curriculum_count': getattr(subject, 'curriculum_count', subject.curriculum_entries.count() if hasattr(subject, 'curriculum_entries') else 0),
    }


def serialize_subject_summary(subject) -> dict:
    """
    // Minimal Subject serialization for dropdown lookups.
    """
    if not subject:
        return {}

    return {
        'id': subject.id,
        'code': subject.code,
        'name': subject.name,
        'units': subject.units,
        'is_active': subject.is_active,
    }


def serialize_curriculum_version(version) -> dict:
    """
    // Serializes a CurriculumVersion with reviewer metadata for the matrix UI.
    """
    if not version:
        return {}

    def _user_label(user):
        if not user:
            return ''
        return user.get_full_name() or user.username

    # Batch identity is the entering school year, not the internal revision
    # counter, so admins read cohorts ("2024-2025") instead of v1/v2/v3.
    effective_name = version.effective_from.name if version.effective_from else None
    starts_on = version.effective_from.starts_on if version.effective_from else None
    batch_year = f'{starts_on.year}-{starts_on.year + 1}' if starts_on else None
    status_display = version.get_status_display()
    if batch_year:
        batch_label = f'{batch_year} ({status_display})'
    elif version.status == 'DRAFT':
        batch_label = 'Draft (editing)'
    else:
        batch_label = f'Legacy ({status_display})'

    return {
        'id': version.id,
        'program_id': version.program_id,
        'program_code': version.program.code if version.program else None,
        'version_number': version.version_number,
        'label': f'v{version.version_number}',
        'batch_year': batch_year,
        'batch_label': batch_label,
        'status': version.status,
        'status_label': status_display,
        'effective_from_id': version.effective_from_id,
        'effective_from': effective_name,
        'notes': version.notes or '',
        'created_by': _user_label(version.created_by),
        'approved_by': _user_label(version.approved_by),
        'approved_at': (
            version.approved_at.isoformat() if version.approved_at else None
        ),
    }


def serialize_curriculum_entry(entry, teachers=None) -> dict:
    """
    // Serializes a Curriculum matrix entry mapping a program, year level, and subject.
    """
    if not entry:
        return {}

    version = entry.version if entry.version_id else None
    return {
        'id': entry.id,
        'program_id': entry.program_id,
        'program_code': entry.program.code if entry.program else None,
        'program_name': entry.program.name if entry.program else None,
        'version_id': entry.version_id,
        'version_number': version.version_number if version else None,
        'version_status': version.status if version else None,
        'year_level': entry.year_level,
        'semester': entry.semester,
        'subject_id': entry.subject_id,
        'subject_code': entry.subject.code if entry.subject else None,
        'subject_name': entry.subject.name if entry.subject else None,
        'subject_units': entry.subject.units if entry.subject else 0,
        'teachers': teachers if teachers is not None else [],
        'is_major': entry.is_major,
    }


def serialize_academic_year(academic_year) -> dict:
    """
    // Serializes an AcademicYear model instance with associated class metrics.
    """
    if not academic_year:
        return {}

    return {
        'id': academic_year.id,
        'name': academic_year.name,
        'starts_on': academic_year.starts_on.isoformat() if academic_year.starts_on else None,
        'ends_on': academic_year.ends_on.isoformat() if academic_year.ends_on else None,
        'is_active': academic_year.is_active,
        'class_count': getattr(academic_year, 'class_count', academic_year.classes.count() if hasattr(academic_year, 'classes') else 0),
    }
