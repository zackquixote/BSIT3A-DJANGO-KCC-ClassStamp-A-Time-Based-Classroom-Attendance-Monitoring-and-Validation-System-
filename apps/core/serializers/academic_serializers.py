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


def serialize_department_summary(department) -> dict:
    """
    // Minimal Department serialization for dropdowns and lookup references.
    """
    if not department:
        return {}

    return {
        'id': department.id,
        'code': department.code,
        'name': department.name,
        'is_active': department.is_active,
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


def serialize_program_summary(program) -> dict:
    """
    // Minimal Program serialization for dropdowns and filter selectors.
    """
    if not program:
        return {}

    return {
        'id': program.id,
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


def serialize_curriculum_entry(entry) -> dict:
    """
    // Serializes a Curriculum matrix entry mapping a program, year level, and subject.
    """
    if not entry:
        return {}

    return {
        'id': entry.id,
        'program_id': entry.program_id,
        'program_code': entry.program.code if entry.program else None,
        'program_name': entry.program.name if entry.program else None,
        'year_level': entry.year_level,
        'semester': entry.semester,
        'subject_id': entry.subject_id,
        'subject_code': entry.subject.code if entry.subject else None,
        'subject_name': entry.subject.name if entry.subject else None,
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


def serialize_academic_year_summary(academic_year) -> dict:
    """
    // Minimal AcademicYear serialization for dropdown selectors.
    """
    if not academic_year:
        return {}

    return {
        'id': academic_year.id,
        'name': academic_year.name,
        'is_active': academic_year.is_active,
    }

