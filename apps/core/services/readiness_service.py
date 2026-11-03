"""
# // ==============================================================================
# // KCC CLASSSTAMP - CURRICULUM & TERM READINESS REPORTING
# // ==============================================================================
# // Subsystem: Academic Administration / Read-Only Audit
# // Description: Builds a reviewable snapshot of curriculum coverage, term
# //   class data, and the gaps that block a safe semester rollout. Nothing in
# //   this module writes to the database.
# // ==============================================================================
"""

from collections import defaultdict

from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils import timezone

from apps.core.models import AcademicYear, Class, ClassSlot, Curriculum, Enrollment, Program
from apps.core.models.classroom import derive_section_code
from apps.core.services.export_service import SafeCsvWriter


SLOT_STATUS_LABELS = {
    'complete': 'Complete',
    'partial': 'Active and inactive subjects',
    'inactive': 'Inactive subjects only',
    'empty': 'No mappings',
}

PROGRAM_STATUS_LABELS = {
    'complete': 'Complete',
    'incomplete': 'Incomplete',
    'inactive_subjects': 'Needs subject review',
    'not_configured': 'Not configured',
}

PROGRAM_STATUS_BADGES = {
    'complete': 'badge--success',
    'incomplete': 'badge--warning',
    'inactive_subjects': 'badge--warning',
    'not_configured': 'badge--danger',
}

SLOT_STATUS_BADGES = {
    'complete': 'badge--success',
    'partial': 'badge--warning',
    'inactive': 'badge--warning',
    'empty': 'badge--danger',
}


def _slot_status(entries):
    if not entries:
        return 'empty'
    active = [entry for entry in entries if entry.subject.is_active]
    if not active:
        return 'inactive'
    if len(active) != len(entries):
        return 'partial'
    return 'complete'


def _program_status(entries, empty_slots, inactive_mappings):
    if not entries:
        return 'not_configured'
    if empty_slots:
        return 'incomplete'
    if inactive_mappings:
        return 'inactive_subjects'
    return 'complete'


def _class_issue_labels(class_obj, duplicate_section_subjects, curriculum_map):
    issues = []
    if not class_obj.is_active:
        issues.append('Class is inactive')

    if class_obj.is_active:
        if not class_obj.active_slots:
            issues.append('No active schedule')
        if not class_obj.active_enrollments:
            issues.append('No active roster')

    if not class_obj.teacher_profile.user.is_active:
        issues.append('Teacher account is inactive')
    if not class_obj.program_id:
        issues.append('No program assigned')
    if not class_obj.year_level:
        issues.append('No year level assigned')

    if class_obj.class_code != class_obj.class_code.strip():
        issues.append('Class code has leading or trailing whitespace')

    derived_section = derive_section_code(class_obj.class_code)
    if class_obj.section_code and class_obj.section_code != derived_section:
        issues.append('Section code does not match class code')

    duplicate_key = (
        class_obj.academic_year_id,
        class_obj.section_code,
        class_obj.subject_id,
    )
    if duplicate_key in duplicate_section_subjects:
        issues.append('Duplicate section and subject in the same term')

    if (
        class_obj.program_id
        and class_obj.year_level
        and class_obj.subject_id
        and (class_obj.program_id, class_obj.year_level, class_obj.subject_id) not in curriculum_map
    ):
        issues.append('Subject is not mapped to this program and year level')

    return issues


