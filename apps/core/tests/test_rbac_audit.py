"""
# // ==============================================================================
# // KCC CLASSSTAMP - RBAC URL-WALK AUDIT (P2-1)
# // ==============================================================================
# // Subsystem: Quality Assurance — View Authorization
# // Description: RoleBasedAccessMiddleware only guards /admin/, /teacher/ and
# //   /student/. Most admin pages live outside those prefixes (/rooms/,
# //   /classes/, /validation/, /students/, /teachers/, /subjects/,
# //   /departments/, /programs/, /academic-years/). They are protected only by
# //   @role_required on the view. One missing decorator is a student/teacher
# //   access hole. This test walks every URL pattern and refuses an app view
# //   that is neither public, nor a documented shared-authenticated page, nor
# //   guarded by @role_required.
# //
# //   Denial UX is intentionally split and documented here:
# //     - Portal prefixes (/admin/, /teacher/, /student/): middleware 403.
# //     - Other admin pages: decorator 302 to the caller's dashboard.
# // ==============================================================================
"""

from django.contrib.admin.sites import site as django_admin_site
from django.urls import URLPattern, URLResolver, get_resolver
from django.test import TestCase


PUBLIC_EXACT = frozenset({
    "/",
    "/robots.txt",
    "/.well-known/security.txt",
    "/login",
    "/login/2fa/",
    "/password-reset/",
    "/password-reset/<str:token>/",
    "/register/",
    "/register/check-availability/",
    "/session/keepalive/",
    "/api/csp-report/",
    "/logout/",
    "/favicon.ico",
    "/service-worker.js",
})

# Any authenticated role. These views dispatch by Profile.role internally or
# are personal (own notifications, own documents, own messages).
SHARED_AUTH_PREFIXES = (
    "/dashboard/",
    "/notifications",
    "/api/notifications/",
    "/messages",
    "/documents/",
    "/api/push/",
    "/account/2fa/",
    "/excuses/calendar/",
    "/api/excuses/",
    "/info/",
    "/student/approval-waiting/",
)

# Admin-directory prefixes that must never be reachable by TEACHER or STUDENT.
ADMIN_ONLY_PREFIXES = (
    "/rooms",
    "/validation",
    "/departments",
    "/programs",
    "/subjects",
    "/academic-years",
    "/students",
    "/teachers",
)


def _is_django_admin(resolver: URLResolver) -> bool:
    return getattr(resolver, "namespace", "") == "admin" or resolver.url_patterns is django_admin_site.urls


def iter_views(patterns=None, prefix="/"):
    patterns = get_resolver().url_patterns if patterns is None else patterns
    for p in patterns:
        if isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p.callback, p.name
        elif isinstance(p, URLResolver):
            if _is_django_admin(p):
                continue
            yield from iter_views(p.url_patterns, prefix + str(p.pattern))


class RbacUrlWalkTests(TestCase):
    """P2-1: every non-public app view carries @role_required."""

    def _problems(self):
        problems = []
        for path, callback, name in iter_views():
            if not callable(callback) or hasattr(callback, "view_class"):
                continue
            if path in PUBLIC_EXACT:
                continue
            if any(path.startswith(prefix) for prefix in SHARED_AUTH_PREFIXES):
                continue
            if getattr(callback, "allowed_roles", None) is None:
                problems.append(f"{path} ({name or 'unnamed'}) has no @role_required")
        return problems

    def test_every_protected_view_has_role_required(self):
        self.assertEqual(self._problems(), [])

    def test_admin_directories_require_the_admin_role(self):
        """A decorator that exists but forgot ADMIN is the same hole."""
        for path, callback, name in iter_views():
            if not callable(callback) or hasattr(callback, "view_class"):
                continue
            if not any(path.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES):
                continue
            roles = getattr(callback, "allowed_roles", None)
            self.assertIsNotNone(roles, f"{path} ({name}) is unguarded")
            self.assertIn("ADMIN", roles, f"{path} ({name}) allows {roles}")

    def test_role_required_exposes_allowed_roles(self):
        """The marker the URL-walk reads must survive @wraps / outer decorators."""

        from apps.core.decorators import role_required
        from apps.core.models import Profile

        @role_required(Profile.ROLE_ADMIN)
        def sample(request):
            return request  # pragma: no cover

        self.assertEqual(sample.allowed_roles, (Profile.ROLE_ADMIN,))
