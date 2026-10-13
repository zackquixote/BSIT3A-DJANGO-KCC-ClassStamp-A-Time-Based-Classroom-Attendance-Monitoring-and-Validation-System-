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

from django.shortcuts import get_object_or_404

from apps.core.models import AuditEvent, Department, Program


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
