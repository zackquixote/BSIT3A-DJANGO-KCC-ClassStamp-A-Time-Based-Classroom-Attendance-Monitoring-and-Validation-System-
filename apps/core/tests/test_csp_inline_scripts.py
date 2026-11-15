"""
# // ==============================================================================
# // KCC CLASSSTAMP - CSP NONCE FOR INLINE SCRIPTS
# // ==============================================================================
# // The site enforces a Content-Security-Policy without 'unsafe-inline', so any
# // <script> block without the per-request nonce is silently dropped by the
# // browser. That is invisible on a laptop (desktop CSS hides the mobile-only
# // controls) but breaks them on phones: the student "Attendance Stats"
# // collapsible did nothing when tapped.
# // ==============================================================================
"""

import datetime
import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    Class,
    ClassSlot,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)

User = get_user_model()
PASSWORD = 'NoncePass!2026'
SCRIPT_RE = re.compile(r'<script\b([^>]*)>', re.I)


class InlineScriptNonceTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        today = datetime.date.today()
        cls.department = Department.objects.create(code='NON', name='Nonce Department')
        cls.program = Program.objects.create(
            department=cls.department, code='BSNON', name='Nonce Program', years_total=4,
        )
        cls.subject = Subject.objects.create(code='NON101', name='Nonce Subject', units=3)
        cls.year = AcademicYear.objects.create(
            name='2026-2027 Nonce', starts_on=today - datetime.timedelta(days=30),
            ends_on=today + datetime.timedelta(days=300), is_active=True,
        )
        cls.admin = User.objects.create_user(username='nonce_admin', password=PASSWORD)
        Profile.objects.create(user=cls.admin, role=Profile.ROLE_ADMIN)
        cls.student = User.objects.create_user(
            username='nonce_student', first_name='Nonce', last_name='Student', password=PASSWORD,
        )
        cls.student_profile = Profile.objects.create(
            user=cls.student, role=Profile.ROLE_STUDENT, student_number='NON-0001',
            program=cls.program, year_level=1, department=cls.department,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='n' * 64,
        )
        cls.klass = Class.objects.create(
            academic_year=cls.year, class_code='BSNON-1A-NON101', subject=cls.subject,
            teacher_profile=Profile.objects.create(
                user=User.objects.create_user(username='nonce_teacher', password=PASSWORD),
                role=Profile.ROLE_TEACHER, department=cls.department,
            ),
            program=cls.program, year_level=1,
        )
        ClassSlot.objects.create(
            class_obj=cls.klass, weekday=today.weekday(),
            starts_at=datetime.time(8, 0), ends_at=datetime.time(9, 0), room='R1',
        )
        Enrollment.objects.create(student_profile=cls.student_profile,
                                  class_obj=cls.klass, status='ACTIVE')

    def _client(self, user):
        client = Client()
        client.force_login(user)
        return client

    def _assert_every_inline_script_carries_a_nonce(self, response):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8', 'replace')
        header = response.get('Content-Security-Policy') or response.get(
            'Content-Security-Policy-Report-Only', ''
        )
        self.assertIn("'nonce-", header, 'CSP header must advertise a nonce')

        inline = [attrs for attrs in SCRIPT_RE.findall(html) if 'src=' not in attrs.lower()]
        self.assertTrue(inline, 'page should still contain inline scripts')
        for attrs in inline:
            self.assertIn(
                'nonce=', attrs.lower(),
                f'inline script without a CSP nonce would be blocked: <script{attrs}>',
            )

    def test_student_dashboard_inline_scripts_are_allowed(self):
        response = self._client(self.student).get(reverse('student_dashboard'))
        self._assert_every_inline_script_carries_a_nonce(response)
        # the control that was dead on mobile
        self.assertContains(response, 'id="studentStatsToggleBtn"')
        self.assertContains(response, 'id="studentKpiCollapsible"')

    def test_attendance_log_inline_scripts_are_allowed(self):
        response = self._client(self.student).get(reverse('student_attendance_log'))
        self._assert_every_inline_script_carries_a_nonce(response)

    def test_admin_pages_sidebar_script_is_allowed(self):
        response = self._client(self.admin).get(reverse('admin_dashboard'))
        self._assert_every_inline_script_carries_a_nonce(response)
