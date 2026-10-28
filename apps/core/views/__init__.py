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
    admin_reset_user_password,
    check_registration_availability,
    login_view,
    logout_view,
    register_view,
    session_keepalive,
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
    admin_live_stream,
    dashboard_redirect,
    student_dashboard,
    teacher_dashboard,
)

# // ------------------------------------------------------------------------------
# // 2b. Student Self-Service Portal (QR badge & personal attendance ledger)
# // ------------------------------------------------------------------------------
from .student_portal_views import (
    student_attendance_log,
    student_qr_badge,
    student_qr_token_api,
    student_offline_badge_issue,
)

# // ------------------------------------------------------------------------------
# // 3. Account Validation & Registrar Dossier Subsystem
# // ------------------------------------------------------------------------------
from .validation_views import (
    approve_student,
    batch_validation_action,
    recently_reviewed_list,
    reject_student,
    validation_detail,
    validation_dossier_json,
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
# // 5b. Excuse Slip Workflow Subsystem
# // ------------------------------------------------------------------------------
from .excuse_views import (
    excuse_slip_review_ajax,
    student_excuse_slips,
    teacher_excuse_slips,
)

# // ------------------------------------------------------------------------------
# // 5. Degree Program & Curriculum Subsystem
# // ------------------------------------------------------------------------------
from .program_views import (
    program_curriculum_list,
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
    student_profile_update_ajax,
    student_promote_all,
    student_qr_reset_ajax,
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
    anomaly_bulk_action,
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
    subject_curriculum_assign,
    subject_curriculum_remove,
    subject_lookup_json,
)

# // ------------------------------------------------------------------------------
# // 9. Teacher & Faculty Management Subsystem
# // ------------------------------------------------------------------------------
from .teacher_views import (
    admin_reset_teacher_password,
    bulk_teacher_operation,
    teacher_analytics_json,
    teacher_assign_class_ajax,
    teacher_create,
    teacher_delete,
    teacher_get,
    teacher_list,
    teacher_reassign_ajax,
    teacher_toggle,
    teacher_unassign_class_ajax,
    teacher_update,
)

# // ------------------------------------------------------------------------------
# // 9b. Disaster Recovery / Database Backup Subsystem
# // ------------------------------------------------------------------------------
from .backup_views import (
    admin_db_backup,
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
    academic_year_rollover,
)

# // ------------------------------------------------------------------------------
# // 11. Class Section, Schedule & Enrollment Subsystem
# // ------------------------------------------------------------------------------
from .class_views import (
    class_attendance_matrix,
    class_list,
    class_roster_enroll,
    class_roster_enroll_batch,
    class_roster_get,
    class_roster_remove,
    class_save,
    class_slot_delete,
    class_slot_save,
    class_toggle,
    class_wizard_options,
    class_wizard_save,
    class_wizard_setup,
    class_wizard_slots_check,
)

# // ------------------------------------------------------------------------------
# // 12. Classroom Attendance Session & Live QR Scanner Subsystem
# // ------------------------------------------------------------------------------
from .session_views import (
    attendance_scan_api,
    teacher_attendance_matrix,
    teacher_class_term_export,
    teacher_manual_override_ajax,
    teacher_session_close,
    teacher_session_export,
    teacher_session_history,
    teacher_session_history_export,
    teacher_session_open,
    teacher_session_roster_json,
    teacher_session_scan,
    teacher_session_summary,
)

# // ------------------------------------------------------------------------------
# // 13. Academic Calendar & Institutional Event Subsystem
# // ------------------------------------------------------------------------------
from .calendar_views import (
    admin_calendar_event_cancel,
    admin_calendar_event_delete,
    admin_calendar_event_get,
    admin_calendar_event_reschedule,
    admin_calendar_event_save,
    admin_calendar_events_json,
    admin_calendar_sync_holidays,
    admin_calendar_view,
)

__all__ = [
    # Academic Calendar
    'admin_calendar_view',
    'admin_calendar_events_json',
    'admin_calendar_event_get',
    'admin_calendar_event_save',
    'admin_calendar_event_reschedule',
    'admin_calendar_event_cancel',
    'admin_calendar_event_delete',
    'admin_calendar_sync_holidays',
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
    'admin_live_stream',
    'teacher_dashboard',
    'student_dashboard',
    'student_qr_badge',
    'student_qr_token_api',
    'student_offline_badge_issue',
    'student_attendance_log',
    '_admin_dashboard_stats',
    '_teacher_dashboard_stats',
    '_student_dashboard_stats',

    # Account Validation
    'validation_queue',
    'validation_hub',
    'validation_pending_queue',
    'validation_detail',
    'validation_dossier_json',
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
    'student_excuse_slips',
    'teacher_excuse_slips',
    'excuse_slip_review_ajax',
    'program_curriculum_list',

    # Student Masterlist & Ingestion
    'student_directory',
    'student_directory_export_csv',
    'student_directory_import_csv',
    'student_import_sample_csv',
    'student_profile_update_ajax',
    'student_promote_all',
    'student_qr_reset_ajax',

    # Audit Log & AJAX Feeds
    'admin_audit_log',
    'admin_activity_feed_json',
    'admin_pending_count_json',

    # Subjects & Curriculum
    'subject_list',
    'subject_save',
    'subject_delete',
    'subject_get',
    'subject_curriculum_assign',
    'subject_curriculum_remove',
    'subject_lookup_json',

    # Teachers & Faculty
    'teacher_list',
    'teacher_create',
    'teacher_update',
    'teacher_reassign_ajax',
    'teacher_toggle',
    'teacher_delete',
    'teacher_get',
    'teacher_analytics_json',
    'bulk_teacher_operation',
    'admin_reset_teacher_password',

    # Disaster Recovery
    'admin_db_backup',

    # Academic Years
    'academic_year_list',
    'academic_year_save',
    'academic_year_set_active',
    'academic_year_delete',
    'academic_year_get',
    'academic_year_rollover',

    # Class Sections & Schedules
    'class_list',
    'class_save',
    'class_toggle',
    'class_slot_save',
    'class_slot_delete',
    'class_wizard_options',
    'class_wizard_save',
    'class_wizard_slots_check',
    'class_wizard_setup',
    'class_roster_get',
    'class_roster_enroll',
    'class_roster_enroll_batch',
    'class_roster_remove',
    'class_attendance_matrix',

    # Sessions & Live Scanner
    'teacher_session_open',
    'teacher_session_scan',
    'teacher_session_roster_json',
    'teacher_session_close',
    'teacher_session_summary',
    'teacher_session_export',
    'teacher_session_history',
    'teacher_session_history_export',
    'teacher_attendance_matrix',
    'teacher_class_term_export',
    'teacher_manual_override_ajax',
    'attendance_scan_api',
]

