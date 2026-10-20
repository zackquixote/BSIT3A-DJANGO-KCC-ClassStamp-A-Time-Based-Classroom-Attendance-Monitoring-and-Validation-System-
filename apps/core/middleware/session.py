"""
# // ==============================================================================
# // KCC CLASSSTAMP - SESSION INACTIVITY TIMEOUT MIDDLEWARE
# // ==============================================================================
# // Subsystem: Campus Kiosk & Terminal Session Guards
# // Description: Terminates idle authenticated sessions after a configurable inactivity
# //   duration (default: 30 minutes / 1800s) to protect shared campus workstations.
# //
# // Hardening:
# //   1. AJAX/JSON 401: Returns HTTP 401 JSON for expired asynchronous API/fetch requests
# //      instead of breaking frontend JS with 302 HTML redirects.
# //   2. Background Polling Immunity: Heartbeat/live counter endpoints do not refresh
# //      the inactivity window, ensuring unattended tabs safely lock out.
# //   3. Database Write Throttling: Throttles session DB writes to once per minute.
# // ==============================================================================
"""

from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone


class SessionInactivityTimeoutMiddleware:
    """
    // Automatically terminates authenticated sessions after a configurable duration
    // of user inactivity (default: 30 minutes / 1800 seconds).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout_seconds = getattr(settings, 'SESSION_INACTIVITY_TIMEOUT', 1800)
        self.write_throttle_seconds = getattr(settings, 'SESSION_INACTIVITY_THROTTLE', 60)
        self.exempt_polling_paths = getattr(
            settings,
            'SESSION_TIMEOUT_EXEMPT_PATHS',
            (
                '/api/admin/pending-count/',
                '/api/admin/activity-feed/',
            )
        )

    @staticmethod
    def _is_ajax_or_json(request):
        return (
            request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
            or getattr(request, 'content_type', '') == 'application/json'
            or request.path.startswith('/api/')
        )

    def __call__(self, request):
        if getattr(request, 'user', None) and request.user.is_authenticated:
            # Exempt logout endpoint itself to prevent redirect loops
            if not request.path.startswith('/logout'):
                last_activity_str = request.session.get('last_activity')
                now = timezone.now()

                if last_activity_str:
                    try:
                        last_activity = datetime.fromisoformat(last_activity_str)
                        if timezone.is_naive(last_activity):
                            last_activity = timezone.make_aware(last_activity)

                        elapsed = (now - last_activity).total_seconds()
                        if elapsed > self.timeout_seconds:
                            auth_logout(request)
                            if self._is_ajax_or_json(request):
                                return JsonResponse(
                                    {
                                        'error': 'session_expired',
                                        'message': 'Your session has expired due to inactivity. Please sign in again.',
                                        'login_url': f"{settings.LOGIN_URL}?next={request.path}",
                                    },
                                    status=401,
                                )

                            messages.warning(
                                request,
                                'Your session has expired due to inactivity. Please sign in again.'
                            )
                            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

                        # Check if request is an automated background poll
                        is_polling = any(request.path.startswith(p) for p in self.exempt_polling_paths) or request.GET.get('heartbeat') == '1'
                        if not is_polling and elapsed >= self.write_throttle_seconds:
                            request.session['last_activity'] = now.isoformat()

                    except (ValueError, TypeError):
                        request.session['last_activity'] = now.isoformat()
                else:
                    request.session['last_activity'] = now.isoformat()

        return self.get_response(request)
