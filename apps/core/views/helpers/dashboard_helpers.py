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

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AnomalyFlag,
    AttendanceRecord,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    Profile,
    Program,
)


# // ==============================================================================
# // HELPER: Admin Dashboard Statistical Aggregation
# // ==============================================================================
def _admin_dashboard_stats():
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
        role=Profile.ROLE_TEACHER, approval_status=Profile.APPROVAL_APPROVED,
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

    return {
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
        # // Chart & feed
        'chart_data': chart_data,
        'activity_feed': activity_feed,
        'active_academic_year': active_academic_year,
        'open_anomaly_count': open_anomaly_count,
        'open_sessions_list': open_sessions_list,
        'attendance_rate': attendance_rate,
        'today_attendance_total': today_attendance_total,
    }


# // ==============================================================================
# // HELPER: Teacher Dashboard Metrics & Class Retrieval
# // ==============================================================================
# // HELPER: Teacher Dashboard Metrics & Class Retrieval
# // ==============================================================================
def _teacher_dashboard_stats(profile):
    """
    // Queries classes assigned to the requesting teacher and identifies active sessions,
    // today's schedule slots, and roster telemetry.
    """
    today = timezone.localdate()
    today_weekday = today.weekday()

    classes = (
        Class.objects.filter(teacher_profile=profile, is_active=True)
        .select_related('subject', 'academic_year')
        .annotate(
            roster_count=Count('enrollments', filter=Q(enrollments__status=Enrollment.STATUS_ACTIVE), distinct=True),
            slot_count=Count('slots', filter=Q(slots__is_active=True), distinct=True)
        )
        .order_by('class_code')
    )

    # Today's scheduled class slots for this teacher
    today_slots = (
        ClassSlot.objects.filter(
            class_obj__teacher_profile=profile,
            class_obj__is_active=True,
            weekday=today_weekday,
            is_active=True
        )
        .select_related('class_obj', 'class_obj__subject')
        .order_by('starts_at')
    )

    # Currently active / OPEN sessions
    open_sessions = (
        ClassSession.objects.filter(
            slot__class_obj__teacher_profile=profile,
            status=ClassSession.STATUS_OPEN
        )
        .select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')
        .order_by('-opened_at')
    )

    total_students_roster = sum(c.roster_count for c in classes)
    total_sessions_count = ClassSession.objects.filter(
        slot__class_obj__teacher_profile=profile
    ).count()

    # Recent concluded/historical sessions for this teacher (up to 8)
    recent_sessions = list(
        ClassSession.objects.filter(
            slot__class_obj__teacher_profile=profile
        )
        .exclude(status=ClassSession.STATUS_OPEN)
        .select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')
        .annotate(
            present_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_PRESENT)),
            late_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_LATE)),
            absent_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_ABSENT)),
            excused_count=Count('attendance_records', filter=Q(attendance_records__status=AttendanceRecord.STATUS_EXCUSED)),
            total_records=Count('attendance_records'),
        )
        .order_by('-opened_at')[:8]
    )

    for s in recent_sessions:
        attended = s.present_count + s.late_count
        s.attendance_rate = round((attended / s.total_records * 100), 1) if s.total_records > 0 else 0

    all_records = AttendanceRecord.objects.filter(session__slot__class_obj__teacher_profile=profile)
    total_records_count = all_records.count()
    if total_records_count > 0:
        attended_total = all_records.filter(
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
        ).count()
        overall_attendance_rate = round((attended_total / total_records_count * 100), 1)
    else:
        overall_attendance_rate = 100.0

    return {
        'classes': classes,
        'class_count': classes.count(),
        'open_session_count': open_sessions.count(),
        'open_sessions': open_sessions,
        'today_slots': today_slots,
        'total_students_roster': total_students_roster,
        'total_sessions_count': total_sessions_count,
        'recent_sessions': recent_sessions,
        'overall_attendance_rate': overall_attendance_rate,
        'today_date': today,
    }


# // ==============================================================================
# // HELPER: Student Dashboard Attendance Metrics
# // ==============================================================================
def _student_dashboard_stats(profile):
    """
    // Summarizes attendance statuses (Present, Late, Absent, Excused) and active enrollments.
    //
    // Arguments:
    //   profile (Profile): The authenticated student's Profile instance.
    //
    // Returns a dict containing:
    //   present_count        — Total PRESENT records
    //   late_count           — Total LATE records
    //   absent_count         — Total ABSENT records
    //   excused_count        — Total EXCUSED records
    //   enrolled_class_count — Active class enrollments
    """
    stats = AttendanceRecord.objects.filter(student_profile=profile).aggregate(
        present_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        late_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        absent_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        excused_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
    )
    stats['enrolled_class_count'] = Enrollment.objects.filter(
        student_profile=profile, status=Enrollment.STATUS_ACTIVE,
    ).count()
    return stats


# // ==============================================================================
# // STANDALONE HELPER: Live Activity Feed (used by AJAX endpoint + dashboard)
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
