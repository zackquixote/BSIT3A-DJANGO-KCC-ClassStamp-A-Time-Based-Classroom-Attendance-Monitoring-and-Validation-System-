"""
# // ==============================================================================
# // KCC CLASSSTAMP - APPROVAL STATUS MIDDLEWARE
# // ==============================================================================
# // Subsystem: Request/Response Pipeline Security Guards
# // Description: Blocks unapproved students from student-portal features.
# //   PENDING / REJECTED students are redirected to /student/approval-waiting/.
# //   Teachers, admins, superusers and exempted paths pass through.
# //   Denied attempts are written to AuditEvent (path only, no payloads).
# //   The existing approved_required decorator stays in place (task rule 9).
# // ==============================================================================
"""

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect

from apps.core.models import AuditEvent, Profile

APPROVAL_WAITING_PATH = '/student/approval-waiting/'

DEFAULT_APPROVAL_EXEMPT_PREFIXES = (
    '/login/',
    '/logout/',
    '/static/',
    '/media/',
    '/service-worker.js',
    '/favicon.ico',
    APPROVAL_WAITING_PATH,
    # Django admin has its own authentication; teachers/admins are skipped
    # below anyway, but staff-only Django URLs must never trap a superuser
    # whose profile is somehow unapproved.
    '/admin/',
)


class ApprovalCheckMiddleware:
    """
    // Enforces Profile.approval_status == APPROVED for students accessing
    // protected student routes. Non-students are never gated.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        exempt = getattr(
            settings, 'APPROVAL_EXEMPT_PREFIXES', DEFAULT_APPROVAL_EXEMPT_PREFIXES
        )
        self.exempted_prefixes = tuple(exempt)

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if self._is_exempted(request.path):
            return self.get_response(request)

        profile = getattr(request.user, 'classstamp_profile', None)
        if profile is None or profile.role != Profile.ROLE_STUDENT:
            return self.get_response(request)

        if request.user.is_superuser:
            return self.get_response(request)

        if profile.approval_status == Profile.APPROVAL_APPROVED:
            return self.get_response(request)

        # Requirement 6.5: log the denied attempt without sensitive payloads.
        AuditEvent.objects.create(
            actor=request.user,
            action='ACCESS_DENIED_UNAPPROVED',
            object_type='Profile',
            object_id=str(profile.pk),
            reason=f'Attempted to access {request.path} with status {profile.approval_status}',
        )

        if request.path.startswith('/api/'):
            return JsonResponse(
                {'error': 'Your account is not approved yet.'},
                status=403,
            )

        # Requirement 6.2: redirect to the waiting page (loop-safe: the
        # waiting page itself is exempt).
        return redirect(APPROVAL_WAITING_PATH)

    def _is_exempted(self, path: str) -> bool:
        """Check if path is in the approval exemption list."""
        return any(path.startswith(prefix) for prefix in self.exempted_prefixes)
