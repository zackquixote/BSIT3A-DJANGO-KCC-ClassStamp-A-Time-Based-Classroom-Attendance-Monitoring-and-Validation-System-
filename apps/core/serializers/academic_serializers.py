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