def build_curriculum_readiness_report(program_id=None):
    """
    // Return a read-only report grouped by program/year/semester plus the
    // // operational gaps found in existing classes and terms.
    """
    programs_qs = (
        Program.objects.select_related('department')
        .prefetch_related(
            Prefetch(
                'curriculum_entries',
                queryset=Curriculum.objects.select_related('subject').order_by(
                    'year_level', 'semester', 'subject__code',
                ),
            ),
        )
        .order_by('department__code', 'code')
    )
    if program_id:
        programs_qs = programs_qs.filter(pk=program_id)
    programs = list(programs_qs)

    coverage_rows = []
    program_rows = []
    total_expected_slots = 0
    total_empty_slots = 0
    total_inactive_mappings = 0
    complete_programs = 0
    incomplete_programs = 0
    unconfigured_programs = 0

    for program in programs:
        entries = list(program.curriculum_entries.all())
        entries_by_slot = defaultdict(list)
        for entry in entries:
            entries_by_slot[(entry.year_level, entry.semester)].append(entry)

        years = []
        program_empty_slots = 0
        program_inactive_mappings = 0

        for year_level in range(1, program.years_total + 1):
            semesters = []
            for semester, semester_label in Curriculum.SEMESTER_CHOICES:
                slot_entries = entries_by_slot.get((year_level, semester), [])
                status = _slot_status(slot_entries)
                inactive_count = sum(
                    1 for entry in slot_entries if not entry.subject.is_active
                )
                active_count = len(slot_entries) - inactive_count

                if not slot_entries:
                    program_empty_slots += 1
                program_inactive_mappings += inactive_count

                subjects = [
                    {
                        'entry_id': entry.pk,
                        'code': entry.subject.code,
                        'name': entry.subject.name,
                        'is_active': entry.subject.is_active,
                    }
                    for entry in slot_entries
                ]

                semester_row = {
                    'value': semester,
                    'label': semester_label,
                    'status': status,
                    'status_label': SLOT_STATUS_LABELS[status],
                    'status_badge': SLOT_STATUS_BADGES[status],
                    'subjects': subjects,
                    'active_count': active_count,
                    'inactive_count': inactive_count,
                }
                semesters.append(semester_row)
                coverage_rows.append({
                    'department': program.department.code,
                    'program': program.code,
                    'program_name': program.name,
                    'program_active': program.is_active,
                    'year_level': year_level,
                    'semester': semester,
                    'semester_label': semester_label,
                    'status': status,
                    'status_label': SLOT_STATUS_LABELS[status],
                    'status_badge': SLOT_STATUS_BADGES[status],
                    'subjects': subjects,
                })

            years.append({
                'year_level': year_level,
                'semesters': semesters,
            })

        expected_slots = program.years_total * len(Curriculum.SEMESTER_CHOICES)
        total_expected_slots += expected_slots
        total_empty_slots += program_empty_slots
        total_inactive_mappings += program_inactive_mappings

        status = _program_status(entries, program_empty_slots, program_inactive_mappings)
        if status == 'complete':
            complete_programs += 1
        elif status == 'not_configured':
            unconfigured_programs += 1
        else:
            incomplete_programs += 1

        program_rows.append({
            'program': program,
            'years': years,
            'mapped_count': len(entries),
            'active_count': sum(1 for entry in entries if entry.subject.is_active),
            'inactive_count': program_inactive_mappings,
            'expected_slots': expected_slots,
            'empty_slots': program_empty_slots,
            'status': status,
            'status_label': PROGRAM_STATUS_LABELS[status],
            'status_badge': PROGRAM_STATUS_BADGES[status],
        })

    curriculum_map = set(
        Curriculum.objects.values_list('program_id', 'year_level', 'subject_id')
    )

    classes_qs = (
        Class.objects
        .select_related(
            'academic_year', 'subject', 'teacher_profile__user',
            'program__department',
        )
        .prefetch_related(
            Prefetch(
                'slots',
                queryset=ClassSlot.objects.filter(is_active=True),
                to_attr='active_slots',
            ),
            Prefetch(
                'enrollments',
                queryset=Enrollment.objects.filter(status=Enrollment.STATUS_ACTIVE),
                to_attr='active_enrollments',
            ),
        )
    )
    if program_id:
        classes_qs = classes_qs.filter(program_id=program_id)
    classes = list(
        classes_qs.order_by('-academic_year__starts_on', 'class_code')
    )

    duplicate_section_subjects = set()
    seen_section_subjects = defaultdict(list)
    for class_obj in classes:
        key = (
            class_obj.academic_year_id,
            class_obj.section_code,
            class_obj.subject_id,
        )
        seen_section_subjects[key].append(class_obj)
    for key, grouped_classes in seen_section_subjects.items():
        if len(grouped_classes) > 1:
            duplicate_section_subjects.add(key)

    class_issues = []
    issues_by_class_id = {}
    for class_obj in classes:
        issues = _class_issue_labels(
            class_obj,
            duplicate_section_subjects,
            curriculum_map,
        )
        issues_by_class_id[class_obj.pk] = issues
        if issues:
            class_issues.append({
                'class_obj': class_obj,
                'department': (
                    class_obj.program.department.code
                    if class_obj.program and class_obj.program.department else ''
                ),
                'program': class_obj.program.code if class_obj.program else '',
                'term': class_obj.academic_year,
                'issues': issues,
            })

    classes_by_term = defaultdict(list)
    for class_obj in classes:
        classes_by_term[class_obj.academic_year_id].append(class_obj)

    terms = list(AcademicYear.objects.order_by('-starts_on'))
    term_rows = []
    for term in terms:
        term_classes = classes_by_term.get(term.pk, [])
        term_rows.append({
            'term': term,
            'class_count': len(term_classes),
            'missing_schedule_count': sum(
                1 for class_obj in term_classes
                if class_obj.is_active and not class_obj.active_slots
            ),
            'missing_roster_count': sum(
                1 for class_obj in term_classes
                if class_obj.is_active and not class_obj.active_enrollments
            ),
            'inactive_teacher_count': sum(
                1 for class_obj in term_classes
                if not class_obj.teacher_profile.user.is_active
            ),
            'issue_count': sum(
                1 for class_obj in term_classes
                if issues_by_class_id.get(class_obj.pk)
            ),
        })

    active_term = next((term for term in terms if term.is_active), None)

    return {
        'generated_at': timezone.now(),
        'programs': programs,
        'program_rows': program_rows,
        'coverage_rows': coverage_rows,
        'term_rows': term_rows,
        'class_issues': class_issues,
        'active_term': active_term,
        'totals': {
            'programs': len(programs),
            'complete_programs': complete_programs,
            'incomplete_programs': incomplete_programs,
            'unconfigured_programs': unconfigured_programs,
            'expected_slots': total_expected_slots,
            'empty_slots': total_empty_slots,
            'inactive_mappings': total_inactive_mappings,
            'terms': len(terms),
            'classes': len(classes),
            'classes_with_issues': len(class_issues),
            'missing_schedules': sum(
                1 for class_obj in classes
                if class_obj.is_active and not class_obj.active_slots
            ),
            'missing_rosters': sum(
                1 for class_obj in classes
                if class_obj.is_active and not class_obj.active_enrollments
            ),
            'inactive_teachers': sum(
                1 for class_obj in classes
                if not class_obj.teacher_profile.user.is_active
            ),
        },
    }


