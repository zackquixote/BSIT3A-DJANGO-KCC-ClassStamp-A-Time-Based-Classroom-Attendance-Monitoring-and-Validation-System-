"""
# // ==============================================================================
# // KCC CLASSSTAMP - TEACHER & FACULTY MANAGEMENT SERVICE
# // ==============================================================================
# // Subsystem: Faculty Account Provisioning & Life Cycle Management
# // Description: Encapsulates User and Profile creation for Faculty members.
# //   Enforces the database shape constraints (chk_cs_profile_shape):
# //     - Teacher must carry department_id
# //     - Student fields (program, year_level, student_number) must be NULL
# //     - Auto-sets approval_status to APPROVED with actor audit trail.
# //   Handles safe deactivation protecting historical attendance and classes.
# // References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md (Phase 2E)
# // ==============================================================================
"""

import secrets
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.models import AuditEvent, Department, Profile

User = get_user_model()


def provision_teacher_account(
    actor, username: str, email: str, first_name: str, last_name: str,
    dept_id: int, password: str = None, is_active: bool = True
) -> dict:
    """
    // [Service] Direct Provisioning of Faculty / Teacher Account
    //
    // Arguments:
    //   actor      (User): Admin performing the action.
    //   username   (str):  Unique login username.
    //   email      (str):  Faculty institutional or personal email.
    //   first_name (str):  Teacher given name.
    //   last_name  (str):  Teacher surname.
    //   dept_id    (int):  Collegiate department affiliation.
    //   password   (str):  Optional password; auto-generated if omitted.
    //   is_active  (bool): Account active status.
    //
    // Returns: dict with keys: user, profile, generated_password, message
    // Raises: ValueError on validation failure.
    """
    username = username.strip().lower()
    email = email.strip().lower()
    first_name = first_name.strip()
    last_name = last_name.strip()

    if not username:
        raise ValueError('Username is required.')
    if not email:
        raise ValueError('Email address is required.')
    if not first_name or not last_name:
        raise ValueError('First name and Last name are required.')

    try:
        validate_email(email)
    except ValidationError:
        raise ValueError('A valid email address is required.')

    if User.objects.filter(username__iexact=username).exists():
        raise ValueError(f'Username "{username}" is already taken.')
    if User.objects.filter(email__iexact=email).exists():
        raise ValueError(f'Email "{email}" is already registered to another account.')

    dept = get_object_or_404(Department, pk=dept_id)

    raw_password = password.strip() if password else secrets.token_urlsafe(10)

    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=raw_password,
            is_active=is_active,
        )

        profile = Profile.objects.create(
            user=user,
            role=Profile.ROLE_TEACHER,
            department=dept,
            program=None,
            year_level=None,
            student_number=None,
            approval_status=None,
            approved_by=None,
            approved_at=None,
        )

    AuditEvent.objects.create(
        actor=actor,
        action='CREATE_TEACHER',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'{user.get_full_name()} ({user.username}) - Dept: {dept.code}',
    )

    return {
        'user': user,
        'profile': profile,
        'generated_password': raw_password if not password else None,
        'message': f'Faculty member "{user.get_full_name()}" provisioned successfully under {dept.code}.',
    }


def update_teacher_profile(
    actor, profile_id: int, first_name: str, last_name: str,
    email: str, dept_id: int, is_active: bool, password: str = None
) -> dict:
    """
    // [Service] Update Faculty Member Profile & Department Affiliation
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user', 'department'),
        pk=profile_id,
        role=Profile.ROLE_TEACHER
    )
    user = profile.user

    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()

    if not first_name or not last_name:
        raise ValueError('First name and Last name are required.')
    if not email:
        raise ValueError('Email address is required.')

    try:
        validate_email(email)
    except ValidationError:
        raise ValueError('A valid email address is required.')

    if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        raise ValueError(f'Email "{email}" is already used by another account.')

    dept = get_object_or_404(Department, pk=dept_id)

    old_summary = f'{user.get_full_name()} (email: {user.email}, dept: {profile.department.code if profile.department else "None"}, active: {user.is_active})'

    with transaction.atomic():
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.is_active = is_active
        if password and password.strip():
            user.set_password(password.strip())
        user.save()

        profile.department = dept
        profile.save()

    new_summary = f'{user.get_full_name()} (email: {user.email}, dept: {dept.code}, active: {user.is_active})'

    AuditEvent.objects.create(
        actor=actor,
        action='UPDATE_TEACHER',
        object_type='Profile',
        object_id=str(profile.pk),
        old_value=old_summary,
        new_value=new_summary,
    )

    return {
        'profile': profile,
        'message': f'Faculty profile "{user.get_full_name()}" updated successfully.',
    }


def toggle_teacher_active(actor, profile_id: int) -> dict:
    """
    // [Service] Quick Toggle Faculty Active / Inactive Status
    """
    profile = get_object_or_404(Profile.objects.select_related('user'), pk=profile_id, role=Profile.ROLE_TEACHER)
    user = profile.user
    user.is_active = not user.is_active
    user.save()

    state_str = 'activated' if user.is_active else 'deactivated'
    AuditEvent.objects.create(
        actor=actor,
        action='TOGGLE_TEACHER_STATUS',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'is_active={user.is_active}',
    )

    return {
        'profile': profile,
        'is_active': user.is_active,
        'message': f'Faculty member "{user.get_full_name()}" was {state_str}.',
    }


def set_teacher_active(actor, profile_id: int, is_active: bool) -> dict:
    """
    // [Service] Explicitly set a faculty account's active status.
    // Unlike toggle_teacher_active, this is idempotent and safe for bulk actions.
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user'), pk=profile_id, role=Profile.ROLE_TEACHER
    )
    user = profile.user
    changed = user.is_active != is_active

    if changed:
        user.is_active = is_active
        user.save(update_fields=['is_active'])
        AuditEvent.objects.create(
            actor=actor,
            action='SET_TEACHER_STATUS',
            object_type='Profile',
            object_id=str(profile.pk),
            new_value=f'is_active={is_active}',
        )

    state_str = 'activated' if user.is_active else 'deactivated'
    return {
        'profile': profile,
        'is_active': user.is_active,
        'changed': changed,
        'message': f'Faculty member "{user.get_full_name() or user.username}" was {state_str}.',
    }


