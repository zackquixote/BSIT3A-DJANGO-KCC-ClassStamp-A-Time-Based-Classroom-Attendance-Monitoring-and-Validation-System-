"""
# // ==============================================================================
# // KCC CLASSSTAMP - PHASE 1 SECURITY MIDDLEWARE TESTS
# // ==============================================================================
# // Covers tasks 1.2 (RBAC middleware), 1.3 (approval middleware + waiting
# // page), 1.4 (API rate limiting), and 1.5 (CSP nonce / report-only / report
# // endpoint). Session-cookie settings are covered in test_session_security.
# // ==============================================================================
"""

from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
import json

from apps.core.middleware import (
    ApprovalCheckMiddleware,
    RateLimitMiddleware,
    RoleBasedAccessMiddleware,
    SecurityHeadersMiddleware,
)
from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    ExcuseSlip,
    Profile,
    Program,
    Subject,
)

User = get_user_model()


def _get_response_stub(request):
    from django.http import HttpResponse

    return HttpResponse('ok')


class RbacMiddlewareTests(TestCase):
    """Portal prefix role gates, exemptions, anonymous redirect, superuser."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = RoleBasedAccessMiddleware(_get_response_stub)
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.teacher_user = User.objects.create_user(username='rbac_teacher')
        Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.student_user = User.objects.create_user(username='rbac_student')
        Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-3001', approval_status=Profile.APPROVAL_APPROVED,
        )
        self.admin_user = User.objects.create_user(username='rbac_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

    def _process(self, path, user=None):
        request = self.factory.get(path)
        request.user = user if user is not None else AnonymousUser()
        return self.middleware(request)

    def test_anonymous_is_redirected_to_login_for_portal_paths(self):
        response = self._process('/teacher/dashboard/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)
        self.assertIn('/teacher/dashboard/', response.url)

    def test_root_path_is_exempt_and_does_not_swallow_other_paths(self):
        response = self._process('/')
        self.assertEqual(response.status_code, 200)
        # A startswith('/') exemption would have returned 200 here too.
        response = self._process('/teacher/dashboard/')
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_access_teacher_portal(self):
        response = self._process('/teacher/dashboard/', self.student_user)
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_access_admin_portal(self):
        response = self._process('/admin/dashboard/', self.teacher_user)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_admin_portal(self):
        response = self._process('/admin/dashboard/', self.admin_user)
        self.assertEqual(response.status_code, 200)

    def test_teacher_can_access_teacher_portal(self):
        response = self._process('/teacher/dashboard/', self.teacher_user)
        self.assertEqual(response.status_code, 200)

    def test_student_can_access_student_portal(self):
        response = self._process('/student/dashboard/', self.student_user)
        self.assertEqual(response.status_code, 200)

    def test_nested_portal_paths_are_gated(self):
        response = self._process('/teacher/session/1/scan/', self.student_user)
        self.assertEqual(response.status_code, 403)
        response = self._process('/student/classes/join/', self.teacher_user)
        self.assertEqual(response.status_code, 403)

    def test_superuser_without_profile_is_not_locked_out_of_admin(self):
        su = User.objects.create_superuser(username='rbac_su', password='Super-Secret-2026!')
        response = self._process('/admin/', su)
        self.assertNotEqual(response.status_code, 403)

    def test_superuser_reaches_teacher_tools_but_not_student_portal(self):
        # Old role_required(TEACHER, ADMIN) decorators let a superuser through
        # any guard that listed ADMIN. Preserve that for teacher tools; the
        # student portal stays role-gated.
        su = User.objects.create_superuser(username='rbac_su2', password='Super-Secret-2026!')
        self.assertEqual(self._process('/teacher/dashboard/', su).status_code, 200)
        self.assertEqual(self._process('/student/dashboard/', su).status_code, 403)

    def test_non_portal_paths_pass_for_authenticated_users(self):
        response = self._process('/notifications/', self.student_user)
        self.assertEqual(response.status_code, 200)

    def test_django_admin_login_redirects_anonymous_to_site_login(self):
        # Requirement 5.5: anonymous users hit the login page before role checks.
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        # LOGIN_URL is '/'; the middleware preserves ?next= (slashes stay
        # unescaped because quote() treats '/' as safe) so sign-in returns
        # the user to /admin/.
        self.assertEqual(response.url, f'{settings.LOGIN_URL}?next=/admin/')


class ApprovalMiddlewareTests(TestCase):
    """Unapproved students are redirected to the waiting page; others pass."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = ApprovalCheckMiddleware(_get_response_stub)
        self.pending_user = User.objects.create_user(username='appr_pending')
        self.pending = Profile.objects.create(
            user=self.pending_user, role=Profile.ROLE_STUDENT,
            student_number='2026-3002', approval_status=Profile.APPROVAL_PENDING,
        )
        self.rejected_user = User.objects.create_user(username='appr_rejected')
        self.rejected = Profile.objects.create(
            user=self.rejected_user, role=Profile.ROLE_STUDENT,
            student_number='2026-3003', approval_status=Profile.APPROVAL_REJECTED,
        )
        self.approved_user = User.objects.create_user(username='appr_ok')
        Profile.objects.create(
            user=self.approved_user, role=Profile.ROLE_STUDENT,
            student_number='2026-3004', approval_status=Profile.APPROVAL_APPROVED,
        )
        self.teacher_user = User.objects.create_user(username='appr_teacher')
        Profile.objects.create(user=self.teacher_user, role=Profile.ROLE_TEACHER)

    def _process(self, path, user):
        request = self.factory.get(path)
        request.user = user
        return self.middleware(request)

    def test_pending_student_is_redirected_to_waiting_page(self):
        response = self._process('/student/dashboard/', self.pending_user)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/student/approval-waiting/')
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.pending_user, action='ACCESS_DENIED_UNAPPROVED',
            ).exists()
        )

    def test_rejected_student_is_redirected_to_waiting_page(self):
        response = self._process('/student/classes/join/', self.rejected_user)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/student/approval-waiting/')

    def test_waiting_page_itself_does_not_loop(self):
        response = self._process('/student/approval-waiting/', self.pending_user)
        self.assertEqual(response.status_code, 200)

    def test_approved_student_passes(self):
        response = self._process('/student/dashboard/', self.approved_user)
        self.assertEqual(response.status_code, 200)

    def test_teacher_is_not_approval_gated(self):
        response = self._process('/teacher/dashboard/', self.teacher_user)
        self.assertEqual(response.status_code, 200)

    def test_api_request_gets_403_json_not_a_redirect(self):
        response = self._process('/api/student/qr-token/', self.pending_user)
        self.assertEqual(response.status_code, 403)

    def test_waiting_page_view_renders_for_pending_student(self):
        self.client.force_login(self.pending_user)
        response = self.client.get(reverse('student_approval_waiting'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pending approval')

    def test_pending_student_hitting_student_join_is_redirected(self):
        self.client.force_login(self.pending_user)
        response = self.client.get(reverse('student_join_class'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/student/approval-waiting/')


class RateLimitMiddlewareTests(TestCase):
    """Fixed-window /api/ throttle: 100 authed, 20 anon, Retry-After, audit."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _middleware(self):
        return RateLimitMiddleware(_get_response_stub)

    def test_anonymous_exceeds_20_and_gets_429_with_retry_after(self):
        mw = self._middleware()
        last = None
        for _ in range(21):
            request = self.factory.get('/api/nonexistent/')
            last = mw(request)
        self.assertEqual(last.status_code, 429)
        retry_after = int(last['Retry-After'])
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 60)

    def test_authenticated_exceeds_100_and_gets_429(self):
        user = User.objects.create_user(username='rl_user')
        mw = self._middleware()
        last = None
        for _ in range(101):
            request = self.factory.get('/api/nonexistent/')
            request.user = user
            last = mw(request)
        self.assertEqual(last.status_code, 429)
        self.assertTrue(
            AuditEvent.objects.filter(action='RATE_LIMIT_EXCEEDED').exists()
        )

    def test_non_api_paths_are_not_limited(self):
        user = User.objects.create_user(username='rl_user2')
        mw = self._middleware()
        for _ in range(150):
            request = self.factory.get('/notifications/')
            request.user = user
            response = mw(request)
            self.assertEqual(response.status_code, 200)

    @override_settings(RATE_LIMIT_ENABLE=False)
    def test_disabled_throttle_allows_unlimited(self):
        mw = self._middleware()
        for _ in range(25):
            request = self.factory.get('/api/nonexistent/')
            self.assertEqual(mw(request).status_code, 200)

    def test_real_scan_route_is_covered(self):
        mw = self._middleware()
        last = None
        for _ in range(21):
            request = self.factory.post('/api/attendance/scan/')
            last = mw(request)
        self.assertEqual(last.status_code, 429)

    def test_first_violation_is_audited_not_every_hit(self):
        user = User.objects.create_user(username='rl_audit')
        mw = self._middleware()
        for _ in range(105):
            request = self.factory.get('/api/nonexistent/')
            request.user = user
            mw(request)
        events = AuditEvent.objects.filter(
            action='RATE_LIMIT_EXCEEDED', actor=user,
        )
        # First exceedance (101) + every 10th after that (110, 120...) = 3.
        self.assertLessEqual(events.count(), 5)
        self.assertGreaterEqual(events.count(), 1)


class CspMiddlewareTests(TestCase):
    """Per-request nonce, enforced default, report-only toggle, report endpoint."""

    def setUp(self):
        cache.clear()

    def test_nonce_is_unique_across_requests_and_never_on_middleware_self(self):
        mw = SecurityHeadersMiddleware(_get_response_stub)
        request_a = RequestFactory().get('/')
        mw(request_a)
        request_b = RequestFactory().get('/')
        mw(request_b)
        self.assertIsNotNone(getattr(request_a, 'csp_nonce', None))
        self.assertNotEqual(request_a.csp_nonce, request_b.csp_nonce)
        self.assertFalse(hasattr(mw, 'nonce'))

    def test_enforced_header_by_default_with_nonce(self):
        # Enforcement went live after browser verification (task 6.3).
        response = self.client.get(reverse('login'))
        csp = response.headers.get('Content-Security-Policy', '')
        self.assertIn("default-src 'self'", csp)
        self.assertIn('nonce-', csp)
        self.assertIn("script-src 'self'", csp)
        script_part = csp.split('script-src')[1].split(';')[0]
        self.assertNotIn("'unsafe-inline'", script_part)
        self.assertIn('report-uri /api/csp-report/', csp)
        self.assertNotIn('cdnjs.cloudflare.com', csp)

    @override_settings(CSP_ENFORCE=False)
    def test_report_only_mode_uses_the_report_only_header(self):
        response = self.client.get(reverse('login'))
        self.assertIn('Content-Security-Policy-Report-Only', response.headers)
        self.assertNotIn('Content-Security-Policy', response.headers)

    @override_settings(CSP_ENABLED=False)
    def test_disabled_csp_omits_the_header(self):
        response = self.client.get(reverse('login'))
        self.assertNotIn('Content-Security-Policy', response.headers)
        self.assertNotIn('Content-Security-Policy-Report-Only', response.headers)

    def test_base_template_inline_scripts_carry_nonce(self):
        # Auth pages are standalone; theme/base.html (and its two every-page
        # inline scripts) renders on authenticated portal pages.
        user = User.objects.create_user(username='nonce_user', password='Str0ng-Pass-2026!')
        Profile.objects.create(user=user, role=Profile.ROLE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse('notification_list'))
        body = response.content.decode('utf-8')
        nonce = None
        csp = response.headers.get(
            'Content-Security-Policy',
            response.headers.get('Content-Security-Policy-Report-Only', ''),
        )
        for part in csp.split(';'):
            if part.strip().startswith('script-src'):
                for token in part.split():
                    if token.startswith("'nonce-"):
                        nonce = token[len("'nonce-"):-1]
        self.assertIsNotNone(nonce)
        self.assertIn(f'nonce="{nonce}"', body)

    def test_csp_report_endpoint_records_audit_event(self):
        payload = {
            'csp-report': {
                'violated-directive': 'script-src',
                'blocked-uri': 'inline',
                'source-file': 'http://testserver/login/',
                'line-number': 11,
            }
        }
        response = self.client.post(
            reverse('csp_report'),
            data=json.dumps(payload),
            content_type='application/csp-report',
        )
        self.assertEqual(response.status_code, 201)
        event = AuditEvent.objects.filter(action='CSP_VIOLATION').first()
        self.assertIsNotNone(event)
        self.assertIn('script-src', event.reason)

    def test_csp_report_rejects_oversized_and_malformed(self):
        response = self.client.post(
            reverse('csp_report'),
            data='{"csp-report": ' + ('x' * 9000) + '}',
            content_type='application/csp-report',
        )
        self.assertEqual(response.status_code, 413)

        response = self.client.post(
            reverse('csp_report'),
            data='not json',
            content_type='application/csp-report',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AuditEvent.objects.filter(action='CSP_VIOLATION').exists())


class SessionSecuritySettingsTests(TestCase):
    """Task 1.8: lock in cookie flags and login key rotation with tests."""

    def test_session_cookie_flags(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.SESSION_COOKIE_AGE, 14400)
        self.assertFalse(settings.SESSION_COOKIE_SECURE)  # dev; prod.py sets True

    def test_login_rotates_session_key(self):
        department = Department.objects.create(code='CCS', name='Computer Studies')
        user = User.objects.create_user(username='sess_user', password='Str0ng-Pass-2026!')
        Profile.objects.create(
            user=user, role=Profile.ROLE_ADMIN, department=department,
        )
        # Anonymous session key exists after the login page is fetched.
        self.client.get(reverse('login'))
        anonymous_key = self.client.session.session_key

        response = self.client.post(
            reverse('login'),
            {'username': 'sess_user', 'password': 'Str0ng-Pass-2026!'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session.session_key)
        self.assertNotEqual(self.client.session.session_key, anonymous_key)

    def test_session_cookie_is_httponly_on_client(self):
        user = User.objects.create_user(username='sess_http', password='Str0ng-Pass-2026!')
        Profile.objects.create(user=user, role=Profile.ROLE_ADMIN)
        self.client.post(
            reverse('login'),
            {'username': 'sess_http', 'password': 'Str0ng-Pass-2026!'},
        )
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie.value)
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
