"""
# // ==============================================================================
# // KCC CLASSSTAMP - DEPARTMENT & PROGRAM ACADEMIC CRUD SERVICE
# // ==============================================================================
# // Subsystem: Academic Organisation Business Logic
# // Description: Encapsulates create/update/delete operations for Departments and
# //   Programs with uniqueness validation, soft-delete protection, and audit trail
# //   emission. Extracted from department_views.py and program_views.py so these
# //   operations can be reused by management commands or future API endpoints.
# //
# // Each function returns a result dict:
# //   { 'instance': <model>, 'action': <str>, 'message': <str>, 'type': <str> }
# //
# // Raises:
# //   ValueError — on constraint violation (duplicate code/name, invalid years).
# // ==============================================================================
"""

from datetime import date
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSession,
    Curriculum,
    Department,
    Profile,
    Program,
    Subject,
)
from apps.core.services.curriculum_version_service import (
    assert_entry_editable,
    current_draft_version,
    ensure_draft_version,
)


class TermSwitchBlocked(Exception):
    """
    // Raised when switching the active term would strand live data in the
    // outgoing one. Carries the counts so the UI can explain the block instead
    // of just refusing.
    """

    def __init__(self, message, blockers):
        super().__init__(message)
        self.message = message
        self.blockers = blockers


# // ==============================================================================
# // SECTION 1: DEPARTMENT CRUD OPERATIONS
# // ==============================================================================

def create_or_update_department(actor, code: str, name: str, is_active: bool, dept_id=None) -> dict:
    """
    // [Service] Create or Update Academic Department
    //
    // Arguments:
    //   actor     (User):  Admin performing the action (for audit trail).
    //   code      (str):   Unique department code (e.g. CITCS). Auto-uppercased.
    //   name      (str):   Full department name.
    //   is_active (bool):  Active status flag.
    //   dept_id   (int):   If provided, updates existing department; otherwise creates.
    //
    // Returns: dict with keys: instance, action, message
    // Raises: ValueError on duplicate code or name.
    """
    code = code.strip().upper()
    name = name.strip()

    # // Uniqueness validation
    code_qs = Department.objects.filter(code__iexact=code)
    name_qs = Department.objects.filter(name__iexact=name)
    if dept_id:
        code_qs = code_qs.exclude(pk=dept_id)
        name_qs = name_qs.exclude(pk=dept_id)

    if code_qs.exists():
        raise ValueError(f'Department code "{code}" is already in use.')
    if name_qs.exists():
        raise ValueError(f'Department name "{name}" is already registered.')

    if dept_id:
        dept = get_object_or_404(Department, pk=dept_id)
        old_val = f'{dept.code} - {dept.name} (active: {dept.is_active})'
        dept.code = code
        dept.name = name
        dept.is_active = is_active
        dept.save()
        action = 'UPDATE_DEPARTMENT'
        msg = f'Department "{dept.code}" updated successfully.'
    else:
        dept = Department.objects.create(code=code, name=name, is_active=is_active)
        old_val = None
        action = 'CREATE_DEPARTMENT'
        msg = f'Department "{dept.code} — {dept.name}" created successfully.'

    AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type='Department',
        object_id=str(dept.pk),
        old_value=old_val,
        new_value=f'{dept.code} - {dept.name} (active: {dept.is_active})',
    )

    return {'instance': dept, 'action': action, 'message': msg}


