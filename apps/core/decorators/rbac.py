"""
# // ==============================================================================
# // KCC CLASSSTAMP - ROLE-BASED ACCESS CONTROL (RBAC) DECORATORS & GUARDS
# // ==============================================================================
# // Subsystem: View Authorization Layer
# // Description: Implements centralized view-layer guards to enforce role segregation
# // (ADMIN, TEACHER, STUDENT) and verify account approval state before route execution.
# // Adheres strictly to security specifications in docs/02_SECURITY.md.
# // ==============================================================================
"""

from functools import wraps

from django.shortcuts import redirect

from apps.core.models import Profile


def _get_profile(user):
    """
    // Retrieves the linked Profile instance via OneToOne reverse relation.
    // Returns None if the user does not possess an active ClassStamp profile.
    """
    return getattr(user, 'classstamp_profile', None)


def role_required(*roles):
    """
    // Restricts view execution to one or more authorized Profile roles.
    //
    // Security Behavior:
    // 1. Redirects unauthenticated sessions directly to 'login'.
    // 2. Evaluates the user's Profile.role against allowed roles list.
    // 3. Superusers automatically satisfy Profile.ROLE_ADMIN authorization.
    // 4. Unauthorized users are redirected to their assigned 'dashboard' fallback.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            profile = _get_profile(request.user)
            user_role = profile.role if profile else None

            # Superusers inherit admin rights
            if request.user.is_superuser:
                if Profile.ROLE_ADMIN in roles or not roles:
                    return view_func(request, *args, **kwargs)

            # Block access if profile missing or role mismatched
            if user_role is None or user_role not in roles:
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def approved_required(view_func):
    """
    // Ensures that accounts undergoing registration review are validated before access.
    //
    // Security Behavior:
    // 1. Admins and superusers bypass this check unconditionally.
    // 2. Teachers are validated or assigned directly by administrators.
    // 3. Students must hold Profile.APPROVAL_APPROVED status; otherwise redirected.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        profile = _get_profile(request.user)
        if profile and profile.role == Profile.ROLE_ADMIN:
            return view_func(request, *args, **kwargs)

        # Gate unapproved or rejected student accounts
        if (
            profile is not None
            and profile.role == Profile.ROLE_STUDENT
            and profile.approval_status != Profile.APPROVAL_APPROVED
        ):
            return redirect('dashboard')

        return view_func(request, *args, **kwargs)
    return wrapper
