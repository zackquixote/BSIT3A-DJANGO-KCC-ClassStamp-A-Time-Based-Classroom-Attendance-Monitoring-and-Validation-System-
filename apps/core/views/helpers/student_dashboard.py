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
def _student_dashboard_stats(profile):
    """
    // Summarizes attendance statuses (Present, Late, Absent, Excused), active enrollments,
    // enrolled class schedule timetable, examination schedule, and public academic events.
    """
    today = timezone.localdate()

    stats = AttendanceRecord.objects.filter(student_profile=profile).aggregate(
        present_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
        late_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
        absent_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
        excused_count=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
    )
    stats['enrolled_class_count'] = Enrollment.objects.filter(
        student_profile=profile, status=Enrollment.STATUS_ACTIVE,
    ).count()

    # Active class enrollments with scheduled slots
    stats['active_enrollments'] = list(
        Enrollment.objects.filter(
            student_profile=profile,
            status=Enrollment.STATUS_ACTIVE,
        )
        .select_related('class_obj', 'class_obj__subject', 'class_obj__teacher_profile__user', 'class_obj__academic_year')
        .prefetch_related('class_obj__slots')
    )

    # S-05: Visual weekly timetable grid entries (Mon-Sat)
    timetable_slots = []
    for enr in stats['active_enrollments']:
        class_obj = enr.class_obj
        teacher = class_obj.teacher_profile
        teacher_name = (
            teacher.user.get_full_name() or teacher.user.username
        ) if teacher else 'Unassigned'
        for slot in class_obj.slots.all():
            if not slot.is_active or slot.weekday > 5:
                continue
            timetable_slots.append({
                'weekday': slot.weekday,
                'weekday_label': slot.get_weekday_display(),
                'starts_at': slot.starts_at,
                'ends_at': slot.ends_at,
                'room': slot.room or '—',
                'class_code': class_obj.class_code,
                'subject_code': class_obj.subject.code,
                'teacher': teacher_name,
                'color': TIMETABLE_PALETTE[class_obj.id % len(TIMETABLE_PALETTE)],
            })
    timetable_slots.sort(key=lambda s: (s['weekday'], s['starts_at']))
    stats['timetable_slots'] = timetable_slots
    stats['today_weekday'] = today.weekday()

    # S-03: Per-subject attendance breakdown cards
    record_agg = (
        AttendanceRecord.objects.filter(student_profile=profile)
        .values('session__slot__class_obj_id')
        .annotate(
            present=Count('id', filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
            late=Count('id', filter=Q(status=AttendanceRecord.STATUS_LATE)),
            absent=Count('id', filter=Q(status=AttendanceRecord.STATUS_ABSENT)),
            excused=Count('id', filter=Q(status=AttendanceRecord.STATUS_EXCUSED)),
            total=Count('id'),
        )
    )
    agg_by_class = {row['session__slot__class_obj_id']: row for row in record_agg}

    log_by_class = {}
    for rec in (
        AttendanceRecord.objects.filter(student_profile=profile)
        .select_related('session', 'session__slot__class_obj')
        .order_by('-session__session_date')
    ):
        log_by_class.setdefault(rec.session.slot.class_obj_id, []).append({
            'session_date': rec.session.session_date,
            'status': rec.status,
            'stamped_at': rec.stamped_at,
            'late_minutes': rec.late_minutes,
        })

    breakdowns = []
    for enr in stats['active_enrollments']:
        class_obj = enr.class_obj
        agg = agg_by_class.get(class_obj.id, {'present': 0, 'late': 0, 'absent': 0, 'excused': 0, 'total': 0})
        attended = agg['present'] + agg['late']
        compliance = round((attended / agg['total'] * 100), 1) if agg['total'] else None

        # S-04: CHED early-warning sentinel (unexcused absences only).
        # Stages are ratios of the institutional threshold, so raising it in
        # System Policy moves every edge at once instead of only the red band.
        absence_rate = round((agg['absent'] / agg['total'] * 100), 1) if agg['total'] else None
        threshold = absence_threshold_percent()
        if absence_rate is None:
            sentinel = {'stage': 'none', 'label': 'No meetings yet'}
        elif absence_rate < threshold * 0.5:
            sentinel = {'stage': 'green', 'label': 'Excellent Attendance'}
        elif absence_rate < threshold * 0.8:
            sentinel = {'stage': 'amber', 'label': 'Caution'}
        elif absence_rate < threshold:
            sentinel = {'stage': 'orange', 'label': 'Warning'}
        else:
            sentinel = {'stage': 'red', 'label': 'Exceeded threshold — Contact Instructor/Dean'}

        breakdowns.append({
            'class_obj': class_obj,
            'present': agg['present'],
            'late': agg['late'],
            'absent': agg['absent'],
            'excused': agg['excused'],
            'total': agg['total'],
            'compliance': compliance,
            'absence_rate': absence_rate,
            'sentinel': sentinel,
            'meetings': log_by_class.get(class_obj.id, []),
        })
    stats['class_breakdowns'] = breakdowns

    # S-09: Excuse slip status tracker (Pending/Approved/Rejected)
    stats['excuse_slips'] = list(
        ExcuseSlip.objects.filter(student_profile=profile)
        .select_related(
            'session', 'session__slot', 'session__slot__class_obj',
            'session__slot__class_obj__subject', 'reviewed_by',
        )
        .order_by('-created_at')[:10]
    )
    slip_counts = ExcuseSlip.objects.filter(student_profile=profile).aggregate(
        pending=Count('id', filter=Q(status=ExcuseSlip.STATUS_PENDING)),
        approved=Count('id', filter=Q(status=ExcuseSlip.STATUS_APPROVED)),
        rejected=Count('id', filter=Q(status=ExcuseSlip.STATUS_REJECTED)),
    )
    stats['excuse_slip_counts'] = slip_counts

    now = timezone.now()
    start_of_today = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    end_of_today = timezone.make_aware(datetime.combine(today, datetime.max.time()))

    # Public Academic Events & Today's Observance
    stats['upcoming_calendar_events'] = list(
        AcademicEvent.objects.filter(
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            end_datetime__gte=now,
        )
        .select_related('academic_year')
        .order_by('start_datetime')[:6]
    )

    today_events = list(
        AcademicEvent.objects.filter(
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            start_datetime__lte=end_of_today,
            end_datetime__gte=start_of_today,
        ).select_related('academic_year')
    )
    stats['today_events'] = today_events
    stats['today_holiday'] = next((e for e in today_events if e.category == AcademicEvent.CATEGORY_HOLIDAY), None)

    # Examination Schedules (Midterms / Finals)
    stats['upcoming_exams'] = list(
        AcademicEvent.objects.filter(
            status=AcademicEvent.STATUS_SCHEDULED,
            visibility=AcademicEvent.VISIBILITY_ALL,
            category=AcademicEvent.CATEGORY_EXAMINATION,
            end_datetime__gte=now,
        )
        .select_related('academic_year')
        .order_by('start_datetime')[:3]
    )

    stats['today_date'] = today
    return stats


# // ==============================================================================
# // STANDALONE HELPER: Live Activity Feed (used by AJAX endpoint + dashboard)
# // ==============================================================================