def delete_or_deactivate_department(actor, pk: int) -> dict:
    """
    // [Service] Delete or Soft-Deactivate Academic Department
    //
    // Protection: If programs or faculty are attached, soft-deactivates instead
    //   of hard-deleting to preserve FK referential integrity.
    //
    // Returns: dict with keys: instance, type ('deleted'|'deactivated'), message
    """
    dept = get_object_or_404(Department, pk=pk)
    has_programs = dept.programs.exists()
    has_faculty = dept.profiles.exists()

    # A department is safe to retire only when nothing is still recording
    # attendance under it. Sections keep working after archiving — the flag never
    # gates scanning — so an open session is the one thing that must be closed
    # first, or its stamps land under a unit the admin believes is retired.
    open_sessions = ClassSession.objects.filter(
        status=ClassSession.STATUS_OPEN,
        slot__class_obj__program__department=dept,
    ).count()
    if open_sessions:
        raise ValueError(
            f'"{dept.code}" still has {open_sessions} open attendance session(s) in '
            f'its programs. Close them before retiring the department.'
        )

    if has_programs or has_faculty:
        dept.is_active = False
        dept.save()
        AuditEvent.objects.create(
            actor=actor,
            action='DEACTIVATE_DEPARTMENT',
            object_type='Department',
            object_id=str(dept.pk),
            new_value='is_active=False',
            reason='Protected deactivation due to existing child associations',
        )
        faculty = dept.profiles.filter(role=Profile.ROLE_TEACHER).count()
        msg = (
            f'Department "{dept.code}" was deactivated '
            f'(attached to {dept.programs.count()} programs and {faculty} faculty).'
        )
        status_type = 'deactivated'
    else:
        code = dept.code
        dept_id_str = str(dept.pk)
        dept.delete()
        AuditEvent.objects.create(
            actor=actor,
            action='DELETE_DEPARTMENT',
            object_type='Department',
            object_id=dept_id_str,
            old_value=code,
        )
        msg = f'Department "{code}" was permanently deleted.'
        status_type = 'deleted'
        dept = None

    return {'instance': dept, 'type': status_type, 'message': msg}


# // ==============================================================================
# // SECTION 2: PROGRAM CRUD OPERATIONS
# // ==============================================================================

def create_or_update_program(
    actor, dept_id, code: str, name: str, years_total: int,
    is_active: bool, prog_id=None
) -> dict:
    """
    // [Service] Create or Update Degree Program
    //
    // Arguments:
    //   actor       (User):  Admin performing the action (for audit trail).
    //   dept_id     (int):   Parent department PK.
    //   code        (str):   Unique program code (e.g. BSIT). Auto-uppercased.
    //   name        (str):   Full program title.
    //   years_total (int):   Program duration (1–8 years).
    //   is_active   (bool):  Active status flag.
    //   prog_id     (int):   If provided, updates existing program; otherwise creates.
    //
    // Returns: dict with keys: instance, action, message
    // Raises: ValueError on invalid years, missing dept, or duplicate code.
    """
    code = code.strip().upper()
    name = name.strip()

    if years_total < 1 or years_total > 8:
        raise ValueError('Program duration must be between 1 and 8 years.')

    dept = get_object_or_404(Department, pk=dept_id)

    code_qs = Program.objects.filter(code__iexact=code)
    if prog_id:
        code_qs = code_qs.exclude(pk=prog_id)
    if code_qs.exists():
        raise ValueError(f'Program code "{code}" already exists.')

    if prog_id:
        prog = get_object_or_404(Program, pk=prog_id)

        # Shortening the duration below data that already exists strands those
        # records: promotion caps at years_total, and a Year 4 student inside a
        # 3-year program is a report nobody can explain.
        highest_student_year = (
            Profile.objects.filter(program_id=prog_id, role=Profile.ROLE_STUDENT)
            .aggregate(top=Max('year_level'))['top'] or 0
        )
        highest_curriculum_year = (
            Curriculum.objects.filter(program_id=prog_id)
            .aggregate(top=Max('year_level'))['top'] or 0
        )
        ceiling = max(highest_student_year, highest_curriculum_year)
        if years_total < ceiling:
            raise ValueError(
                f'{code} already has students or curriculum entries in Year {ceiling}. '
                f'Duration cannot be shortened to {years_total} year(s) without moving '
                f'them first.'
            )

        old_val = (
            f'{prog.code} - {prog.name} '
            f'(dept={prog.department.code}, yrs={prog.years_total}, active={prog.is_active})'
        )
        prog.department = dept
        prog.code = code
        prog.name = name
        prog.years_total = years_total
        prog.is_active = is_active
        prog.save()
        action = 'UPDATE_PROGRAM'
        msg = f'Program "{prog.code}" updated successfully.'
    else:
        prog = Program.objects.create(
            department=dept, code=code, name=name,
            years_total=years_total, is_active=is_active,
        )
        old_val = None
        action = 'CREATE_PROGRAM'
        msg = f'Program "{prog.code} — {prog.name}" created under {dept.code} successfully.'

    AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type='Program',
        object_id=str(prog.pk),
        old_value=old_val,
        new_value=f'{prog.code} - {prog.name} (dept={dept.code}, yrs={prog.years_total}, active={prog.is_active})',
    )

    return {'instance': prog, 'action': action, 'message': msg}


