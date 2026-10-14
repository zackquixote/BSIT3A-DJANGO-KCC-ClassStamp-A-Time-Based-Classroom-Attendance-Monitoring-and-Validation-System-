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
from django.utils import timezone

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
            approval_status=Profile.APPROVAL_APPROVED,
            approved_by=actor,
            approved_at=timezone.now(),
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
