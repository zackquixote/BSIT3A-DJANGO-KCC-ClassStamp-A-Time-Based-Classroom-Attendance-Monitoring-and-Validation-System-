"""
# // ==============================================================================
# // KCC CLASSSTAMP - SECTION MEMBERSHIP SERVICE
# // ==============================================================================
# // Subsystem: Section Derivation (single source of truth)
# // Description:
# //   A student does not own a section field: section membership is the set of
# //   section codes reachable through their active enrollments for a term.
# //
# //   - A regular student lands in exactly one section -> that is their section.
# //   - An irregular or transferee student lands in several (or none) -> there is
# //     no single answer, and callers must not invent one.
# //
# //   Every screen and report should read membership from here instead of parsing
# //   Class.class_code, so "which section is this student in?" has one answer.
# // References: apps/core/models/classroom.py (derive_section_code)
# // ==============================================================================
"""

from apps.core.models import AcademicYear, Enrollment, Profile
from apps.core.models.classroom import derive_section_code


def _resolve_academic_year(academic_year=None):
    """Return the requested term, or the currently active one when omitted."""
    if academic_year is not None:
        return academic_year
    return AcademicYear.objects.filter(is_active=True).first()


def section_codes_for(profile, academic_year=None):
    """
    // [Service] Distinct section codes a student is actively enrolled in.
    // Scoped to one academic year so a promotion or rollover cannot leak last
    // term's sections into this term's display.
    """
    term = _resolve_academic_year(academic_year)

    enrollments = Enrollment.objects.filter(
        student_profile=profile,
        status=Enrollment.STATUS_ACTIVE,
    )
    if term is not None:
        enrollments = enrollments.filter(class_obj__academic_year=term)

    rows = enrollments.values_list(
        'class_obj__section_code',
        'class_obj__class_code',
    )

    # Fallback to the offering code keeps un-backfilled rows visible instead of
    # silently reporting "no section".
    codes = {
        (section_code or derive_section_code(class_code))
        for section_code, class_code in rows
        if section_code or class_code
    }
    return sorted(codes)


def student_section_summary(profile, academic_year=None):
    """
    // [Service] Canonical answer to "which section is this student in?".
    //
    // Returns:
    //   sections          list[str]  every distinct section, ordered
    //   home_section      str | None the single section, or None when ambiguous
    //   is_single_section bool
    //   section_count     int
    //   classification    str        REGULAR | IRREGULAR | TRANSFEREE | raw value
    //   academic_year     str | None
    //
    // home_section is deliberately None for an irregular student: forcing one
    // label would silently mis-file them in section rosters and reports.
    """
    term = _resolve_academic_year(academic_year)
    sections = section_codes_for(profile, term)

    return {
        'sections': sections,
        'home_section': sections[0] if len(sections) == 1 else None,
        'is_single_section': len(sections) == 1,
        'section_count': len(sections),
        'classification': profile.student_type or Profile.STUDENT_TYPE_REGULAR,
        'academic_year': term.name if term else None,
    }
