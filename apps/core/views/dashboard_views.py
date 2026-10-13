"""
# // ==============================================================================
# // KCC CLASSSTAMP - ROLE-BASED DASHBOARD CONTROLLERS
# // ==============================================================================
# // Subsystem: Multi-Role Dashboard Dispatcher & Portal Aggregators
# // Description: Evaluates user persona (Admin, Teacher, Student) and renders
# // dedicated operational dashboards with relevant institutional KPIs and schedules.
# // Security References: docs/02_SECURITY.md | apps/core/decorators.py
# // ==============================================================================
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.decorators import approved_required, role_required
from apps.core.models import Profile
from apps.core.views.helpers import (
    _admin_dashboard_stats,
    _student_dashboard_stats,
    _teacher_dashboard_stats,
)


# // Statistical helpers are defined in helpers/dashboard_helpers.py
# // and imported above — this file contains only HTTP view controllers.


# // ==============================================================================
# // VIEW: Smart Role-Aware Dashboard Dispatcher (/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
def dashboard_redirect(request):
    """
    // [RBAC Dispatcher] Evaluates the authenticated user's role and issues
    // a redirect to the corresponding role-specific dashboard URL:
    // - ADMIN / Superuser -> /admin/dashboard/
    // - TEACHER           -> /teacher/dashboard/
    // - STUDENT           -> /student/dashboard/
    // Fallback renders home.html for accounts with no assigned profile.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    role = profile.role if profile else None

    # // [Superuser Escalation] Superusers without an explicit profile get admin portal
    if role is None and request.user.is_superuser:
        role = Profile.ROLE_ADMIN

    # // [Role Routing] Render dedicated role portal
    if role == Profile.ROLE_ADMIN:
        return admin_dashboard(request)
    if role == Profile.ROLE_TEACHER:
        return teacher_dashboard(request)
    if role == Profile.ROLE_STUDENT:
        if profile and profile.approval_status == Profile.APPROVAL_APPROVED:
            return student_dashboard(request)
        return render(request, 'home.html')

    # // Fallback for bare accounts with no role
    return render(request, 'home.html')


# // ==============================================================================
# // VIEW: Admin Dashboard Portal (/admin/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_dashboard(request):
    """
    // [Admin Portal] Renders admin overview with institutional metrics.
    """
    return render(request, 'core/admin/dashboard.html', _admin_dashboard_stats())


# // ==============================================================================
# // VIEW: Teacher Dashboard Portal (/teacher/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER)
def teacher_dashboard(request):
    """
    // [Teacher Portal] Renders teacher's class list and active session summary.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    return render(request, 'core/teacher/dashboard.html', _teacher_dashboard_stats(profile))


# // ==============================================================================
# // VIEW: Student Dashboard Portal (/student/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_dashboard(request):
    """
    // [Student Portal] Renders student overview with personal attendance summary.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    return render(request, 'core/student/dashboard.html', _student_dashboard_stats(profile))
