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
# //   Pre-auth sensitive surfaces (registration availability oracle and password
# //   reset) are throttled separately per IP for every client (authenticated or
# //   not): AUTH_LIMIT (RATE_LIMIT_AUTHSENSITIVE, default 30) per WINDOW_SECONDS.
# //   Counters: classstamp:rl:auth:<ip>. 429 shape and audit action match /api/.
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

# Pre-auth surfaces that were previously unlimited. Prefix match on request.path
# (query string is never included). /password-reset/ also covers the token
# confirm page, which is the same unauthenticated attack surface.
AUTH_SENSITIVE_PREFIXES = ('/register/check-availability/', '/password-reset/')


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
        # Separate anonymous-style limit for AUTH_SENSITIVE_PREFIXES. Read here
        # (not at import) so override_settings works for newly built middleware.
        self.auth_limit = getattr(settings, 'RATE_LIMIT_AUTHSENSITIVE', 30)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        path = request.path
        if self._is_auth_sensitive(path):
            return self._throttle_auth_sensitive(request)

        if not self._requires_rate_limiting(path):
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
            return self._too_many_requests(request, cache_key, count, limit, authenticated)

        return self.get_response(request)

    def _throttle_auth_sensitive(self, request):
        """Fixed-window per-IP throttle for pre-auth sensitive paths.

        // GET and POST share one bucket. Authenticated users are not given a
        // larger limit: these are pre-auth surfaces, so every client counts
        // against classstamp:rl:auth:<ip>.
        """
        cache_key = self._get_auth_cache_key(request)
        try:
            count = _bump_counter(cache_key, WINDOW_SECONDS)
        except Exception:
            # A cache outage must not take the page down; losing the throttle
            # is a security-relevant event and is logged, not silent.
            logger.warning(
                'Rate-limit cache unavailable; allowing request for %s',
                cache_key,
                exc_info=True,
            )
            return self.get_response(request)

        if count > self.auth_limit:
            # Bucket is per-IP anonymous-style even if a session is present.
            return self._too_many_requests(
                request, cache_key, count, self.auth_limit, False,
            )
        return self.get_response(request)

    def _too_many_requests(self, request, cache_key, count, limit, authenticated):
        """Same 429 shape as the /api/ throttle: Retry-After + text/plain."""
        self._audit_violation(request, cache_key, count, limit, authenticated)
        # Seconds remaining in the current 60s window, minimum 1.
        retry_after = max(1, WINDOW_SECONDS - int(time.time() % WINDOW_SECONDS))
        response = HttpResponse('Too Many Requests', status=429)
        response['Retry-After'] = str(retry_after)
        response['Content-Type'] = 'text/plain'
        return response

    def _requires_rate_limiting(self, path: str) -> bool:
        """Check if path should be rate limited. The real scan route is
        /api/attendance/scan/; there is no /student/scan/ route."""
        return path.startswith('/api/')

    def _is_auth_sensitive(self, path: str) -> bool:
        """True for the registration oracle and password-reset prefixes."""
        return path.startswith(AUTH_SENSITIVE_PREFIXES)

    def _get_cache_key(self, request, authenticated: bool, user=None) -> str:
        """Generate the per-identity fixed-window cache key."""
        if authenticated and user is not None:
            return f'classstamp:rl:user:{user.pk}'
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        return f'classstamp:rl:ip:{ip}'

    def _get_auth_cache_key(self, request) -> str:
        """Per-IP key for AUTH_SENSITIVE_PREFIXES; method is not in the key."""
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        return f'classstamp:rl:auth:{ip}'

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
