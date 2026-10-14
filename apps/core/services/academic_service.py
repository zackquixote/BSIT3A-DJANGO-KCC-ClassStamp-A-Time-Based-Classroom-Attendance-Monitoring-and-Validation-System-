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
from django.shortcuts import get_object_or_404

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    Curriculum,
    Department,
    Program,
    Subject,
)


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
        msg = (
            f'Department "{dept.code}" was deactivated '
            f'(attached to {dept.programs.count()} programs and {dept.profiles.count()} faculty).'
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

    if has_students or has_curriculum:
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
    is_active: bool, subject_id=None
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
    //   subject_id  (int):   If provided, updates existing subject; otherwise creates.
    //
    // Returns: dict with keys: instance, action, message
    // Raises: ValueError on duplicate code.
    """
    code = code.strip().upper()
    name = name.strip()
    description = (description or '').strip()

    if not code:
        raise ValueError('Subject code is required.')
    if not name:
        raise ValueError('Subject name is required.')

    code_qs = Subject.objects.filter(code__iexact=code)
    if subject_id:
        code_qs = code_qs.exclude(pk=subject_id)
    if code_qs.exists():
        raise ValueError(f'Subject code "{code}" already exists.')

    if subject_id:
        subject = get_object_or_404(Subject, pk=subject_id)
        old_val = f'{subject.code} - {subject.name} (active: {subject.is_active})'
        subject.code = code
        subject.name = name
        subject.description = description
        subject.is_active = is_active
        subject.save()
        action = 'UPDATE_SUBJECT'
        msg = f'Subject "{subject.code}" updated successfully.'
    else:
        subject = Subject.objects.create(
            code=code,
            name=name,
            description=description,
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
        new_value=f'{subject.code} - {subject.name} (active: {subject.is_active})',
    )

    return {'instance': subject, 'action': action, 'message': msg}


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

def assign_curriculum_subject(actor, program_id: int, year_level: int, subject_id: int) -> dict:
    """
    // [Service] Map Subject to Program Year Level in Curriculum Matrix
    //
    // Raises: ValueError on out-of-bounds year level or duplicate mapping.
    """
    program = get_object_or_404(Program, pk=program_id)
    subject = get_object_or_404(Subject, pk=subject_id)

    if year_level < 1 or year_level > program.years_total:
        raise ValueError(
            f'Year level {year_level} is invalid for {program.code} (max duration: {program.years_total} years).'
        )

    if Curriculum.objects.filter(program=program, year_level=year_level, subject=subject).exists():
        raise ValueError(f'{subject.code} is already assigned to {program.code} Year {year_level}.')

    entry = Curriculum.objects.create(
        program=program,
        year_level=year_level,
        subject=subject,
    )

    AuditEvent.objects.create(
        actor=actor,
        action='ASSIGN_CURRICULUM',
        object_type='Curriculum',
        object_id=str(entry.pk),
        new_value=f'{program.code} Y{year_level} <- {subject.code}',
    )

    return {
        'instance': entry,
        'action': 'ASSIGN_CURRICULUM',
        'message': f'Subject "{subject.code}" assigned to {program.code} Year {year_level}.',
    }


def remove_curriculum_entry(actor, pk: int) -> dict:
    """
    // [Service] Remove Subject from Program Curriculum Matrix
    """
    entry = get_object_or_404(Curriculum, pk=pk)
    summary = f'{entry.program.code} Y{entry.year_level} - {entry.subject.code}'
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


def set_active_academic_year(actor, pk: int) -> dict:
    """
    // [Service] Promote an Academic Year to the Single Current Active Term
    """
    ay = get_object_or_404(AcademicYear, pk=pk)
    with transaction.atomic():
        AcademicYear.objects.exclude(pk=ay.pk).filter(is_active=True).update(is_active=False)
        ay.is_active = True
        ay.save()

    AuditEvent.objects.create(
        actor=actor,
        action='SET_ACTIVE_ACADEMIC_YEAR',
        object_type='AcademicYear',
        object_id=str(ay.pk),
        new_value=f'{ay.name} is now the active term',
    )

    return {'instance': ay, 'message': f'"{ay.name}" is now the active institutional academic term.'}


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