def _csv_response(filename):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_readiness_coverage_csv(report):
    """Export every program/year/semester slot and its mapped subjects."""
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response = _csv_response(f'KCC_Curriculum_Coverage_{timestamp}.csv')
    writer = SafeCsvWriter(response)
    writer.writerow([
        'Department',
        'Program',
        'Program Title',
        'Program Active',
        'Year Level',
        'Semester',
        'Slot Status',
        'Subject Code',
        'Subject Title',
        'Subject Active',
    ])

    for row in report['coverage_rows']:
        base = [
            row['department'],
            row['program'],
            row['program_name'],
            'Yes' if row['program_active'] else 'No',
            row['year_level'],
            row['semester_label'],
            row['status_label'],
        ]
        if not row['subjects']:
            writer.writerow(base + ['', '', ''])
            continue
        for subject in row['subjects']:
            writer.writerow(base + [
                subject['code'],
                subject['name'],
                'Yes' if subject['is_active'] else 'No',
            ])

    return response


def export_readiness_issues_csv(report):
    """Export the classes that need attention before a term is published."""
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response = _csv_response(f'KCC_Readiness_Issues_{timestamp}.csv')
    writer = SafeCsvWriter(response)
    writer.writerow([
        'Department',
        'Program',
        'Term',
        'Term Active',
        'Class Code',
        'Section Code',
        'Subject',
        'Teacher',
        'Issues',
    ])

    for row in report['class_issues']:
        class_obj = row['class_obj']
        writer.writerow([
            row['department'],
            row['program'],
            row['term'].name,
            'Yes' if row['term'].is_active else 'No',
            class_obj.class_code,
            class_obj.section_code,
            class_obj.subject.code,
            class_obj.teacher_profile.user.get_full_name() or class_obj.teacher_profile.user.username,
            '; '.join(row['issues']),
        ])

    return response
