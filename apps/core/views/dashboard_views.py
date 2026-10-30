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

from datetime import datetime

from django.contrib.auth.decorators import login_required
import json
import time

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render

from apps.core.decorators import approved_required, role_required
from apps.core.models import AcademicYear, ClassSlot, Profile
from apps.core.views.helpers import (
    _admin_dashboard_stats,
    _student_dashboard_stats,
    _teacher_dashboard_stats,
    get_activity_feed,
    get_attendance_chart_data,
    get_pending_count,
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


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_attendance_chart_json(request):
    """
    // [AJAX Endpoint] Dynamic Attendance Analytics
    // Returns JSON payload for Chart.js across 7, 14, 30 days or specific calendar dates.
    """
    days_param = request.GET.get('days', '7').strip()
    date_param = request.GET.get('date', '').strip()

    target_date = None
    if date_param:
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            target_date = None

    try:
        days = int(days_param)
        if days not in [7, 14, 30]:
            days = 7
    except (ValueError, TypeError):
        days = 7

    data = get_attendance_chart_data(days=days, target_date=target_date)
    return JsonResponse(data)


# // ==============================================================================
# // VIEW: Admin Dashboard Real-Time SSE Stream (/admin/live-stream/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_live_stream(request):
    """
    // [SSE Stream Controller] Server-Sent Events stream for Admin Command Center.
    // Pushes real-time live attendance feed events and pending validation counter updates.
    """
    def event_stream():
        # Emit initial synchronization payload
        feed = get_activity_feed(limit=10)
        pending = get_pending_count()
        yield f"event: stamp\ndata: {json.dumps({'feed': feed})}\n\n"
        yield f"event: pending\ndata: {json.dumps({'pending_count': pending})}\n\n"

        # Stream continuous pulses for 20 seconds before graceful disconnect/reconnect
        start_time = time.time()
        last_pending = pending
        while time.time() - start_time < 20:
            time.sleep(3)
            current_pending = get_pending_count()
            if current_pending != last_pending:
                last_pending = current_pending
                yield f"event: pending\ndata: {json.dumps({'pending_count': current_pending})}\n\n"
            yield ": ping\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    return response


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
# // VIEW: Teacher "My Classes" Workspace (/teacher/classes/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER)
def teacher_classes(request):
    """
    // [Teacher Portal] Dedicated teaching-load workspace: each assigned section
    // with its weekly meeting slots, roster size and session launchers.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    stats = _teacher_dashboard_stats(profile)
    classes = list(stats['classes'])

    slots_by_class = {}
    if classes:
        slots = (
            ClassSlot.objects.filter(
                class_obj_id__in=[c.id for c in classes],
                is_active=True,
            )
            .order_by('weekday', 'starts_at')
        )
        for slot in slots:
            slots_by_class.setdefault(slot.class_obj_id, []).append(slot)

    weekly_slot_total = 0
    at_risk_count = 0
    for c in classes:
        c.week_slots = slots_by_class.get(c.id, [])
        weekly_slot_total += len(c.week_slots)
        if c.radar_critical:
            at_risk_count += 1

    return render(request, 'core/teacher/classes.html', {
        'classes': classes,
        'class_count': len(classes),
        'weekly_slot_total': weekly_slot_total,
        'at_risk_count': at_risk_count,
        'total_students_roster': stats['total_students_roster'],
        'active_year': AcademicYear.objects.filter(is_active=True).first(),
    })


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
