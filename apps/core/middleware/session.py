"""
# // ==============================================================================
# // KCC CLASSSTAMP - SESSION INACTIVITY TIMEOUT MIDDLEWARE
# // ==============================================================================
# // Subsystem: Campus Kiosk & Terminal Session Guards
# // Description: Terminates idle authenticated sessions after a configurable inactivity
# //   duration (default: 30 minutes / 1800s) to protect shared campus workstations.
# // ==============================================================================
"""

from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
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

    def __call__(self, request):
        if request.user.is_authenticated:
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
                            messages.warning(
                                request,
                                'Your session has expired due to inactivity. Please sign in again.'
                            )
                            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
                    except (ValueError, TypeError):
                        pass

                request.session['last_activity'] = now.isoformat()

        return self.get_response(request)