def delete_or_deactivate_program(actor, pk: int) -> dict:
    """
    // [Service] Delete or Soft-Deactivate Degree Program
    //
    // Protection: If students or curriculum entries are attached, soft-deactivates
    //   instead of hard-deleting to preserve referential integrity.
    //
    // Returns: dict with keys: instance, type ('deleted'|'deactivated'), message
    """
    prog = get_object_or_404(Program, pk=pk)
    has_students = prog.profiles.exists()
    has_curriculum = prog.curriculum_entries.exists()
    # Class rows are not a hard FK (Class.program is SET_NULL), so without this
    # check a program with sections but no students yet would be deleted and every
    # one of its sections would silently lose its program.
    has_classes = prog.class_sections.exists()

    # Same rule as departments and class sections: a retired unit must not still
    # be recording attendance, or its stamps land under something nobody watches.
    open_sessions = ClassSession.objects.filter(
        status=ClassSession.STATUS_OPEN,
        slot__class_obj__program=prog,
    ).count()
    if open_sessions:
        raise ValueError(
            f'"{prog.code}" still has {open_sessions} open attendance session(s). '
            f'Close them before retiring the program.'
        )

    if has_students or has_curriculum or has_classes:
        prog.is_active = False
        prog.save()
        AuditEvent.objects.create(
            actor=actor,
            action='DEACTIVATE_PROGRAM',
            object_type='Program',
            object_id=str(prog.pk),
            new_value='is_active=False',
            reason='Protected deactivation due to existing student enrollments or curriculum bindings',
        )
        msg = (
            f'Program "{prog.code}" was deactivated '
            f'(attached to {prog.profiles.count()} students or curriculum entries).'
        )
        status_type = 'deactivated'
    else:
        code = prog.code
        prog_id_str = str(prog.pk)
        prog.delete()
        AuditEvent.objects.create(
            actor=actor,
            action='DELETE_PROGRAM',
            object_type='Program',
            object_id=prog_id_str,
            old_value=code,
        )
        msg = f'Program "{code}" was permanently deleted.'
        status_type = 'deleted'
        prog = None

    return {'instance': prog, 'type': status_type, 'message': msg}


# // ==============================================================================
# // SECTION 3: SUBJECT CRUD OPERATIONS
# // ==============================================================================

def create_or_update_subject(
    actor, code: str, name: str, description: str,
    is_active: bool, units: int = 3, subject_id=None
) -> dict:
    """
    // [Service] Create or Update Academic Subject
    //
    // Arguments:
    //   actor       (User):  Admin performing the action (for audit trail).
    //   code        (str):   Unique course code (e.g. IT311). Auto-uppercased.
    //   name        (str):   Official subject descriptive title.
    //   description (str):   Optional syllabus or course overview.
    //   is_active   (bool):  Active status flag.
    //   units       (int):   Credit units; 1 unit = 1 class hour per week.
    //   subject_id  (int):   If provided, updates existing subject; otherwise creates.
    //
    // Returns: dict with keys: instance, action, message
    // Raises: ValueError on duplicate code or invalid units.
    """
    code = code.strip().upper()
    name = name.strip()
    description = (description or '').strip()

    if not code:
        raise ValueError('Subject code is required.')
    if not name:
        raise ValueError('Subject name is required.')
    try:
        units = int(units)
    except (TypeError, ValueError):
        raise ValueError('Units must be a whole number.')
    if units < 1:
        raise ValueError('Units must be at least 1.')

    warning = ''

    code_qs = Subject.objects.filter(code__iexact=code)
    if subject_id:
        code_qs = code_qs.exclude(pk=subject_id)
    if code_qs.exists():
        raise ValueError(f'Subject code "{code}" already exists.')

    if subject_id:
        subject = get_object_or_404(Subject, pk=subject_id)
        previous_units = subject.units
        old_val = f'{subject.code} - {subject.name} ({subject.units}u, active: {subject.is_active})'
        subject.code = code
        subject.name = name
        subject.description = description
        subject.units = units
        subject.is_active = is_active
        subject.save()
        action = 'UPDATE_SUBJECT'
        msg = f'Subject "{subject.code}" updated successfully.'

        # Units drive the wizard's "1 unit = 1 class hour per week" rule, so an
        # edit silently changes what every existing section is expected to hold.
        # Warn instead of blocking: unit corrections between terms are legitimate.
        if previous_units != units:
            active_year = AcademicYear.objects.filter(is_active=True).first()
            affected = Class.objects.filter(subject=subject, is_active=True)
            if active_year is not None:
                affected = affected.filter(academic_year=active_year)
            affected_count = affected.count()
            if affected_count:
                warning = (
                    f'{affected_count} active section(s) still carry the old weekly '
                    f'hours ({previous_units} unit(s) → {units}). Reschedule them if '
                    f'this change was intentional.'
                )
    else:
        subject = Subject.objects.create(
            code=code,
            name=name,
            description=description,
            units=units,
            is_active=is_active,
        )
        old_val = None
        action = 'CREATE_SUBJECT'
        msg = f'Subject "{subject.code} — {subject.name}" created successfully.'

    AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type='Subject',
        object_id=str(subject.pk),
        old_value=old_val,
        new_value=f'{subject.code} - {subject.name} ({subject.units}u, active: {subject.is_active})',
    )

    return {'instance': subject, 'action': action, 'message': msg, 'warning': warning}


