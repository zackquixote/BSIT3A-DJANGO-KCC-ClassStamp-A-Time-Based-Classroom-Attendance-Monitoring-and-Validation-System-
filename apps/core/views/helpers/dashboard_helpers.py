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
    AttendanceRecord,
    Class,
    ClassSession,
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

    # // [2.2] Weekly attendance chart — last 7 calendar days
    chart_labels = []
    chart_present = []
    chart_late = []
    chart_absent = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%a %d'))
        qs = AttendanceRecord.objects.filter(session__session_date=day)
        chart_present.append(qs.filter(status=AttendanceRecord.STATUS_PRESENT).count())
        chart_late.append(qs.filter(status=AttendanceRecord.STATUS_LATE).count())
        chart_absent.append(qs.filter(status=AttendanceRecord.STATUS_ABSENT).count())

    chart_data = {
        'labels': chart_labels,
        'present': chart_present,
        'late': chart_late,
        'absent': chart_absent,
    }

    # // [2.1] Live activity feed — last 10 confirmed attendance stamps
    activity_feed = get_activity_feed(limit=10)

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
    }


# // ==============================================================================
# // HELPER: Teacher Dashboard Metrics & Class Retrieval
# // ==============================================================================
def _teacher_dashboard_stats(profile):
    """
    // Queries classes assigned to the requesting teacher and identifies active sessions.
    //
    // Arguments:
    //   profile (Profile): The authenticated teacher's Profile instance.
    //
    // Returns a dict containing:
    //   classes            — QuerySet of active Class objects assigned to the teacher
    //   class_count        — Total number of assigned active classes
    //   open_session_count — Count of currently OPEN sessions across the teacher's classes
    """
    classes = (
        Class.objects.filter(teacher_profile=profile, is_active=True)
        .select_related('subject', 'academic_year')
        .order_by('class_code')
    )
    return {
        'classes': classes,
        'class_count': classes.count(),
        'open_session_count': ClassSession.objects.filter(
            slot__class_obj__teacher_profile=profile,
            status=ClassSession.STATUS_OPEN,
        ).count(),
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
    records = AttendanceRecord.objects.filter(student_profile=profile)
    return {
        'present_count': records.filter(status=AttendanceRecord.STATUS_PRESENT).count(),
        'late_count': records.filter(status=AttendanceRecord.STATUS_LATE).count(),
        'absent_count': records.filter(status=AttendanceRecord.STATUS_ABSENT).count(),
        'excused_count': records.filter(status=AttendanceRecord.STATUS_EXCUSED).count(),
        'enrolled_class_count': Enrollment.objects.filter(
            student_profile=profile, status=Enrollment.STATUS_ACTIVE,
        ).count(),
    }


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
