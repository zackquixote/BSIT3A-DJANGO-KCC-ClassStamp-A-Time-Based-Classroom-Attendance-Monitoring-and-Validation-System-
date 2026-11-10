"""
# // ==============================================================================
# // KCC CLASSSTAMP - PERMISSION SERVICE
# // ==============================================================================
# // Subsystem: Authorization & Access Control
# // Description: Centralized permission checking service for object-level
# //   authorization. Provides consistent authorization logic across the
# //   application for class access, session modification, excuse slip approval,
# //   and enrollment management.
# //
# // Design Philosophy:
# //   - Defense in depth: Complements middleware RBAC with fine-grained checks
# //   - Single source of truth: All permission logic centralized here
# //   - Consistent patterns: All methods follow same signature pattern
# //
# // References:
# //   - requirements.md § Requirement 7: Centralized Permission Service
# //   - design.md § 2.1 PermissionService
# // ==============================================================================
"""

import logging
from typing import Optional

from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class PermissionService:
    """
    // [Service] Centralized Permission Checking Service
    // Provides object-level authorization for role-based access control.
    // All methods return boolean indicating whether the user has permission.
    """

    @staticmethod
    def can_user_access_class(user: User, class_obj) -> bool:
        """
        // Check if user has permission to view class details.
        //
        // Authorization Rules:
        //   - Admin: can access any class
        //   - Teacher: can access own classes (teacher_profile matches)
        //   - Student: can access enrolled classes (active enrollment exists)
        //
        // Arguments:
        //   user (User): The Django User attempting access
        //   class_obj (Class): The Class object being accessed
        //
        // Returns:
        //   bool: True if user has permission, False otherwise
        """
        from apps.core.models import Enrollment

        # Superusers bypass object-level checks. The view helpers this service
        # replaces (`_teacher_can_manage`, `_can_review_excuse`, ...) short-
        # circuited is_superuser before looking at the profile; preserved so a
        # profile-less superuser is not locked out of staff workflows.
        if user.is_superuser:
            return True

        # User must have an attached profile
        profile = getattr(user, 'classstamp_profile', None)
        if not profile:
            logger.debug(f'Access denied: User {user.pk} has no profile')
            return False

        # Admin can access any class
        if profile.role == 'ADMIN':
            return True

        # Teacher can access own classes
        if profile.role == 'TEACHER':
            has_access = class_obj.teacher_profile_id == profile.pk
            if not has_access:
                logger.debug(
                    f'Access denied: Teacher {profile.pk} is not instructor '
                    f'of class {class_obj.class_code}'
                )
            return has_access

        # Student can access enrolled classes
        if profile.role == 'STUDENT':
            is_enrolled = Enrollment.objects.filter(
                student_profile=profile,
                class_obj=class_obj,
                status=Enrollment.STATUS_ACTIVE
            ).exists()
            if not is_enrolled:
                logger.debug(
                    f'Access denied: Student {profile.student_number} is not '
                    f'enrolled in class {class_obj.class_code}'
                )
            return is_enrolled

        # Unknown role or no valid role
        logger.warning(f'Access denied: User {user.pk} has unknown role {profile.role}')
        return False

    @staticmethod
    def can_user_modify_session(user: User, session) -> bool:
        """
        // Check if user has permission to edit session attendance.
        //
        // Authorization Rules:
        //   - Admin: can modify any session
        //   - Teacher: can modify own class sessions
        //   - Student: cannot modify sessions
        //
        // Arguments:
        //   user (User): The Django User attempting modification
        //   session (ClassSession): The ClassSession being modified
        //
        // Returns:
        //   bool: True if user has permission, False otherwise
        """
        # Superusers bypass object-level checks (see can_user_access_class).
        if user.is_superuser:
            return True

        # User must have an attached profile
        profile = getattr(user, 'classstamp_profile', None)
        if not profile:
            logger.debug(f'Modification denied: User {user.pk} has no profile')
            return False

        # Admin can modify any session
        if profile.role == 'ADMIN':
            return True

        # Teacher can modify own class sessions
        if profile.role == 'TEACHER':
            class_obj = session.slot.class_obj
            has_permission = class_obj.teacher_profile_id == profile.pk
            if not has_permission:
                logger.debug(
                    f'Modification denied: Teacher {profile.pk} is not instructor '
                    f'of session class {class_obj.class_code}'
                )
            return has_permission

        # Students cannot modify sessions
        if profile.role == 'STUDENT':
            logger.debug(f'Modification denied: Students cannot modify sessions')
            return False

        # Unknown role
        logger.warning(
            f'Modification denied: User {user.pk} has unknown role {profile.role}'
        )
        return False

    @staticmethod
    def can_user_approve_excuse(user: User, excuse_slip) -> bool:
        """
        // Check if user has permission to approve excuse slips.
        //
        // Authorization Rules:
        //   - Admin: can approve any excuse slip
        //   - Teacher: can approve slips for own classes
        //   - Student: cannot approve excuse slips
        //
        // Arguments:
        //   user (User): The Django User attempting approval
        //   excuse_slip (ExcuseSlip): The ExcuseSlip being approved
        //
        // Returns:
        //   bool: True if user has permission, False otherwise
        """
        # Superusers bypass object-level checks (see can_user_access_class).
        if user.is_superuser:
            return True

        # User must have an attached profile
        profile = getattr(user, 'classstamp_profile', None)
        if not profile:
            logger.debug(f'Approval denied: User {user.pk} has no profile')
            return False

        # Admin can approve any excuse slip
        if profile.role == 'ADMIN':
            return True

        # Teacher can approve slips for own classes
        if profile.role == 'TEACHER':
            class_obj = excuse_slip.session.slot.class_obj
            has_permission = class_obj.teacher_profile_id == profile.pk
            if not has_permission:
                logger.debug(
                    f'Approval denied: Teacher {profile.pk} is not instructor '
                    f'of excuse slip class {class_obj.class_code}'
                )
            return has_permission

        # Students cannot approve excuse slips
        if profile.role == 'STUDENT':
            logger.debug(f'Approval denied: Students cannot approve excuse slips')
            return False

        # Unknown role
        logger.warning(
            f'Approval denied: User {user.pk} has unknown role {profile.role}'
        )
        return False

    @staticmethod
    def can_user_manage_enrollment(user: User, class_obj) -> bool:
        """
        // Check if user has permission to manage class enrollment.
        //
        // Authorization Rules:
        //   - Admin: can manage any enrollment
        //   - Teacher: can manage own class enrollments
        //   - Student: cannot manage enrollments
        //
        // Arguments:
        //   user (User): The Django User attempting enrollment management
        //   class_obj (Class): The Class whose enrollment is being managed
        //
        // Returns:
        //   bool: True if user has permission, False otherwise
        """
        # Superusers bypass object-level checks (see can_user_access_class).
        if user.is_superuser:
            return True

        # User must have an attached profile
        profile = getattr(user, 'classstamp_profile', None)
        if not profile:
            logger.debug(f'Enrollment management denied: User {user.pk} has no profile')
            return False

        # Admin can manage any enrollment
        if profile.role == 'ADMIN':
            return True

        # Teacher can manage own class enrollments
        if profile.role == 'TEACHER':
            has_permission = class_obj.teacher_profile_id == profile.pk
            if not has_permission:
                logger.debug(
                    f'Enrollment management denied: Teacher {profile.pk} is not '
                    f'instructor of class {class_obj.class_code}'
                )
            return has_permission

        # Students cannot manage enrollments
        if profile.role == 'STUDENT':
            logger.debug(f'Enrollment management denied: Students cannot manage enrollments')
            return False

        # Unknown role
        logger.warning(
            f'Enrollment management denied: User {user.pk} has unknown role {profile.role}'
        )
        return False

    @staticmethod
    def get_user_role(user: User) -> Optional[str]:
        """
        // Get the role of a user from their profile.
        //
        // Arguments:
        //   user (User): The Django User
        //
        // Returns:
        //   Optional[str]: The role string ('ADMIN', 'TEACHER', 'STUDENT') or None
        """
        profile = getattr(user, 'classstamp_profile', None)
        if not profile:
            return None
        return profile.role

    @staticmethod
    def is_admin(user: User) -> bool:
        """
        // Check if user has ADMIN role.
        //
        // Arguments:
        //   user (User): The Django User
        //
        // Returns:
        //   bool: True if user is an admin, False otherwise
        """
        return PermissionService.get_user_role(user) == 'ADMIN'

    @staticmethod
    def is_teacher(user: User) -> bool:
        """
        // Check if user has TEACHER role.
        //
        // Arguments:
        //   user (User): The Django User
        //
        // Returns:
        //   bool: True if user is a teacher, False otherwise
        """
        return PermissionService.get_user_role(user) == 'TEACHER'

    @staticmethod
    def is_student(user: User) -> bool:
        """
        // Check if user has STUDENT role.
        //
        // Arguments:
        //   user (User): The Django User
        //
        // Returns:
        //   bool: True if user is a student, False otherwise
        """
        return PermissionService.get_user_role(user) == 'STUDENT'
