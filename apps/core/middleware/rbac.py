"""
# // ==============================================================================
# // KCC CLASSSTAMP - ROLE-BASED ACCESS CONTROL MIDDLEWARE
# // ==============================================================================
# // Subsystem: Request/Response Pipeline Security Guards
# // Description: Route-level defense in depth. Rejects authenticated users whose
# //   Profile.role does not match the portal prefix they are requesting, before
# //   any view (and therefore any view decorator) runs.
# //
# //   Actual portal prefixes are /admin/, /teacher/ and /student/.
# //   Anonymous users are redirected to the real login route before role checking.
# //   Authenticated role mismatches get HTTP 403.
# //   Superusers / Django staff are never locked out of Django's /admin/ site.
# //   View decorators stay in place (task rule 9) until route-level tests prove
# //   equivalent protection.
# // ==============================================================================
"""

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from apps.core.models import Profile

# Prefixes that carry no role restriction (public or self-contained).
DEFAULT_ROLE_EXEMPT_PREFIXES = (
    '/',
    '/login/',
    '/logout/',
    '/static/',
    '/media/',
    '/service-worker.js',
    '/favicon.ico',
    '/info/',
    '/users/',
)


class RoleBasedAccessMiddleware:
    """
    // Enforces role-based URL path restrictions at the middleware layer.
    // Maps portal prefixes to Profile roles:
    //   /admin/    -> ADMIN   (Django admin + app admin pages)
    //   /teacher/  -> TEACHER
    //   /student/  -> STUDENT
    """

    ROLE_PREFIXES = (
        ('/admin/', Profile.ROLE_ADMIN),
        ('/teacher/', Profile.ROLE_TEACHER),
        ('/student/', Profile.ROLE_STUDENT),
    )

    def __init__(self, get_response):
        self.get_response = get_response
        exempt = getattr(settings, 'ROLE_EXEMPT_PREFIXES', DEFAULT_ROLE_EXEMPT_PREFIXES)
        self.exempted_prefixes = tuple(exempt)

    def __call__(self, request):
        if not request.user.is_authenticated:
            # Requirement 5.5: redirect anonymous users to login before any
            # role check. Preserve ?next= so login returns them to the target.
            if self._is_exempted(request.path):
                return self.get_response(request)
            if self._required_role(request.path) is not None:
                login_url = settings.LOGIN_URL
                if request.path and request.path != '/':
                    from urllib.parse import quote
                    separator = '&' if '?' in login_url else '?'
                    return redirect(f'{login_url}{separator}next={quote(request.path)}')
                return redirect(login_url)
            return self.get_response(request)

        if self._is_exempted(request.path):
            return self.get_response(request)

        required_role = self._required_role(request.path)
        if required_role is None:
            return self.get_response(request)

        if self._has_role(request, required_role):
            return self.get_response(request)

        return HttpResponseForbidden(
            'You do not have permission to access this portal.'
        )

    def _is_exempted(self, path: str) -> bool:
        """Check if path is in the RBAC exemption list.

        The root path is an exact match only: treating '/' as a startswith
        prefix would exempt every URL on the site.
        """
        if path == '/':
            return True
        return any(
            path.startswith(prefix)
            for prefix in self.exempted_prefixes
            if prefix != '/'
        )

    def _required_role(self, path: str):
        """Return the Profile role required for this path, or None."""
        for prefix, role in self.ROLE_PREFIXES:
            if path.startswith(prefix):
                return role
        return None

    def _has_role(self, request, required_role: str) -> bool:
        """
        // Superusers satisfy the ADMIN and TEACHER gates (matching the old
        // role_required decorators, which allowed a superuser through any
        // guard that listed ROLE_ADMIN). They do not inherit the STUDENT
        // portal. Django staff without a ClassStamp profile may still reach
        // Django's /admin/ site. Everyone else needs a matching profile role.
        """
        if request.user.is_superuser and required_role != Profile.ROLE_STUDENT:
            return True

        profile = getattr(request.user, 'classstamp_profile', None)
        if profile is None:
            if required_role == Profile.ROLE_ADMIN and (
                request.user.is_staff or request.user.is_superuser
            ):
                return True
            return False

        return profile.role == required_role
