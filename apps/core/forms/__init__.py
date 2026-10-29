"""
# // ==============================================================================
# // KCC CLASSSTAMP - FORMS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Django Form Validation Layer
# // Description: Re-exports all form classes for a clean flat import path:
# //
# //       from apps.core.forms import RegistrationForm, DepartmentForm, ProgramForm
# //
# // Module layout:
# //   registration_form.py — Student self-registration multi-field form
# //   academic_forms.py    — DepartmentForm and ProgramForm (admin CRUD)
# //   student_profile_form.py — Student self-service profile maintenance
# // ==============================================================================
"""

from .academic_forms import DepartmentForm, ProgramForm
from .registration_form import RegistrationForm
from .student_profile_form import StudentProfileForm

__all__ = [
    'RegistrationForm',
    'DepartmentForm',
    'ProgramForm',
    'StudentProfileForm',
]