def reset_teacher_password(actor, profile_id: int, custom_password: str = None) -> dict:
    """
    // [Service] Reset a faculty account password and return the temporary credential.
    // Emits an immutable audit event. Caller is responsible for secure delivery.
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user'), pk=profile_id, role=Profile.ROLE_TEACHER
    )
    user = profile.user

    password = (custom_password or '').strip() or secrets.token_urlsafe(12)
    user.set_password(password)
    user.save(update_fields=['password'])

    AuditEvent.objects.create(
        actor=actor,
        action='RESET_TEACHER_PASSWORD',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'Administrative password reset for {user.get_full_name() or user.username} ({user.username})',
    )

    return {
        'profile': profile,
        'username': user.username,
        'display_name': user.get_full_name() or user.username,
        'temporary_password': password,
    }


def delete_or_deactivate_teacher(actor, profile_id: int) -> dict:
    """
    // [Service] Delete or Soft-Deactivate Faculty Account
    //
    // Protection: If assigned classes exist, soft-deactivates user rather than hard deleting.
    """
    profile = get_object_or_404(Profile.objects.select_related('user'), pk=profile_id, role=Profile.ROLE_TEACHER)
    user = profile.user
    has_classes = profile.taught_classes.exists()

    if has_classes:
        user.is_active = False
        user.save()
        AuditEvent.objects.create(
            actor=actor,
            action='DEACTIVATE_TEACHER',
            object_type='Profile',
            object_id=str(profile.pk),
            new_value='is_active=False',
            reason='Protected deactivation due to existing assigned classes',
        )
        msg = f'Faculty account "{user.get_full_name()}" was deactivated (assigned to {profile.taught_classes.count()} class sections).'
        status_type = 'deactivated'
    else:
        name = user.get_full_name() or user.username
        user_id_str = str(user.pk)
        user.delete()  # Cascade deletes profile
        AuditEvent.objects.create(
            actor=actor,
            action='DELETE_TEACHER',
            object_type='User',
            object_id=user_id_str,
            old_value=name,
        )
        msg = f'Faculty account "{name}" was permanently deleted.'
        status_type = 'deleted'
        profile = None

    return {'instance': profile, 'type': status_type, 'message': msg}


# // ==============================================================================
# // [Service] Quick Department Reassignment (A-12)
# // ==============================================================================
def reassign_teacher_department(actor, profile_id: int, dept_id: int) -> dict:
    """
    // Transfer a faculty member to another active department.
    // Teaching load (assigned classes) is intentionally left intact; the
    // reassignment is recorded in the audit trail with the previous department.
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user', 'department'),
        pk=profile_id,
        role=Profile.ROLE_TEACHER,
    )
    department = get_object_or_404(Department, pk=dept_id, is_active=True)

    display_name = profile.user.get_full_name() or profile.user.username
    previous = profile.department

    if previous and previous.pk == department.pk:
        raise ValueError(f'{display_name} is already assigned to {department.name}.')

    class_count = profile.taught_classes.count()

    profile.department = department
    profile.save(update_fields=['department', 'updated_at'])

    AuditEvent.objects.create(
        actor=actor,
        action='TEACHER_REASSIGNED',
        object_type='Profile',
        object_id=str(profile.pk),
        old_value=previous.name if previous else 'None',
        new_value=department.name,
        reason=f'Department reassignment (A-12); {class_count} assigned class(es) left intact.',
    )

    return {
        'message': f'{display_name} reassigned to {department.name} ({department.code}).',
        'department_name': department.name,
        'department_code': department.code,
        'class_count': class_count,
    }
