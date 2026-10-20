"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC STATISTICAL AGGREGATION HELPERS
# // ==============================================================================
# // Subsystem: Academic Program KPI & Roster Aggregation Layer
# // Description: Query helper functions that aggregate program student cohorts
# //   across academic year levels and collegiate departments with caching.
# //   Extracted from program_views.py to keep views thin and controller-focused.
# // ==============================================================================
"""

from django.core.cache import cache
from django.db.models import Count

from apps.core.models import Profile


def get_program_student_stats(program):
    """
    // Aggregates student counts for a program grouped by year level and department.
    // Employs a 5-minute cache window to avoid repeated aggregate table scans.
    //
    // Returns a dict containing:
    //   students_by_dept_year — QuerySet / cached list of year & dept counts
    //   all_by_dept_year      — Full grouping queryset for statistics computation
    //   dept_breakdown        — Nested dict: {dept_code: {year_level: count}}
    //   dept_totals_list      — Sorted list of [[dept_code, total_count], ...]
    //   total_students        — Total approved students enrolled in this program
    """
    cache_key = f'program_students_{program.id}'
    students_by_dept_year = cache.get(cache_key)

    if not students_by_dept_year:
        students_by_dept_year = (
            Profile.objects
            .filter(
                role=Profile.ROLE_STUDENT,
                program=program,
                approval_status=Profile.APPROVAL_APPROVED,
                year_level__isnull=False,
            )
            .values('year_level', 'department__code', 'department__name')
            .annotate(count=Count('id'))
            .order_by('department__name', 'year_level')
        )
        cache.set(cache_key, students_by_dept_year, 300)

    if not students_by_dept_year.exists():
        students_by_dept_year = (
            Profile.objects
            .filter(
                role=Profile.ROLE_STUDENT,
                program=program,
                approval_status=Profile.APPROVAL_APPROVED,
                year_level__isnull=False,
            )
            .values('year_level', 'department__code', 'department__name')
            .annotate(count=Count('id'))
            .order_by('department__name', 'year_level')
        )

    all_by_dept_year = (
        Profile.objects
        .filter(
            role=Profile.ROLE_STUDENT,
            program=program,
            approval_status=Profile.APPROVAL_APPROVED,
            year_level__isnull=False,
        )
        .values('year_level', 'department__code', 'department__name')
        .annotate(count=Count('id'))
        .order_by('department__name', 'year_level')
    )

    dept_breakdown = {}
    dept_totals = []
    for item in all_by_dept_year:
        dept_code = item['department__code']
        if dept_code not in dept_breakdown:
            dept_breakdown[dept_code] = {}
            dept_totals.append([dept_code, 0])
        dept_breakdown[dept_code][item['year_level']] = item['count']
        dept_totals[-1][1] += item['count']

    dept_totals.sort(key=lambda x: x[1], reverse=True)
    dept_totals_list = [list(item) for item in dept_totals]

    return {
        'students_by_dept_year': students_by_dept_year,
        'all_by_dept_year': all_by_dept_year,
        'dept_breakdown': dept_breakdown,
        'dept_totals_list': dept_totals_list,
        'total_students': sum(s['count'] for s in all_by_dept_year),
    }
