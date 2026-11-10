"""
# // ==============================================================================
# // KCC CLASSSTAMP - API RATE LIMIT MIDDLEWARE
# // ==============================================================================
# // Subsystem: Request/Response Pipeline Security Guards
# // Description: Fixed-window throttling for /api/ endpoints (including the real
# //   /api/attendance/scan/ route). Authenticated users: 100 req/min by default;
# //   anonymous: 20 req/min. The stricter per-operator/per-IP scan throttle in
# //   session_views stays in place as an additional layer.
# //
# //   Counters use atomic cache add/incr (the existing _bump_counter pattern)
# //   so concurrent workers cannot under-count. Production must point every
# //   worker at a shared cache backend; LocMem is per-process only.
# //
# //   429 responses carry an accurate Retry-After (seconds left in the window).
# //   Repeated violations are audited with throttled logging so an attacker
# //   cannot flood the audit table.
# // ==============================================================================
"""

import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from apps.core.models import AuditEvent

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
# Audit the first exceedance, then every Nth further violation in the window.
AUDIT_EVERY_N = 10


def _bump_counter(key, window):
    """
    // Atomically increment a fixed-window counter, creating it with a TTL.
    // Mirrors session_views._bump_counter; duplicated here because middleware
    // must not import the views layer.
    """
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 1, window)
        return 1


class RateLimitMiddleware:
    """
    // Applies rate limiting to API endpoints to prevent abuse.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'RATE_LIMIT_ENABLE', True)
        self.authenticated_limit = getattr(settings, 'RATE_LIMIT_AUTHENTICATED', 100)
        self.anonymous_limit = getattr(settings, 'RATE_LIMIT_ANONYMOUS', 20)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        if not self._requires_rate_limiting(request.path):
            return self.get_response(request)

        user = getattr(request, 'user', None)
        authenticated = bool(user and user.is_authenticated)
        limit = self.authenticated_limit if authenticated else self.anonymous_limit
        cache_key = self._get_cache_key(request, authenticated, user)

        try:
            count = _bump_counter(cache_key, WINDOW_SECONDS)
        except Exception:
            # A cache outage must not take the API down; losing the throttle
            # is a security-relevant event and is logged, not silent.
            logger.warning(
                'Rate-limit cache unavailable; allowing request for %s',
                cache_key,
                exc_info=True,
            )
            return self.get_response(request)

        if count > limit:
            self._audit_violation(request, cache_key, count, limit, authenticated)
            # Seconds remaining in the current 60s window, minimum 1.
            retry_after = max(1, WINDOW_SECONDS - int(time.time() % WINDOW_SECONDS))
            response = HttpResponse('Too Many Requests', status=429)
            response['Retry-After'] = str(retry_after)
            response['Content-Type'] = 'text/plain'
            return response

        return self.get_response(request)

    def _requires_rate_limiting(self, path: str) -> bool:
        """Check if path should be rate limited. The real scan route is
        /api/attendance/scan/; there is no /student/scan/ route."""
        return path.startswith('/api/')

    def _get_cache_key(self, request, authenticated: bool, user=None) -> str:
        """Generate the per-identity fixed-window cache key."""
        if authenticated and user is not None:
            return f'classstamp:rl:user:{user.pk}'
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        return f'classstamp:rl:ip:{ip}'

    def _audit_violation(self, request, cache_key, count, limit, authenticated):
        """
        // Throttled audit: write the first exceedance of a window, then only
        // every AUDIT_EVERY_N-th further hit, so a flood cannot fill the
        // audit table. The count itself is the flood signal.
        """
        if count != limit + 1 and (count - limit) % AUDIT_EVERY_N != 0:
            return

        identity = (
            f'user:{request.user.pk}' if authenticated
            else f'ip:{request.META.get("REMOTE_ADDR", "unknown")}'
        )
        try:
            AuditEvent.objects.create(
                actor=request.user if authenticated else None,
                action='RATE_LIMIT_EXCEEDED',
                object_type='Request',
                object_id=cache_key,
                reason=f'{count} requests in {WINDOW_SECONDS}s window (limit {limit}) for {identity}',
            )
        except Exception:
            # Never let audit writing break the 429 response.
            logger.warning('Failed to audit rate-limit violation', exc_info=True)
