"""
# // ==============================================================================
# // KCC CLASSSTAMP - SERIALIZERS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Data Serialization Layer
# // Description: Provides clean, deterministic serialization of domain models
# //   into primitive Python dictionaries suitable for JsonResponse, AJAX responses,
# //   API outputs, and audit logs.
# //
# // Module layout:
# //   academic_serializers.py — Department and Program model serializers
# //   student_serializers.py  — Student profile and directory serializers
# //   audit_serializers.py    — AuditEvent activity serializers
# // ==============================================================================
"""

from .academic_serializers import (
    serialize_academic_year,
    serialize_academic_year_summary,
    serialize_curriculum_entry,
    serialize_department,
    serialize_department_summary,
    serialize_program,
    serialize_program_summary,
    serialize_subject,
    serialize_subject_summary,
)
from .audit_serializers import serialize_audit_event
from .student_serializers import (
    serialize_student_detail,
    serialize_student_summary,
)
from .teacher_serializers import (
    serialize_teacher,
    serialize_teacher_summary,
)

__all__ = [
    # Academic
    'serialize_department',
    'serialize_department_summary',
    'serialize_program',
    'serialize_program_summary',
    'serialize_subject',
    'serialize_subject_summary',
    'serialize_curriculum_entry',
    'serialize_academic_year',
    'serialize_academic_year_summary',
    # Teacher
    'serialize_teacher',
    'serialize_teacher_summary',
    # Student
    'serialize_student_detail',
    'serialize_student_summary',
    # Audit
    'serialize_audit_event',
]
