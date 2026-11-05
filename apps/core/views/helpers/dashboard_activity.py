"""
# // ==============================================================================
# // KCC CLASSSTAMP - DASHBOARD STATISTICAL AGGREGATION HELPERS
# // ==============================================================================
# // Subsystem: Dashboard KPI Computation Layer
# // Description: Pure query functions that aggregate role-specific institutional
# //   metrics for injection into dashboard template contexts. Extracted from
# //   dashboard_views.py to keep views thin and helpers independently testable.
# //
# //   _admin_dashboard_stats()        — Institutional KPIs for the admin portal
# //   _teacher_dashboard_stats()      — Assigned classes and open sessions for a teacher
# //   _student_dashboard_stats()      — Personal attendance breakdown for a student
# //   get_activity_feed(limit)        — Latest stamp events for live activity feed
# //   get_pending_count()             — Current pending validation count (AJAX)
# //
# // References: docs/04_MODELS_REFERENCE.md § Dashboard Aggregation
# // ==============================================================================
"""

from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.core.models import (
    AcademicEvent,
    AcademicYear,
    AnomalyFlag,
    AttendanceDispute,
    AttendanceRecord,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    ExcuseSlip,
    Profile,
    Program,
)
from apps.core.services.attendance_policy import absence_threshold_percent
from apps.core.views.helpers.absence_radar import (
    BAND_CRITICAL,
    BAND_WATCH,
    absence_radar_for_class,
)

# S-05: rotating palette for timetable grid blocks
TIMETABLE_PALETTE = ('#60a5fa', '#34d399', '#fbbf24', '#a78bfa', '#f472b6', '#22d3ee')


# // ==============================================================================
# // HELPER: Admin Dashboard Statistical Aggregation
# // ==============================================================================
def get_activity_feed(limit=10):
    """
    // Returns the most recent confirmed attendance stamp records as plain dicts
    // for use in both the server-rendered feed and the AJAX polling endpoint.
    //
    // Arguments:
    //   limit (int): Maximum number of records to return (default: 10).
    //
    // Returns: list of dicts with keys: student, student_id, class_code,
    //          status, method, stamped_at (ISO string)
    """
    records = (
        AttendanceRecord.objects
        .select_related(
            'student_profile__user',
            'session__slot__class_obj',
        )
        .exclude(stamped_at=None)
        .order_by('-stamped_at')[:limit]
    )
    feed = []
    for r in records:
        try:
            class_code = r.session.slot.class_obj.class_code
        except Exception:
            class_code = '—'
        feed.append({
            'student': r.student_profile.user.get_full_name() or r.student_profile.user.username,
            'student_id': r.student_profile.student_number or '—',
            'class_code': class_code,
            'status': r.status,
            'method': r.method,
            'stamped_at': r.stamped_at.isoformat() if r.stamped_at else '',
            'stamped_time': timezone.localtime(r.stamped_at).strftime('%I:%M %p') if r.stamped_at else '',
        })
    return feed


# // ==============================================================================
# // STANDALONE HELPER: Pending Count (used by AJAX auto-refresh endpoint)
# // ==============================================================================
def get_pending_count():
    """
    // Returns current count of students awaiting account approval.
    // Used by the /api/admin/pending-count/ AJAX polling endpoint for
    // auto-refreshing the badge without a full page reload.
    """
    return Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    ).count()


