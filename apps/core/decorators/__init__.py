"""
# // ==============================================================================
# // KCC CLASSSTAMP - DECORATORS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: View Authorization Layer
# // Description: Re-exports all route authorization decorators for flat import access:
# //
# //       from apps.core.decorators import role_required, approved_required
# //
# // Module layout:
# //   rbac.py — role_required and approved_required decorators
# // ==============================================================================
"""

from .rbac import (
    _get_profile,
    approved_required,
    role_required,
)

__all__ = [
    'role_required',
    'approved_required',
    '_get_profile',
]
