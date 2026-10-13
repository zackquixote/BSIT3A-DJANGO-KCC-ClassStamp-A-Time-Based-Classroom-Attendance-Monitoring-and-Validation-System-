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
    serialize_department,
    serialize_department_summary,
    serialize_program,
    serialize_program_summary,
)
from .audit_serializers import serialize_audit_event
from .student_serializers import (
    serialize_student_detail,
    serialize_student_summary,
)

__all__ = [
    'serialize_department',
    'serialize_department_summary',
    'serialize_program',
    'serialize_program_summary',
    'serialize_student_detail',
    'serialize_student_summary',
    'serialize_audit_event',
]
