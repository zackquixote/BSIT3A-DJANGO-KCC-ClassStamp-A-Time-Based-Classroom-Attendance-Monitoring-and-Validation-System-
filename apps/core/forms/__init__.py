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
# //   student_profile_form.py — Student self-service profile maintenance
# // ==============================================================================
"""

from .registration_form import RegistrationForm
from .student_profile_form import StudentAvatarForm, StudentProfileForm

__all__ = ['RegistrationForm']
