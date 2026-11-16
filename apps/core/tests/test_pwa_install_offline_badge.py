"""
# // ==============================================================================
# // KCC CLASSSTAMP - PWA INSTALL + OFFLINE BADGE SAVE
# // ==============================================================================
# // The install affordance must ship on the pages a student lands on first, and
# // the offline badge needs a one-tap save (the QR is rendered as a data: URI,
# // so nothing reaches the gallery on its own).
# // ==============================================================================
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear, Class, ClassSlot, Department, Enrollment, Profile, Program, Subject,
)

User = get_user_model()
PASSWORD = 'PwaPass!2026'


class PwaInstallAndOfflineBadgeTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        today = datetime.date.today()
        cls.department = Department.objects.create(code='PWA', name='PWA Department')
        cls.program = Program.objects.create(
            department=cls.department, code='BSPWA', name='PWA Program', years_total=4,
        )
        cls.subject = Subject.objects.create(code='PWA101', name='PWA Subject', units=3)
        cls.year = AcademicYear.objects.create(
            name='2026-2027 PWA', starts_on=today - datetime.timedelta(days=30),
            ends_on=today + datetime.timedelta(days=300), is_active=True,
        )
        cls.student = User.objects.create_user(
            username='pwa_student', first_name='Pwa', last_name='Student', password=PASSWORD,
        )
        cls.student_profile = Profile.objects.create(
            user=cls.student, role=Profile.ROLE_STUDENT, student_number='PWA-0001',
            program=cls.program, year_level=1, department=cls.department,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='p' * 64,
        )
        teacher = User.objects.create_user(username='pwa_teacher', password=PASSWORD)
        cls.klass = Class.objects.create(
            academic_year=cls.year, class_code='BSPWA-1A-PWA101', subject=cls.subject,
            teacher_profile=Profile.objects.create(
                user=teacher, role=Profile.ROLE_TEACHER, department=cls.department,
            ),
            program=cls.program, year_level=1,
        )
        ClassSlot.objects.create(
            class_obj=cls.klass, weekday=today.weekday(),
            starts_at=datetime.time(8, 0), ends_at=datetime.time(9, 0), room='R1',
        )
        Enrollment.objects.create(student_profile=cls.student_profile,
                                  class_obj=cls.klass, status='ACTIVE')

    def test_login_page_loads_the_install_script(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js/core/pwa_install.js')

    def test_install_script_is_part_of_the_core_bundle(self):
        from apps.core.services.asset_bundles import JS_SOURCES
        self.assertIn('js/core/pwa_install.js', JS_SOURCES)

    def test_qr_badge_exposes_the_save_action(self):
        client = Client()
        client.force_login(self.student)
        response = client.get(reverse('student_qr_badge'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="offlineBadgeSaveBtn"')
        self.assertContains(response, 'Save to gallery')
        self.assertContains(response, 'id="offlineBadgeIssueBtn"')

    def test_save_handler_shipped_with_the_offline_script(self):
        import pathlib
        source = pathlib.Path('static/js/student/offline_badge.js').read_text(encoding='utf-8')
        self.assertIn('offlineBadgeSaveBtn', source)
        self.assertIn('navigator.canShare', source)
        self.assertIn("link.download = filename", source)
