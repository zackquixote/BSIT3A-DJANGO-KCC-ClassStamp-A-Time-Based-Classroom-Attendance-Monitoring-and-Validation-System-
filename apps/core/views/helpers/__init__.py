"""
# // ==============================================================================
# // KCC CLASSSTAMP - VIEWS HELPERS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: View Layer Support Utilities
# // Description: Re-exports all helper functions and constants from each domain
# //   helper module so consumers can use a single flat import path:
# //
# //       from apps.core.views.helpers import _get_lock_state, _admin_dashboard_stats
# //
# // Module layout:
# //   auth_helpers.py      — Login rate-limiting, lockout helpers, registration validator
# //   dashboard_helpers.py — Role-specific KPI/stats aggregation helpers
# // ==============================================================================
"""

from .auth_helpers import (
    INVALID_LOGIN_MESSAGE,
    LOCK_DURATION,
    LOCKED_MESSAGE,
    MAX_FAILED_ATTEMPTS,
    _get_lock_state,
    _reset_lock_state,
    _set_lock_state,
    _validate_registration_data,
)
from .dashboard_helpers import (
    _admin_dashboard_stats,
    _student_dashboard_stats,
    _teacher_dashboard_stats,
    get_attendance_chart_data,
)

__all__ = [
    # Auth rate-limiting constants
    'MAX_FAILED_ATTEMPTS',
    'LOCK_DURATION',
    'INVALID_LOGIN_MESSAGE',
    'LOCKED_MESSAGE',
    # Auth helper functions
    '_reset_lock_state',
    '_get_lock_state',
    '_set_lock_state',
    '_validate_registration_data',
    # Dashboard stat helpers
    '_admin_dashboard_stats',
    '_teacher_dashboard_stats',
    '_student_dashboard_stats',
    'get_attendance_chart_data',
]
