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
def _teacher_dashboard_stats(profile):
    """
    // Queries classes assigned to the requesting teacher and identifies active sessions,
    // today's schedule slots, and roster telemetry.
    """
    today = timezone.localdate()
    today_weekday = today.weekday()
    active_year = AcademicYear.objects.filter(is_active=True).first()

    class_scope = {'academic_year': active_year} if active_year else {}
    slot_scope = {'class_obj__academic_year': active_year} if active_year else {}
    session_scope = {'slot__class_obj__academic_year': active_year} if active_year else {}
    record_scope = {'session__slot__class_obj__academic_year': active_year} if active_year else {}

    classes = (
        Class.objects.filter(teacher_profile=profile, is_active=True, **class_scope)
        .select_related('subject', 'academic_year')
        .annotate(
            roster_count=Count('enrollments', filter=Q(enrollments__status=Enrollment.STATUS_ACTIVE), distinct=True),
            slot_count=Count('slots', filter=Q(slots__is_active=True), distinct=True)
        )
        .order_by('class_code')
    )
    class_ids = list(classes.values_list('id', flat=True))
    pending_excuses = ExcuseSlip.objects.filter(
        status=ExcuseSlip.STATUS_PENDING,
        session__slot__class_obj_id__in=class_ids,
    ).count()
    pending_disputes = AttendanceDispute.objects.filter(
        status=AttendanceDispute.STATUS_PENDING,
        record__session__slot__class_obj_id__in=class_ids,
    ).count()

    # T-05: per-class consecutive unexcused-absence streaks (>= 3 newest sessions)
    streaks_by_class = {c.id: [] for c in classes}
    class_ids = [c.id for c in classes]
    if class_ids:
        statuses_by_key = {}
        for row in (
            AttendanceRecord.objects.filter(
                session__slot__class_obj_id__in=class_ids,
                student_profile__role=Profile.ROLE_STUDENT,
            )
            .order_by('student_profile_id', 'session__slot__class_obj_id', '-session__session_date')
            .values_list(
                'session__slot__class_obj_id', 'student_profile_id',
                'student_profile__user__first_name', 'student_profile__user__last_name',
                'student_profile__student_number', 'status',
            )
        ):
            key = (row[0], row[1])
            entry = statuses_by_key.setdefault(key, {'meta': row[2:5], 'statuses': []})
            entry['statuses'].append(row[5])

        for (class_id, _student_id), entry in statuses_by_key.items():
            streak = 0
            for status in entry['statuses']:
                if status == AttendanceRecord.STATUS_ABSENT:
                    streak += 1
                else:
                    break
            if streak >= 3:
                streaks_by_class[class_id].append({
                    'first_name': entry['meta'][0],
                    'last_name': entry['meta'][1],
                    'student_number': entry['meta'][2] or '—',
                    'streak': streak,
                })

    # CHED 20% absence radar per class (T-01) + consecutive-absence sentinel (T-05)
    for c in classes:
        radar = absence_radar_for_class(c)
        c.radar_watch = radar[BAND_WATCH]
        c.radar_critical = radar[BAND_CRITICAL]
        c.absent_streaks = streaks_by_class.get(c.id, [])

    # Today's scheduled class slots for this teacher
    today_slots = (
        ClassSlot.objects.filter(
            class_obj__teacher_profile=profile,
            class_obj__is_active=True,
            weekday=today_weekday,
            is_active=True,
            **slot_scope
        )
        .select_related('class_obj', 'class_obj__subject')
        .order_by('starts_at')
    )

    # Currently active / OPEN sessions
    open_sessions = (
        ClassSession.objects.filter(
            slot__class_obj__teacher_profile=profile,
            status=ClassSession.STATUS_OPEN,
            **session_scope
        )
        .select_related('slot', 'slot__class_obj', 'slot__class_obj__subject')
        .order_by('-opened_at')
    )

    total_students_roster = sum(c.roster_count for c in classes)
    total_sessions_count = ClassSession.objects.filter(
        slot__class_obj__teacher_profile=profile,
        **session_scope
    ).count()

    # Recent concluded/historical sessions for this teacher (up to 8)
    recent_sessions = list(
        ClassSession.objects.filter(
            slot__class_obj__teacher_profile=profile,
            **session_scope
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

    all_records = AttendanceRecord.objects.filter(
        session__slot__class_obj__teacher_profile=profile,
        **record_scope,
    )
    total_records_count = all_records.count()
    if total_records_count > 0:
        attended_total = all_records.filter(
            status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE]
        ).count()
        overall_attendance_rate = round((attended_total / total_records_count * 100), 1)
    else:
        overall_attendance_rate = 100.0

    now = timezone.now()
    start_of_today = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    end_of_today = timezone.make_aware(datetime.combine(today, datetime.max.time()))

    # Academic Calendar Events & Today's Observances for Faculty
    upcoming_calendar_events = list(
        AcademicEvent.objects.filter(
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility__in=[AcademicEvent.VISIBILITY_ALL, AcademicEvent.VISIBILITY_FACULTY],
            end_datetime__gte=now,
        )
        .select_related('academic_year')
        .order_by('start_datetime')[:6]
    )

    today_events = list(
        AcademicEvent.objects.filter(
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility__in=[AcademicEvent.VISIBILITY_ALL, AcademicEvent.VISIBILITY_FACULTY],
            start_datetime__lte=end_of_today,
            end_datetime__gte=start_of_today,
        ).select_related('academic_year')
    )
    today_holiday = next((e for e in today_events if e.category == AcademicEvent.CATEGORY_HOLIDAY), None)

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
        'absent_streak_students': sum(len(v) for v in streaks_by_class.values()),
        'pending_excuses': pending_excuses,
        'pending_disputes': pending_disputes,
        'today_date': today,
        'upcoming_calendar_events': upcoming_calendar_events,
        'today_events': today_events,
        'today_holiday': today_holiday,
    }


# // ==============================================================================
# // HELPER: Student Dashboard Attendance Metrics & Academic Calendar
# // ==============================================================================