def delete_or_deactivate_subject(actor, pk: int) -> dict:
    """
    // [Service] Delete or Soft-Deactivate Subject Offering
    //
    // Protection: If classes or curriculum mappings are attached, soft-deactivates
    //   instead of hard-deleting to preserve FK referential integrity.
    //
    // Returns: dict with keys: instance, type ('deleted'|'deactivated'), message
    """
    subject = get_object_or_404(Subject, pk=pk)
    has_classes = subject.classes.exists()
    has_curriculum = subject.curriculum_entries.exists()

    # Last of the "retire while still live" family: a subject cannot be retired
    # while a session is open against one of its sections.
    open_sessions = ClassSession.objects.filter(
        status=ClassSession.STATUS_OPEN,
        slot__class_obj__subject=subject,
    ).count()
    if open_sessions:
        raise ValueError(
            f'"{subject.code}" still has {open_sessions} open attendance session(s). '
            f'Close them before retiring the subject.'
        )

    if has_classes or has_curriculum:
        subject.is_active = False
        subject.save()
        AuditEvent.objects.create(
            actor=actor,
            action='DEACTIVATE_SUBJECT',
            object_type='Subject',
            object_id=str(subject.pk),
            new_value='is_active=False',
            reason='Protected deactivation due to existing class sections or curriculum entries',
        )
        msg = (
            f'Subject "{subject.code}" was deactivated '
            f'(attached to {subject.classes.count()} class sections and {subject.curriculum_entries.count()} curriculum entries).'
        )
        status_type = 'deactivated'
    else:
        code = subject.code
        subj_id_str = str(subject.pk)
        subject.delete()
        AuditEvent.objects.create(
            actor=actor,
            action='DELETE_SUBJECT',
            object_type='Subject',
            object_id=subj_id_str,
            old_value=code,
        )
        msg = f'Subject "{code}" was permanently deleted.'
        status_type = 'deleted'
        subject = None

    return {'instance': subject, 'type': status_type, 'message': msg}


# // ==============================================================================
# // SECTION 4: CURRICULUM MATRIX OPERATIONS
# // ==============================================================================

def assign_curriculum_subject(
    actor, program_id: int, year_level: int, subject_id: int, semester: int = 1
) -> dict:
    """
    // [Service] Map Subject to Program Year Level + Semester in Curriculum Matrix
    //
    // Raises: ValueError on out-of-bounds year level/semester or duplicate mapping.
    """
    program = get_object_or_404(Program, pk=program_id)
    subject = get_object_or_404(Subject, pk=subject_id)

    if year_level < 1 or year_level > program.years_total:
        raise ValueError(
            f'Year level {year_level} is invalid for {program.code} (max duration: {program.years_total} years).'
        )

    if semester not in dict(Curriculum.SEMESTER_CHOICES):
        raise ValueError(f'Semester {semester} is invalid. Use 1 (1st Sem), 2 (2nd Sem), or 3 (Summer).')

    draft = current_draft_version(program)
    if draft is None:
        if program.curriculum_versions.exists():
            raise ValueError(
                'This curriculum is approved and read-only. '
                'Create a draft before changing the subject matrix.'
            )
        # Programs created before versioning (or in tests) still work without an
        # explicit version; the first edit starts draft v1.
        draft = ensure_draft_version(actor, program)

    if Curriculum.objects.filter(
        version=draft, year_level=year_level, semester=semester, subject=subject,
    ).exists():
        sem_label = dict(Curriculum.SEMESTER_CHOICES).get(semester, f'Sem {semester}')
        raise ValueError(
            f'{subject.code} is already assigned to {program.code} Year {year_level} {sem_label}.'
        )

    entry = Curriculum.objects.create(
        program=program,
        version=draft,
        year_level=year_level,
        semester=semester,
        subject=subject,
    )

    AuditEvent.objects.create(
        actor=actor,
        action='ASSIGN_CURRICULUM',
        object_type='Curriculum',
        object_id=str(entry.pk),
        new_value=(
            f'{program.code} Y{year_level} S{semester} <- {subject.code} '
            f'(draft v{draft.version_number})'
        ),
    )

    return {
        'instance': entry,
        'action': 'ASSIGN_CURRICULUM',
        'message': (
            f'Subject "{subject.code}" added to {program.code} draft '
            f'v{draft.version_number}, Year {year_level} Sem {semester}.'
        ),
    }


