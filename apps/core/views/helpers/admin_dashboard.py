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
def _admin_dashboard_stats():
    from apps.core.views.helpers.dashboard_activity import (
        get_activity_feed,
        get_attendance_chart_data,
        get_attendance_heatmap_data,
    )

    """
    // Computes institutional metrics for display on the admin overview interface.
    //
    // Returns a dict containing:
    //   pending_count       — Students awaiting account approval
    //   student_count       — Total approved active students
    //   teacher_count       — Total approved faculty members
    //   open_session_count  — Currently open attendance sessions system-wide
    //   department_count    — Number of registered departments
    //   program_count       — Number of registered degree programs
    //   pending_students    — Real queue list of students waiting for validation
    //   departments_list    — Departments annotated with student counts
    //   recent_approved     — Recently approved students panel
    //   student_delta       — Change in student count vs yesterday
    //   teacher_delta       — Change in teacher count vs yesterday
    //   session_delta       — Change in open session count vs yesterday
    //   pending_delta       — Change in pending count vs yesterday
    //   chart_data          — Dict for 7-day weekly attendance Chart.js bar chart (json_script)
    //   activity_feed       — Last 10 attendance stamp events for live feed
    """
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    # // Current KPI counts
    pending_count = Profile.objects.filter(
        role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_PENDING,
    ).count()
    student_count = Profile.objects.filter(
        role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_APPROVED,
    ).count()
    teacher_count = Profile.objects.filter(
        role=Profile.ROLE_TEACHER, user__is_active=True,
    ).count()
    open_session_count = ClassSession.objects.filter(status=ClassSession.STATUS_OPEN).count()

    # // [2.3] Departments annotated with approved student count
    departments_list = Department.objects.annotate(
        student_count=Count(
            'programs__profiles',
            filter=Q(
                programs__profiles__role=Profile.ROLE_STUDENT,
                programs__profiles__approval_status=Profile.APPROVAL_APPROVED,
            ),
        )
    ).prefetch_related('programs').all()

    # // [3.4] KPI trend deltas: compare to snapshot before today
    student_count_yesterday = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_APPROVED,
        approved_at__date__lt=today,
    ).count()
    teacher_count_yesterday = Profile.objects.filter(
        role=Profile.ROLE_TEACHER,
        approval_status=Profile.APPROVAL_APPROVED,
        created_at__date__lt=today,
    ).count()
    pending_count_yesterday = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
        created_at__date__lt=today,
    ).count()
    session_count_yesterday = ClassSession.objects.filter(
        status=ClassSession.STATUS_OPEN,
        opened_at__date=yesterday,
    ).count()

    # // [2.2] Weekly attendance analytics — last 7 calendar days (Optimized Single Query)
    chart_data = get_attendance_chart_data(days=7)

    # // [2.1] Live activity feed — last 10 confirmed attendance stamps
    activity_feed = get_activity_feed(limit=10)

    # // Institutional context & active session inspection
    active_academic_year = AcademicYear.objects.filter(is_active=True).first()
    open_anomaly_count = AnomalyFlag.objects.filter(status=AnomalyFlag.STATUS_OPEN).count()
    open_sessions_list = (
        ClassSession.objects.filter(status=ClassSession.STATUS_OPEN)
        .select_related(
            'slot__class_obj__subject',
            'slot__class_obj__teacher_profile__user',
        )
        .order_by('-opened_at')[:8]
    )

    # // [2.4] Today's attendance compliance rate
    today_records = AttendanceRecord.objects.filter(session__session_date=today)
    today_attendance_total = today_records.count()
    if today_attendance_total > 0:
        today_attended = today_records.filter(
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
        ).count()
        attendance_rate = round((today_attended / today_attendance_total) * 100, 1)
    else:
        attendance_rate = None

    # // Academic Calendar & Philippine Holiday Integration
    upcoming_calendar_events = list(
        AcademicEvent.objects.filter(
            end_datetime__date__gte=today,
            status=AcademicEvent.STATUS_SCHEDULED,
        )
        .select_related('academic_year')
        .order_by('start_datetime')[:6]
    )

    today_events = list(
        AcademicEvent.objects.filter(
            start_datetime__date__lte=today,
            end_datetime__date__gte=today,
            status=AcademicEvent.STATUS_SCHEDULED,
        ).select_related('academic_year')
    )
    today_holiday = next((e for e in today_events if e.category == AcademicEvent.CATEGORY_HOLIDAY), None)

    # Lightweight event dates for mini-calendar day dots
    month_start = today.replace(day=1) - timedelta(days=7)
    month_end = today.replace(day=28) + timedelta(days=45)
    month_events_qs = AcademicEvent.objects.filter(
        start_datetime__date__lte=month_end,
        end_datetime__date__gte=month_start,
        status=AcademicEvent.STATUS_SCHEDULED,
    ).values('id', 'title', 'category', 'start_datetime', 'end_datetime', 'is_all_day')

    mini_calendar_events = []
    for evt in month_events_qs:
        s_date = timezone.localtime(evt['start_datetime']).strftime('%Y-%m-%d')
        e_date = timezone.localtime(evt['end_datetime']).strftime('%Y-%m-%d')
        meta = AcademicEvent.CATEGORY_META.get(evt['category'], AcademicEvent.CATEGORY_META[AcademicEvent.CATEGORY_OTHER])
        mini_calendar_events.append({
            'id': evt['id'],
            'title': evt['title'],
            'start_date': s_date,
            'end_date': e_date,
            'category': evt['category'],
            'category_color': meta['color'],
            'category_icon': meta['icon'],
            'category_label': meta['label'],
            'is_all_day': evt['is_all_day'],
        })

    # Approved students with no active section in the current term. They can sign
    # in and render a badge, but every scan is refused as INELIGIBLE until someone
    # enlists them — so the count belongs on the dashboard, not in a filter nobody
    # thinks to open.
    active_year = AcademicYear.objects.filter(is_active=True).first()
    unassigned_qs = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_APPROVED,
        user__is_active=True,
    )
    active_enrolment = Q(enrollments__status=Enrollment.STATUS_ACTIVE)
    if active_year is not None:
        active_enrolment &= Q(enrollments__class_obj__academic_year=active_year)
    unassigned_count = unassigned_qs.exclude(active_enrolment).distinct().count()

    return {
        'unassigned_count': unassigned_count,
        'pending_count': pending_count,
        'student_count': student_count,
        'teacher_count': teacher_count,
        'open_session_count': open_session_count,
        'department_count': Department.objects.count(),
        'program_count': Program.objects.count(),
        'pending_students': Profile.objects.filter(
            role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_PENDING,
        ).select_related('user', 'program', 'program__department').order_by('-created_at')[:6],
        'departments_list': departments_list,
        'recent_approved': Profile.objects.filter(
            role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_APPROVED,
        ).select_related('user', 'program').order_by('-approved_at', '-updated_at')[:5],
        # // Trend deltas
        'student_delta': student_count - student_count_yesterday,
        'teacher_delta': teacher_count - teacher_count_yesterday,
        'pending_delta': pending_count - pending_count_yesterday,
        'session_delta': open_session_count - session_count_yesterday,
        # // Chart, heatmap & feed
        'chart_data': chart_data,
        'heatmap_data': get_attendance_heatmap_data(days=35),
        'activity_feed': activity_feed,
        'active_academic_year': active_academic_year,
        'open_anomaly_count': open_anomaly_count,
        'open_sessions_list': open_sessions_list,
        'attendance_rate': attendance_rate,
        'today_attendance_total': today_attendance_total,
        # // Academic Calendar & Holidays
        'upcoming_calendar_events': upcoming_calendar_events,
        'today_events': today_events,
        'today_holiday': today_holiday,
        'mini_calendar_events_json': mini_calendar_events,
        'today_date': today,
    }


# // ==============================================================================
# // HELPER: Teacher Dashboard Metrics & Class Retrieval
# // ==============================================================================
# // HELPER: Teacher Dashboard Metrics & Class Retrieval
# // ==============================================================================
