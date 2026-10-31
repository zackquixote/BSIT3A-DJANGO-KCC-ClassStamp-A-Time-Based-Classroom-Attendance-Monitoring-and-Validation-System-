"""
# // ==============================================================================
# // KCC CLASSSTAMP - SERIALIZERS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Data Serialization Layer
# // Description: Provides clean, deterministic serialization of domain models
# //   into primitive Python dictionaries suitable for JsonResponse, AJAX responses,
# //   API outputs, and audit logs.
# // ==============================================================================
"""

from .academic_serializers import (
    serialize_academic_year,
    serialize_curriculum_entry,
    serialize_department,
    serialize_program,
    serialize_subject,
    serialize_subject_summary,
)
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
    'serialize_program',
    'serialize_subject',
    'serialize_subject_summary',
    'serialize_curriculum_entry',
    'serialize_academic_year',
    # Teacher
    'serialize_teacher',
    'serialize_teacher_summary',
    # Student
    'serialize_student_detail',
    'serialize_student_summary',
]