def remove_curriculum_entry(actor, pk: int) -> dict:
    """
    // [Service] Remove Subject from Program Curriculum Matrix
    //
    // Approved versions are immutable; the caller must create a draft first.
    """
    entry = get_object_or_404(Curriculum, pk=pk)
    assert_entry_editable(entry)
    summary = f'{entry.program.code} Y{entry.year_level} S{entry.semester} - {entry.subject.code}'
    entry_id = str(entry.pk)
    entry.delete()

    AuditEvent.objects.create(
        actor=actor,
        action='REMOVE_CURRICULUM',
        object_type='Curriculum',
        object_id=entry_id,
        old_value=summary,
    )

    return {'type': 'deleted', 'message': f'Removed "{summary}" from curriculum matrix.'}


# // ==============================================================================
# // SECTION 5: ACADEMIC YEAR CRUD OPERATIONS
# // ==============================================================================

def create_or_update_academic_year(
    actor, name: str, starts_on, ends_on,
    is_active: bool, ay_id=None
) -> dict:
    """
    // [Service] Create or Update Academic Year & Term Window
    //
    // Enforces:
    //   - ends_on > starts_on
    //   - Single active academic term invariant (atomic deactivation of others when is_active=True)
    //
    // Returns: dict with keys: instance, action, message
    // Raises: ValueError on date anomaly or duplicate name.
    """
    name = name.strip()
    if not name:
        raise ValueError('Academic Year term name is required.')

    # Convert string dates if needed
    if isinstance(starts_on, str):
        starts_on = date.fromisoformat(starts_on.strip())
    if isinstance(ends_on, str):
        ends_on = date.fromisoformat(ends_on.strip())

    if ends_on <= starts_on:
        raise ValueError(f'Closing date ({ends_on}) must be chronologically after opening date ({starts_on}).')

    # A term is a time window, and two windows covering the same days mean two
    # answers to "which term was this absence in?".
    overlapping = AcademicYear.objects.filter(
        starts_on__lte=ends_on,
        ends_on__gte=starts_on,
    )
    if ay_id:
        overlapping = overlapping.exclude(pk=ay_id)
    clash = overlapping.first()
    if clash is not None:
        raise ValueError(
            f'These dates overlap "{clash.name}" '
            f'({clash.starts_on} to {clash.ends_on}). Adjust the window so two '
            f'terms never run at the same time.'
        )

    name_qs = AcademicYear.objects.filter(name__iexact=name)
    if ay_id:
        name_qs = name_qs.exclude(pk=ay_id)
    if name_qs.exists():
        raise ValueError(f'Academic Year term "{name}" already exists.')

    with transaction.atomic():
        if ay_id:
            ay = get_object_or_404(AcademicYear, pk=ay_id)
            old_val = f'{ay.name} ({ay.starts_on} to {ay.ends_on}, active: {ay.is_active})'
            ay.name = name
            ay.starts_on = starts_on
            ay.ends_on = ends_on
            ay.is_active = is_active
            ay.save()
            action = 'UPDATE_ACADEMIC_YEAR'
            msg = f'Academic Year "{ay.name}" updated successfully.'
        else:
            ay = AcademicYear.objects.create(
                name=name,
                starts_on=starts_on,
                ends_on=ends_on,
                is_active=is_active,
            )
            old_val = None
            action = 'CREATE_ACADEMIC_YEAR'
            msg = f'Academic Year "{ay.name}" created successfully.'

        # Enforce single active term invariant
        if is_active:
            AcademicYear.objects.exclude(pk=ay.pk).filter(is_active=True).update(is_active=False)

    AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type='AcademicYear',
        object_id=str(ay.pk),
        old_value=old_val,
        new_value=f'{ay.name} ({ay.starts_on} to {ay.ends_on}, active: {ay.is_active})',
    )

    return {'instance': ay, 'action': action, 'message': msg}


