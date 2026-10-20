"""
# // ==============================================================================
# // KCC CLASSSTAMP - CORE APPLICATION VIEW CONTROLLERS (PACKAGE EXPORTS)
# // ==============================================================================
# // Architecture: Modular Controller Package
# // Description: Centralized view package organizing controllers by domain responsibility:
# //
# //   - auth_views: Session authentication, rate-limiting lockout, login/logout, self-registration
# //   - dashboard_views: Multi-role dispatcher, admin, teacher, student dashboards & metric aggregators
# //   - validation_views: Registrar verification queue, student dossier reviews, approval & rejection
# //   - department_views: College department directory, AJAX CRUD, and cascade protections
# //   - program_views: Degree program directory, AJAX CRUD, and duration constraints
# //   - student_views: Student directory masterlist, section rosters, CSV export & batch ingestion
# //
# // All controllers are re-exported at package root to maintain 100% backward compatibility
# // with existing URL routing (`from . import views`) and test suites.
# // References: docs/01_DEV_PLAN.md | docs/02_SECURITY.md
# // ==============================================================================
"""

# // ------------------------------------------------------------------------------
# // 1. Authentication & Registration Subsystem
# // ------------------------------------------------------------------------------
from .auth_views import (
    INVALID_LOGIN_MESSAGE,
    LOCK_DURATION,
    LOCKED_MESSAGE,
    MAX_FAILED_ATTEMPTS,
    _get_lock_state,
    _reset_lock_state,
    _set_lock_state,
    _validate_registration_data,
    check_registration_availability,
    login_view,
    logout_view,
    register_view,
)

# // ------------------------------------------------------------------------------
# // 2. Role-Based Dashboards & Portal Subsystem
# // ------------------------------------------------------------------------------
from .dashboard_views import (
    _admin_dashboard_stats,
    _student_dashboard_stats,
    _teacher_dashboard_stats,
    admin_attendance_chart_json,
    admin_dashboard,
    dashboard_redirect,
    student_dashboard,
    teacher_dashboard,
)

# // ------------------------------------------------------------------------------
# // 3. Account Validation & Registrar Dossier Subsystem
# // ------------------------------------------------------------------------------
from .validation_views import (
    approve_student,
    recently_reviewed_list,
    reject_student,
    validation_detail,
    validation_hub,
    validation_pending_queue,
    validation_queue,
)

# // ------------------------------------------------------------------------------
# // 4. Academic Department Management Subsystem
# // ------------------------------------------------------------------------------
from .department_views import (
    department_delete,
    department_list,
    department_save,
)

# // ------------------------------------------------------------------------------
# // 5. Degree Program & Curriculum Subsystem
# // ------------------------------------------------------------------------------
from .program_views import (
    program_delete,
    program_list,
    program_save,
    program_students_csv_export,
    program_students_per_year,
)

# // ------------------------------------------------------------------------------
# // 6. Student Directory, Masterlist & Bulk Ingestion Subsystem
# // ------------------------------------------------------------------------------
from .student_views import (
    student_directory,
    student_directory_export_csv,
    student_directory_import_csv,
    student_import_sample_csv,
)

# // ------------------------------------------------------------------------------
# // 7. Audit Log & AJAX Feed Endpoints
# // ------------------------------------------------------------------------------
from .audit_views import (
    admin_audit_log,
    admin_audit_log_export_csv,
    admin_activity_feed_json,
    admin_pending_count_json,
)

# // ------------------------------------------------------------------------------
# // 7b. Security Anomaly & Fraud Adjudication Subsystem
# // ------------------------------------------------------------------------------
from .anomaly_views import (
    anomaly_list,
    anomaly_adjudicate,
)

# // ------------------------------------------------------------------------------
# // 8. Subject & Curriculum Management Subsystem
# // ------------------------------------------------------------------------------
from .subject_views import (
    subject_list,
    subject_save,
    subject_delete,
    subject_get,
    subject_curriculum_list,
    subject_curriculum_assign,
    subject_curriculum_remove,
    subject_lookup_json,
)

# // ------------------------------------------------------------------------------
# // 9. Teacher & Faculty Management Subsystem
# // ------------------------------------------------------------------------------
from .teacher_views import (
    teacher_list,
    teacher_create,
    teacher_update,
    teacher_toggle,
    teacher_delete,
    teacher_get,
    teacher_assign_class_ajax,
    teacher_unassign_class_ajax,
)

# // ------------------------------------------------------------------------------
# // 10. Academic Year & Term Management Subsystem
# // ------------------------------------------------------------------------------
from .academic_year_views import (
    academic_year_list,
    academic_year_save,
    academic_year_set_active,
    academic_year_delete,
    academic_year_get,
)

# // ------------------------------------------------------------------------------
# // 11. Class Section, Schedule & Enrollment Subsystem
# // ------------------------------------------------------------------------------
from .class_views import (
    class_list,
    class_save,
    class_toggle,
    class_slot_save,
    class_slot_delete,
    class_roster_get,
    class_roster_enroll,
    class_roster_remove,
)

# // ------------------------------------------------------------------------------
# // 12. Classroom Attendance Session & Live QR Scanner Subsystem
# // ------------------------------------------------------------------------------
from .session_views import (
    attendance_scan_api,
    teacher_manual_override_ajax,
    teacher_session_close,
    teacher_session_open,
    teacher_session_scan,
    teacher_session_summary,
)

__all__ = [
    # Auth & Registration
    'MAX_FAILED_ATTEMPTS',
    'LOCK_DURATION',
    'INVALID_LOGIN_MESSAGE',
    'LOCKED_MESSAGE',
    '_reset_lock_state',
    '_get_lock_state',
    '_set_lock_state',
    '_validate_registration_data',
    'login_view',
    'logout_view',
    'register_view',
    'check_registration_availability',

    # Dashboards
    'dashboard_redirect',
    'admin_dashboard',
    'teacher_dashboard',
    'student_dashboard',
    '_admin_dashboard_stats',
    '_teacher_dashboard_stats',
    '_student_dashboard_stats',

    # Account Validation
    'validation_queue',
    'validation_hub',
    'validation_pending_queue',
    'validation_detail',
    'approve_student',
    'reject_student',
    'recently_reviewed_list',

    # Departments
    'department_list',
    'department_save',
    'department_delete',

    # Programs
    program_students_csv_export,
    program_students_csv_export,
    'program_list',
    'program_save',
    'program_delete',
    'program_students_per_year',

    # Student Masterlist & Ingestion
    'student_directory',
    'student_directory_export_csv',
    'student_directory_import_csv',
    'student_import_sample_csv',

    # Audit Log & AJAX Feeds
    'admin_audit_log',
    'admin_activity_feed_json',
    'admin_pending_count_json',

    # Subjects & Curriculum
    'subject_list',
    'subject_save',
    'subject_delete',
    'subject_get',
    'subject_curriculum_list',
    'subject_curriculum_assign',
    'subject_curriculum_remove',
    'subject_lookup_json',

    # Teachers & Faculty
    'teacher_list',
    'teacher_create',
    'teacher_update',
    'teacher_toggle',
    'teacher_delete',
    'teacher_get',

    # Academic Years
    'academic_year_list',
    'academic_year_save',
    'academic_year_set_active',
    'academic_year_delete',
    'academic_year_get',

    # Sessions & Live Scanner
    'teacher_session_open',
    'teacher_session_scan',
    'teacher_session_close',
    'teacher_session_summary',
    'teacher_manual_override_ajax',
    'attendance_scan_api',
]