# // ==============================================================================
# // STANDALONE HELPER: Multi-Day & Historical Attendance Chart Data
# // ==============================================================================
def get_attendance_chart_data(days=7, target_date=None):
    """
    // Computes dynamic daily attendance stats across a rolling window or historical date.
    // Supports 7, 14, 30 days or inspecting a specific calendar date (e.g. Oct 07, 2026).
    """
    today = timezone.localdate()
    if target_date:
        end_date = target_date
    else:
        end_date = today

    start_date = end_date - timedelta(days=days - 1)
    day_map = {start_date + timedelta(days=i): {'present': 0, 'late': 0, 'absent': 0, 'excused': 0} for i in range(days)}

    counts_qs = (
        AttendanceRecord.objects.filter(
            session__session_date__gte=start_date,
            session__session_date__lte=end_date,
        )
        .values('session__session_date', 'status')
        .annotate(total=Count('id'))
    )

    for item in counts_qs:
        s_date = item['session__session_date']
        st = item['status']
        if s_date in day_map:
            if st == AttendanceRecord.STATUS_PRESENT:
                day_map[s_date]['present'] = item['total']
            elif st == AttendanceRecord.STATUS_LATE:
                day_map[s_date]['late'] = item['total']
            elif st == AttendanceRecord.STATUS_ABSENT:
                day_map[s_date]['absent'] = item['total']
            elif st == AttendanceRecord.STATUS_EXCUSED:
                day_map[s_date]['excused'] = item['total']

    chart_labels = [d.strftime('%a %d') for d in day_map.keys()]
    raw_dates = [d.strftime('%Y-%m-%d') for d in day_map.keys()]
    display_dates = [d.strftime('%b %d, %Y') for d in day_map.keys()]
    chart_present = [vals['present'] for vals in day_map.values()]
    chart_late = [vals['late'] for vals in day_map.values()]
    chart_absent = [vals['absent'] for vals in day_map.values()]
    chart_excused = [vals['excused'] for vals in day_map.values()]

    return {
        'labels': chart_labels,
        'dates': raw_dates,
        'display_dates': display_dates,
        'present': chart_present,
        'late': chart_late,
        'absent': chart_absent,
        'excused': chart_excused,
        'days': days,
        'range_label': f"{start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}",
    }


# // ==============================================================================
# // STANDALONE HELPER: 35-Day Institutional Attendance Activity Heatmap
# // ==============================================================================
def get_attendance_heatmap_data(days=35):
    """
    // Computes day-by-day attendance volume and intensity matrix across the rolling
    // multi-week window (default 35 days / 5 weeks) for calendar heatmap rendering.
    //
    // Returns:
    //   days: list of dicts with date metadata, attendance breakdowns, and intensity (0..4)
    //   summary: aggregated metrics (total scans, active days, peak day)
    """
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)

    day_map = {
        start_date + timedelta(days=i): {
            'present': 0,
            'late': 0,
            'absent': 0,
            'excused': 0,
        }
        for i in range(days)
    }

    counts_qs = (
        AttendanceRecord.objects.filter(
            session__session_date__gte=start_date,
            session__session_date__lte=today,
        )
        .values('session__session_date', 'status')
        .annotate(total=Count('id'))
    )

    for item in counts_qs:
        s_date = item['session__session_date']
        st = item['status']
        if s_date in day_map:
            if st == AttendanceRecord.STATUS_PRESENT:
                day_map[s_date]['present'] = item['total']
            elif st == AttendanceRecord.STATUS_LATE:
                day_map[s_date]['late'] = item['total']
            elif st == AttendanceRecord.STATUS_ABSENT:
                day_map[s_date]['absent'] = item['total']
            elif st == AttendanceRecord.STATUS_EXCUSED:
                day_map[s_date]['excused'] = item['total']

    day_items = []
    total_scans_sum = 0
    active_days_count = 0
    peak_scans = 0
    peak_date_str = "—"

    for d, counts in day_map.items():
        scans = counts['present'] + counts['late']
        total_scans_sum += scans
        if scans > 0:
            active_days_count += 1
        if scans > peak_scans:
            peak_scans = scans
            peak_date_str = d.strftime('%b %d')

        # Intensity classification (0 to 4)
        if scans == 0:
            intensity = 0
        elif scans <= 5:
            intensity = 1
        elif scans <= 15:
            intensity = 2
        elif scans <= 30:
            intensity = 3
        else:
            intensity = 4

        day_items.append({
            'date': d.strftime('%Y-%m-%d'),
            'display_date': d.strftime('%b %d, %Y'),
            'day_num': d.day,
            'weekday_num': d.weekday(),  # 0 = Monday, 6 = Sunday
            'weekday_short': d.strftime('%a'),
            'month_short': d.strftime('%b'),
            'present': counts['present'],
            'late': counts['late'],
            'absent': counts['absent'],
            'excused': counts['excused'],
            'total_scans': scans,
            'total_records': counts['present'] + counts['late'] + counts['absent'] + counts['excused'],
            'intensity': intensity,
            'is_today': (d == today),
        })

    avg_scans = round(total_scans_sum / active_days_count, 1) if active_days_count > 0 else 0

    return {
        'days': day_items,
        'summary': {
            'total_scans': total_scans_sum,
            'active_days': active_days_count,
            'peak_scans': peak_scans,
            'peak_date': peak_date_str,
            'avg_scans': avg_scans,
            'range_label': f"{start_date.strftime('%b %d')} – {today.strftime('%b %d, %Y')}",
        },
    }