def set_active_academic_year(actor, pk: int, force: bool = False, reason: str = '') -> dict:
    """
    // [Service] Promote an Academic Year to the Single Current Active Term
    //
    // Refuses the switch while the outgoing term still has an OPEN attendance
    // session: the session would keep accepting stamps into a term nobody is
    // looking at. `force=True` with a written reason overrides, and the override
    // is recorded in the audit trail.
    """
    ay = get_object_or_404(AcademicYear, pk=pk)
    outgoing = AcademicYear.objects.filter(is_active=True).exclude(pk=ay.pk).first()

    blockers = term_switch_blockers(outgoing)
    # Only an OPEN session is actively writing attendance into the outgoing term.
    # Active classes are reported for context but must not block: they stay marked
    # active after a term ends, so blocking on them would make every ordinary
    # rollover a forced one — and a guard that always fires is a guard nobody reads.
    has_blockers = blockers['open_sessions'] > 0

    if has_blockers and not force:
        raise TermSwitchBlocked(
            f'"{outgoing.name}" still has {blockers["open_sessions"]} open attendance '
            f'session(s). Close them before switching; '
            f'{blockers["active_classes"]} class(es) remain attached to it.',
            blockers,
        )
    if has_blockers and not (reason or '').strip():
        raise ValueError('A written reason is required to switch terms while data is live.')

    with transaction.atomic():
        AcademicYear.objects.exclude(pk=ay.pk).filter(is_active=True).update(is_active=False)
        ay.is_active = True
        ay.save()

    AuditEvent.objects.create(
        actor=actor,
        action='SET_ACTIVE_ACADEMIC_YEAR',
        object_type='AcademicYear',
        object_id=str(ay.pk),
        old_value=outgoing.name if outgoing else 'none',
        new_value=(
            f'{ay.name} is now the active term'
            + (' (forced with live data)' if has_blockers else '')
        ),
        reason=(reason or '').strip() or 'Administrative term switch',
    )

    return {'instance': ay, 'message': f'"{ay.name}" is now the active institutional academic term.'}


def term_switch_blockers(academic_year):
    """
    // What still depends on this term being current.
    // Pending registrations are deliberately not counted: Profile carries no
    // academic-year FK, so a pending account is not attributable to a term and
    // blocking on it would be guesswork.
    """
    if academic_year is None:
        return {'open_sessions': 0, 'active_classes': 0}

    return {
        'open_sessions': ClassSession.objects.filter(
            status=ClassSession.STATUS_OPEN,
            slot__class_obj__academic_year=academic_year,
        ).count(),
        'active_classes': Class.objects.filter(
            academic_year=academic_year,
            is_active=True,
        ).count(),
    }


def _advance_approved_students() -> int:
    """
    Advances approved students one year level, capped at program duration.

    Only REGULAR (or unclassified) students are advanced. An irregular student's
    standing is earned by subject credits, not by time served: bumping their
    year_level silently moves them into the wrong cohort and every section
    report then follows the wrong year. They need a per-student decision.
    """
    promoted_count = 0
    students = (
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        .filter(
            Q(student_type=Profile.STUDENT_TYPE_REGULAR)
            | Q(student_type__isnull=True)
            | Q(student_type='')
        )
        .select_related('program')
    )
    for student in students:
        cap = student.program.years_total if student.program else 0
        if cap and student.year_level < cap:
            student.year_level += 1
            student.save(update_fields=['year_level', 'updated_at'])
            promoted_count += 1
    return promoted_count


def promote_students(actor) -> dict:
    """
    // [Service] End-of-Year Batch Student Promotion (A-06)
    //
    // 1-click advance of every APPROVED student to the next year level,
    // capped at their program's years_total (final-year students stay put).
    """
    with transaction.atomic():
        promoted_count = _advance_approved_students()

    AuditEvent.objects.create(
        actor=actor,
        action='PROMOTE_STUDENTS',
        object_type='Student',
        object_id='ALL',
        new_value=f'{promoted_count} approved student(s) advanced one year level (capped at program duration)',
        reason='End-of-year batch promotion (A-06)',
    )

    return {
        'promoted_count': promoted_count,
        'message': f'Promoted {promoted_count} approved student(s) to the next year level.',
    }


