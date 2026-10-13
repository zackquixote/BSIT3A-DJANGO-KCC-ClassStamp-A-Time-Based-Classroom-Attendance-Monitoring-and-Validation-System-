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
    reject_student,
    validation_detail,
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
    'validation_detail',
    'approve_student',
    'reject_student',

    # Departments
    'department_list',
    'department_save',
    'department_delete',

    # Programs
    'program_list',
    'program_save',
    'program_delete',

    # Student Masterlist & Ingestion
    'student_directory',
    'student_directory_export_csv',
    'student_directory_import_csv',
    'student_import_sample_csv',
]
