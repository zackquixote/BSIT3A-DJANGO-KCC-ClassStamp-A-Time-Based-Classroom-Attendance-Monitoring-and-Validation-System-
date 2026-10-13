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
)
from .approval_service import (
    approve_student_registration,
    reject_student_registration,
)
from .auth_service import provision_student_account
from .student_service import (
    build_student_queryset,
    import_students_from_csv,
)

__all__ = [
    # Academic CRUD
    'create_or_update_department',
    'delete_or_deactivate_department',
    'create_or_update_program',
    'delete_or_deactivate_program',
    # Approval workflow
    'approve_student_registration',
    'reject_student_registration',
    # Auth provisioning
    'provision_student_account',
    # Student directory & import
    'build_student_queryset',
    'import_students_from_csv',
]