def rollover_academic_year(
    actor, name: str, starts_on, ends_on, promote: bool = False
) -> dict:
    """
    // [Service] Academic Term Rollover (A-08)
    //
    // Single atomic operation:
    //   1. Creates the new term (active).
    //   2. Deactivates every previous active term (single-active invariant).
    //   3. Optional promotion: bumps approved students' year_level by 1,
    //      capped at their program's years_total.
    //
    // Raises: ValueError on missing name, duplicate name, or invalid date window.
    """
    name = name.strip()
    if not name:
        raise ValueError('New term name is required.')
    if isinstance(starts_on, str):
        starts_on = date.fromisoformat(starts_on.strip())
    if isinstance(ends_on, str):
        ends_on = date.fromisoformat(ends_on.strip())
    if ends_on <= starts_on:
        raise ValueError(f'Closing date ({ends_on}) must be after opening date ({starts_on}).')
    if AcademicYear.objects.filter(name__iexact=name).exists():
        raise ValueError(f'Academic Year term "{name}" already exists.')
    clash = AcademicYear.objects.filter(
        starts_on__lte=ends_on,
        ends_on__gte=starts_on,
    ).first()
    if clash is not None:
        raise ValueError(
            f'The new term overlaps "{clash.name}" '
            f'({clash.starts_on} to {clash.ends_on}). Rollover must start after the '
            f'current term ends.'
        )

    previous_actives = list(
        AcademicYear.objects.filter(is_active=True)
        .order_by('-starts_on')
        .values_list('name', flat=True)
    )

    with transaction.atomic():
        ay = AcademicYear.objects.create(
            name=name,
            starts_on=starts_on,
            ends_on=ends_on,
            is_active=True,
        )
        AcademicYear.objects.exclude(pk=ay.pk).filter(is_active=True).update(is_active=False)

        promoted_count = 0
        if promote:
            promoted_count = _advance_approved_students()

    AuditEvent.objects.create(
        actor=actor,
        action='CREATE_ACADEMIC_YEAR',
        object_type='AcademicYear',
        object_id=str(ay.pk),
        new_value=f'{ay.name} ({ay.starts_on} to {ay.ends_on}, active: True, rollover)',
    )
    AuditEvent.objects.create(
        actor=actor,
        action='TERM_ROLLOVER',
        object_type='AcademicYear',
        object_id=str(ay.pk),
        old_value='Active before rollover: ' + (', '.join(previous_actives) or '(none)'),
        new_value=f'New active term: {ay.name}; promote_students={promote}',
    )
    if promote:
        AuditEvent.objects.create(
            actor=actor,
            action='PROMOTE_STUDENTS',
            object_type='Student',
            object_id='ALL',
            new_value=f'{promoted_count} approved student(s) advanced one year level (capped at program duration)',
        )

    return {
        'instance': ay,
        'message': f'Term "{ay.name}" is now active.',
        'promoted_count': promoted_count,
        'previous_actives': previous_actives,
    }


def delete_or_deactivate_academic_year(actor, pk: int) -> dict:
    """
    // [Service] Delete or Soft-Deactivate Academic Year Term
    //
    // Protection: If classes are scheduled under this term, prevent hard-deletion.
    """
    ay = get_object_or_404(AcademicYear, pk=pk)
    has_classes = ay.classes.exists()

    if has_classes:
        ay.is_active = False
        ay.save()
        AuditEvent.objects.create(
            actor=actor,
            action='DEACTIVATE_ACADEMIC_YEAR',
            object_type='AcademicYear',
            object_id=str(ay.pk),
            new_value='is_active=False',
            reason='Protected deactivation due to scheduled classes in term',
        )
        msg = f'Academic Year "{ay.name}" was deactivated (attached to {ay.classes.count()} class sections).'
        status_type = 'deactivated'
    else:
        name = ay.name
        ay_id_str = str(ay.pk)
        ay.delete()
        AuditEvent.objects.create(
            actor=actor,
            action='DELETE_ACADEMIC_YEAR',
            object_type='AcademicYear',
            object_id=ay_id_str,
            old_value=name,
        )
        msg = f'Academic Year "{name}" was permanently deleted.'
        status_type = 'deleted'
        ay = None

    return {'instance': ay, 'type': status_type, 'message': msg}

