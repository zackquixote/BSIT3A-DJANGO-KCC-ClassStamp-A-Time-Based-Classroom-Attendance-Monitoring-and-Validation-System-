"""
# // ==============================================================================
# // KCC CLASSSTAMP - SERVICES PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Business Logic Service Layer
# // Description: Encapsulates all domain business logic, keeping view controllers
# //   thin (HTTP-only) and services independently testable and reusable.
# //
# // Module layout:
# //   student_service.py    — Student directory queries, CSV bulk import pipeline
# //   approval_service.py   — Account approval/rejection workflow & QR provisioning
# //   auth_service.py       — User account creation (registration provisioning)
# //   academic_service.py   — Department & Program CRUD with audit trail emission
# // ==============================================================================
"""

from .academic_service import (
    create_or_update_department,
    delete_or_deactivate_department,
    create_or_update_program,
    delete_or_deactivate_program,
    create_or_update_subject,
    delete_or_deactivate_subject,
    assign_curriculum_subject,
    remove_curriculum_entry,
    create_or_update_academic_year,
    set_active_academic_year,
    delete_or_deactivate_academic_year,
    rollover_academic_year,
)
from .approval_service import (
    approve_student_registration,
    reject_student_registration,
)
from .auth_service import provision_student_account
from .attendance_service import build_attendance_matrix
from .class_service import ClassAssignmentError, assign_class
from .export_service import (
    export_program_students_csv,
    export_student_directory_csv,
    export_student_import_sample_csv,
)
from .student_service import (
    build_student_queryset,
    import_students_from_csv,
)
from .teacher_service import (
    provision_teacher_account,
    update_teacher_profile,
    toggle_teacher_active,
    set_teacher_active,
    reset_teacher_password,
    delete_or_deactivate_teacher,
)

from .holiday_service import (
    calculate_easter_sunday,
    get_philippine_holidays,
    seed_philippine_holidays,
)

from .anomaly_service import (
    RULE_TOKEN_REPLAY_ACROSS_SESSION,
    RULE_DUPLICATE_STAMP_ATTEMPT,
    RULE_RAPID_SCAN_PROXY,
    RULE_STAMP_AFTER_CLASS_END,
    RULE_STAMP_BEFORE_CLASS_START,
    RULE_SCHEDULE_CONFLICT,
    RULE_TOKEN_BRUTE_FORCE,
    RULE_POST_CLOSE_OVERRIDE,
    raise_flag,
    detect_token_replay,
    detect_duplicate_stamp,
    detect_rapid_scan,
    detect_off_window,
    detect_schedule_conflict,
    detect_token_bruteforce,
    detect_post_close_override,
)

__all__ = [
    # Academic CRUD
    'create_or_update_department',
    'delete_or_deactivate_department',
    'create_or_update_program',
    'delete_or_deactivate_program',
    'create_or_update_subject',
    'delete_or_deactivate_subject',
    'assign_curriculum_subject',
    'remove_curriculum_entry',
    'create_or_update_academic_year',
    'set_active_academic_year',
    'delete_or_deactivate_academic_year',
    'rollover_academic_year',
    # Teacher Management
    'provision_teacher_account',
    'update_teacher_profile',
    'toggle_teacher_active',
    'set_teacher_active',
    'reset_teacher_password',
    'delete_or_deactivate_teacher',
    # Approval workflow
    'approve_student_registration',
    'reject_student_registration',
    # Auth provisioning
    'provision_student_account',
    # Student directory & import
    'build_student_queryset',
    'import_students_from_csv',
    # Attendance matrix
    'build_attendance_matrix',
    # Class assignment
    'assign_class',
    'ClassAssignmentError',
    # CSV Exports
    'export_program_students_csv',
    'export_student_directory_csv',
    'export_student_import_sample_csv',
    # Holiday Calendar
    'calculate_easter_sunday',
    'get_philippine_holidays',
    'seed_philippine_holidays',
    # Anomaly / Fraud Detection
    'RULE_TOKEN_REPLAY_ACROSS_SESSION',
    'RULE_DUPLICATE_STAMP_ATTEMPT',
    'RULE_RAPID_SCAN_PROXY',
    'RULE_STAMP_AFTER_CLASS_END',
    'RULE_STAMP_BEFORE_CLASS_START',
    'RULE_SCHEDULE_CONFLICT',
    'RULE_TOKEN_BRUTE_FORCE',
    'RULE_POST_CLOSE_OVERRIDE',
    'raise_flag',
    'detect_token_replay',
    'detect_duplicate_stamp',
    'detect_rapid_scan',
    'detect_off_window',
    'detect_schedule_conflict',
    'detect_token_bruteforce',
    'detect_post_close_override',
]
