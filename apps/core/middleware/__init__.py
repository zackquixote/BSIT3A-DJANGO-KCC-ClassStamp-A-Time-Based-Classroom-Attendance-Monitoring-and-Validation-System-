"""
# // ==============================================================================
# // KCC CLASSSTAMP - MIDDLEWARE PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Request/Response Pipeline Security Guards
# // Description: Re-exports all middleware classes for flat import access:
# //
# //       from apps.core.middleware import (
# //           RequestCorrelationIdMiddleware,
# //           AttachProfileMiddleware,
# //           DisableBrowserCacheMiddleware,
# //           SessionInactivityTimeoutMiddleware,
# //           SecurityHeadersMiddleware,
# //           RoleBasedAccessMiddleware,
# //           ApprovalCheckMiddleware,
# //           RateLimitMiddleware,
# //       )
# //
# // Module layout:
# //   correlation.py — RequestCorrelationIdMiddleware (UUID request.id & X-Request-ID)
# //   profile.py     — AttachProfileMiddleware (attaches request.profile)
# //   cache.py       — DisableBrowserCacheMiddleware (no-cache headers)
# //   session.py     — SessionInactivityTimeoutMiddleware (kiosk auto-logout)
# //   security.py    — SecurityHeadersMiddleware (defense-in-depth & CSP headers)
# //   rbac.py        — RoleBasedAccessMiddleware (portal prefix role gates)
# //   approval.py    — ApprovalCheckMiddleware (unapproved student gate)
# //   ratelimit.py   — RateLimitMiddleware (fixed-window /api/ throttle)
# // ==============================================================================
"""

from .approval import ApprovalCheckMiddleware
from .cache import DisableBrowserCacheMiddleware
from .correlation import RequestCorrelationIdMiddleware
from .profile import AttachProfileMiddleware
from .ratelimit import RateLimitMiddleware
from .rbac import RoleBasedAccessMiddleware
from .security import SecurityHeadersMiddleware
from .session import SessionInactivityTimeoutMiddleware

__all__ = [
    'RequestCorrelationIdMiddleware',
    'AttachProfileMiddleware',
    'DisableBrowserCacheMiddleware',
    'SessionInactivityTimeoutMiddleware',
    'SecurityHeadersMiddleware',
    'RoleBasedAccessMiddleware',
    'ApprovalCheckMiddleware',
    'RateLimitMiddleware',
]
