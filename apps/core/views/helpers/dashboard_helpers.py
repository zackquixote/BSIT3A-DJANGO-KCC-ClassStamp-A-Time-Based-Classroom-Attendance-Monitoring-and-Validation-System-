"""
# // ==============================================================================
# // KCC CLASSSTAMP - DASHBOARD STATISTICAL AGGREGATION HELPERS
# // ==============================================================================
# // Subsystem: Dashboard KPI Computation Layer
# // Description: Pure query functions that aggregate role-specific institutional
# //   metrics for injection into dashboard template contexts. Extracted from
# //   dashboard_views.py to keep views thin and helpers independently testable.
# //
# //   _admin_dashboard_stats()   — Institutional KPIs for the admin portal
# //   _teacher_dashboard_stats() — Assigned classes and open sessions for a teacher
# //   _student_dashboard_stats() — Personal attendance breakdown for a student
# //
# // References: docs/04_MODELS_REFERENCE.md § Dashboard Aggregation
# // ==============================================================================
"""

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
    //   pending_count      — Students awaiting account approval
    //   student_count      — Total approved active students
    //   teacher_count      — Total approved faculty members
    //   open_session_count — Currently open attendance sessions system-wide
    //   department_count   — Number of registered departments
    //   program_count      — Number of registered degree programs
    """
    return {
        'pending_count': Profile.objects.filter(
            role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_PENDING,
        ).count(),
        'student_count': Profile.objects.filter(
            role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_APPROVED,
        ).count(),
        'teacher_count': Profile.objects.filter(
            role=Profile.ROLE_TEACHER, approval_status=Profile.APPROVAL_APPROVED,
        ).count(),
        'open_session_count': ClassSession.objects.filter(status=ClassSession.STATUS_OPEN).count(),
        'department_count': Department.objects.count(),
        'program_count': Program.objects.count(),
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
