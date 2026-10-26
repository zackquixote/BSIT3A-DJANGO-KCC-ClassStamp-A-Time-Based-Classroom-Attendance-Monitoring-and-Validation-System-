"""
# // ==============================================================================
# // KCC CLASSSTAMP - CLASS ASSIGNMENT SERVICE
# // ==============================================================================
# // Subsystem: Class Section Assignment & Teaching-Load Mutation
# // Description: Canonical entry point for creating, updating, and reassigning
# //   Class sections. Keeps instructor assignment consistent across the Classes
# //   masterlist and the Teachers teaching-load modal, with one audit trail.
# // References: docs/01_DEV_PLAN.md (Phase 2G) | apps/core/models/classroom.py
# // ==============================================================================
"""

from django.db import transaction

from apps.core.models import AuditEvent, Class


class ClassAssignmentError(ValueError):
    pass


def _teacher_label(profile) -> str:
    if not profile:
        return 'Unassigned'
    user = profile.user
    return user.get_full_name() or user.username


def assign_class(
    *, actor, teacher_profile, academic_year, subject, class_code,
    grace_minutes=10, capacity=None, class_obj=None, reassign_existing=False,
):
    """
    // [Service] Creates or updates a Class assignment and writes its audit event.
    //
    // Returns: dict with keys class, created, reassigned_from
    // Raises: ClassAssignmentError on duplicate/invalid assignment.
    """
    class_code = (class_code or '').strip().upper()
    if not class_code:
        raise ClassAssignmentError('Section code is required.')

    with transaction.atomic():
        conflict_qs = Class.objects.select_for_update().filter(
            academic_year=academic_year,
            class_code=class_code,
        )
        if class_obj is not None:
            conflict_qs = conflict_qs.exclude(pk=class_obj.pk)

        conflict = conflict_qs.first()
        if conflict:
            if class_obj is not None or not reassign_existing:
                raise ClassAssignmentError(
                    f"A class with code '{class_code}' already exists for {academic_year.name}."
                )
            if conflict.teacher_profile_id == teacher_profile.pk:
                raise ClassAssignmentError(
                    f'Class {class_code} is already assigned to {_teacher_label(teacher_profile)}.'
                )
            class_obj = conflict

        created = class_obj is None
        reassigned_from = None
        old_value = ''

        if created:
            class_obj = Class()
        else:
            old_teacher = class_obj.teacher_profile
            reassigned_from = _teacher_label(old_teacher) if old_teacher.pk != teacher_profile.pk else None
            old_value = (
                f"{class_obj.class_code} ({class_obj.subject.code}) / "
                f"{_teacher_label(old_teacher)}"
            )

        class_obj.academic_year = academic_year
        class_obj.subject = subject
        class_obj.teacher_profile = teacher_profile
        class_obj.class_code = class_code
        class_obj.grace_minutes = grace_minutes
        class_obj.capacity = capacity
        if created or reassigned_from:
            class_obj.is_active = True
        class_obj.save()

        if created:
            action = 'CREATE_CLASS'
        elif reassigned_from:
            action = 'REASSIGN_CLASS'
        else:
            action = 'UPDATE_CLASS'

        AuditEvent.objects.create(
            actor=actor,
            action=action,
            object_type='Class',
            object_id=str(class_obj.id),
            old_value=old_value,
            new_value=f"{class_code} ({subject.code}) / {_teacher_label(teacher_profile)}",
            reason=f'Assigned class section {class_code} to {_teacher_label(teacher_profile)}',
        )

    return {
        'class': class_obj,
        'created': created,
        'reassigned_from': reassigned_from,
    }
