"""
# // ==============================================================================
# // KCC CLASSSTAMP - SYSTEM POLICY TESTS
# // ==============================================================================
# // Thresholds used to be constants. These tests pin the resolution rules:
# //   - no policy row  -> documented defaults (so old behaviour is unchanged)
# //   - a policy row   -> overrides reach the scan window and the radar bands
# ==============================================================================
"""

from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Profile,
    Program,
    Subject,
    SystemPolicy,
)
from apps.core.services.attendance_policy import (
    BAND_CRITICAL,
    BAND_SAFE,
    BAND_WATCH,
    classify_absence_rate,
)
from apps.core.views import session_views

User = get_user_model()


class PolicyPageTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='policy_admin2')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.teacher_user = User.objects.create_user(username='policy_teacher')
        Profile.objects.create(user=self.teacher_user, role=Profile.ROLE_TEACHER)

    def test_admin_can_open_the_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin_policy'))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['policy'])

    def test_teacher_is_redirected(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('admin_policy'))

        self.assertEqual(response.status_code, 403)

    def test_saving_persists_and_audits(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('admin_policy'), {
            'scan_close_tolerance_minutes': '25',
            'absence_threshold_percent': '15',
        })

        self.assertEqual(response.status_code, 302)
        policy = SystemPolicy.get_solo()
        self.assertEqual(policy.scan_close_tolerance_minutes, 25)
        self.assertEqual(float(policy.absence_threshold_percent), 15.0)
        self.assertEqual(policy.updated_by, self.admin_user)
        self.assertTrue(AuditEvent.objects.filter(action='UPDATE_SYSTEM_POLICY').exists())

    def test_blank_fields_clear_back_to_defaults(self):
        SystemPolicy.objects.create(
            scan_close_tolerance_minutes=30, absence_threshold_percent=12,
        )
        self.client.force_login(self.admin_user)

        self.client.post(reverse('admin_policy'), {
            'scan_close_tolerance_minutes': '',
            'absence_threshold_percent': '',
        })

        policy = SystemPolicy.get_solo()
        self.assertIsNone(policy.scan_close_tolerance_minutes)
        self.assertIsNone(policy.absence_threshold_percent)

    def test_out_of_range_value_is_rejected(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('admin_policy'), {
            'scan_close_tolerance_minutes': '9999',
            'absence_threshold_percent': '20',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(SystemPolicy.get_solo())


class PolicyEffectTests(TestCase):
    def setUp(self):
        self.slot = ClassSlot(starts_at=time(9, 0), ends_at=time(10, 0))
        self.session = ClassSession(slot=self.slot, session_date=date(2026, 5, 12))

    def _at(self, hour, minute):
        return timezone.make_aware(datetime(2026, 5, 12, hour, minute))

    def test_default_window_uses_the_module_constant(self):
        # 10:10 is inside the built-in 15 minute tolerance.
        self.assertFalse(session_views._scan_window_closed(self.session, now=self._at(10, 10)))

    def test_policy_tightens_the_window(self):
        SystemPolicy.objects.create(scan_close_tolerance_minutes=0)

        self.assertTrue(session_views._scan_window_closed(self.session, now=self._at(10, 1)))

    def test_policy_loosens_the_window(self):
        SystemPolicy.objects.create(scan_close_tolerance_minutes=120)

        self.assertFalse(session_views._scan_window_closed(self.session, now=self._at(11, 30)))

    def test_absence_bands_follow_the_threshold(self):
        # Default 20% -> watchlist starts at 10.
        self.assertEqual(classify_absence_rate(5), BAND_SAFE)
        self.assertEqual(classify_absence_rate(15), BAND_WATCH)
        self.assertEqual(classify_absence_rate(20), BAND_CRITICAL)

        SystemPolicy.objects.create(absence_threshold_percent=10)

        # 10% policy -> watchlist starts at 5, critical at 10.
        self.assertEqual(classify_absence_rate(4), BAND_SAFE)
        self.assertEqual(classify_absence_rate(7), BAND_WATCH)
        self.assertEqual(classify_absence_rate(10), BAND_CRITICAL)
