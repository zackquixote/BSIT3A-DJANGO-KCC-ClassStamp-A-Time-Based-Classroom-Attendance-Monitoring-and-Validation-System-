"""
# // ==============================================================================
# // KCC CLASSSTAMP - MODELS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Core ORM — Domain Model Registry
# // Description: Re-exports every model from each domain module so that all
# //   existing imports of the form:
# //
# //       from apps.core.models import Profile, Department, AuditEvent
# //       from .models import Profile, AuditEvent
# //
# //   continue to work without any change to views, tests, or migrations.
# //
# // Module layout (mirrors apps/core/views/ and apps/core/tests/ structure):
# //   academic.py    — Department, Program, Subject, Curriculum, AcademicYear
# //   profile.py     — Profile (RBAC persona, QR secret, approval workflow)
# //   classroom.py   — Class, ClassSlot, Enrollment
# //   attendance.py  — ClassSession, AttendanceRecord, StampAttempt
# //   audit.py       — AnomalyFlag, ReviewAction, AuditEvent
# // ==============================================================================
"""

# // Academic Hierarchy
from .academic import (
    AcademicYear,
    Curriculum,
    Department,
    Program,
    Subject,
)

# // Identity & RBAC
from .profile import Profile

# // Classroom Structure & Rosters
from .classroom import (
    Class,
    ClassSlot,
    Enrollment,
)

# // Time-Based Attendance Engine
from .attendance import (
    AttendanceRecord,
    ClassSession,
    StampAttempt,
)

# // Fraud Detection & Audit Trail
from .audit import (
    AnomalyFlag,
    AuditEvent,
    ReviewAction,
)

__all__ = [
    # Academic
    'AcademicYear',
    'Curriculum',
    'Department',
    'Program',
    'Subject',
    # Identity
    'Profile',
    # Classroom
    'Class',
    'ClassSlot',
    'Enrollment',
    # Attendance
    'AttendanceRecord',
    'ClassSession',
    'StampAttempt',
    # Audit
    'AnomalyFlag',
    'AuditEvent',
    'ReviewAction',
]
