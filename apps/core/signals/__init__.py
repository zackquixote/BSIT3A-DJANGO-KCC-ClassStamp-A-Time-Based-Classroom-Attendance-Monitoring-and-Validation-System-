"""
# // ==============================================================================
# // KCC CLASSSTAMP - SIGNALS PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Domain Signals & Lifecycle Dispatchers
# // Description: Re-exports all signal receiver functions so importing `apps.core.signals`
# //   in `CoreConfig.ready()` registers all event listeners.
# //
# // Module layout:
# //   auth_signals.py — user_logged_in, user_logged_out, user_login_failed
# //   file_signals.py — post_delete profile proof file cleanup
# // ==============================================================================
"""

from .auth_signals import (
    log_user_login,
    log_user_login_failed,
    log_user_logout,
)
from .file_signals import cleanup_profile_proof_file

__all__ = [
    'log_user_login',
    'log_user_logout',
    'log_user_login_failed',
    'cleanup_profile_proof_file',
]
