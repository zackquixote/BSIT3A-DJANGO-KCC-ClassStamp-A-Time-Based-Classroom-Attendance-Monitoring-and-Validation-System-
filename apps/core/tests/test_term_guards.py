"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC TERM GUARD TESTS
# // ==============================================================================
# // Three guards added to /academic-years/:
# //   - overlapping term windows are refused
# //   - switching the active term while the outgoing one holds live data is
# //     blocked, and can only be forced with a written, audited reason
# //   - a page-level banner when nothing is current
# ==============================================================================
"""

from datetime import date, time

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
)
from apps.core.services.academic_service import (
    TermSwitchBlocked,
    create_or_update_academic_year,
    set_active_academic_year,
)

User = get_user_model()


class TermGuardBase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='term_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.teacher_user = User.objects.create_user(username='term_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.current = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )
        self.next_term = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=False,
        )
        self.client.force_login(self.admin_user)


class TermOverlapTests(TermGuardBase):
    def test_overlapping_window_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            create_or_update_academic_year(
                actor=self.admin_user,
                name='2025-2026 Summer',
                starts_on=date(2026, 1, 15),
                ends_on=date(2026, 5, 31),
                is_active=False,
            )

        self.assertIn('overlap', str(ctx.exception))
        self.assertFalse(AcademicYear.objects.filter(name='2025-2026 Summer').exists())

    def test_non_overlapping_window_is_accepted(self):
        result = create_or_update_academic_year(
            actor=self.admin_user,
            name='2025-2026 Summer',
            starts_on=date(2026, 4, 1),
            ends_on=date(2026, 5, 31),
            is_active=False,
        )

        self.assertEqual(result['instance'].name, '2025-2026 Summer')

    def test_editing_a_term_does_not_collide_with_itself(self):
        result = create_or_update_academic_year(
            actor=self.admin_user,
            name='2025-2026',
            starts_on=date(2025, 6, 1),
            ends_on=date(2026, 3, 30),
            is_active=True,
            ay_id=self.current.pk,
        )

        self.assertEqual(result['instance'].ends_on, date(2026, 3, 30))

    def test_overlap_is_reported_through_the_endpoint(self):
        response = self.client.post(reverse('academic_year_save'), {
            'name': '2025-2026 Summer',
            'starts_on': '2026-01-15',
            'ends_on': '2026-05-31',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('overlap', response.json()['error'])


class SetActiveGuardTests(TermGuardBase):
    def setUp(self):
        super().setUp()
        self.class_obj = Class.objects.create(
            academic_year=self.current, class_code='BSIT-1A', subject=self.subject,
            teacher_profile=self.teacher_profile, program=self.program, year_level=1,
        )
        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )

    def _open_session(self):
        return ClassSession.objects.create(
            slot=self.slot, session_date=timezone.localdate(),
            status=ClassSession.STATUS_OPEN,
            opened_by=self.teacher_user, created_by=self.teacher_user,
        )

    def test_switch_is_blocked_while_a_session_is_open(self):
        self._open_session()

        with self.assertRaises(TermSwitchBlocked) as ctx:
            set_active_academic_year(actor=self.admin_user, pk=self.next_term.pk)

        self.assertEqual(ctx.exception.blockers['open_sessions'], 1)
        self.current.refresh_from_db()
        self.assertTrue(self.current.is_active)

    def test_endpoint_returns_409_with_blocker_counts(self):
        self._open_session()

        response = self.client.post(reverse('academic_year_set_active', args=[self.next_term.pk]))

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertTrue(payload['requires_force'])
        self.assertEqual(payload['blockers']['open_sessions'], 1)
        self.assertEqual(payload['blockers']['active_classes'], 1)

    def test_force_requires_a_written_reason(self):
        self._open_session()

        response = self.client.post(
            reverse('academic_year_set_active', args=[self.next_term.pk]),
            {'force': '1'},
        )

        self.assertEqual(response.status_code, 400)
        self.next_term.refresh_from_db()
        self.assertFalse(self.next_term.is_active)

    def test_forced_switch_succeeds_and_is_audited(self):
        self._open_session()

        response = self.client.post(
            reverse('academic_year_set_active', args=[self.next_term.pk]),
            {'force': '1', 'reason': 'Registrar approved an early cutover'},
        )

        self.assertEqual(response.status_code, 200)
        self.next_term.refresh_from_db()
        self.current.refresh_from_db()
        self.assertTrue(self.next_term.is_active)
        self.assertFalse(self.current.is_active)

        event = AuditEvent.objects.get(action='SET_ACTIVE_ACADEMIC_YEAR')
        self.assertIn('forced', event.new_value)
        self.assertEqual(event.reason, 'Registrar approved an early cutover')

    def test_clean_switch_is_not_blocked(self):
        response = self.client.post(reverse('academic_year_set_active', args=[self.next_term.pk]))

        self.assertEqual(response.status_code, 200)
        self.next_term.refresh_from_db()
        self.assertTrue(self.next_term.is_active)


class ActiveTermBannerTests(TermGuardBase):
    def test_banner_when_no_term_is_active(self):
        AcademicYear.objects.update(is_active=False)

        response = self.client.get(reverse('academic_year_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No active academic term')

    def test_banner_when_active_term_has_ended(self):
        AcademicYear.objects.update(is_active=False)
        AcademicYear.objects.create(
            name='2024-2025', starts_on=date(2024, 6, 1), ends_on=date(2025, 3, 31),
            is_active=True,
        )
        self.current.is_active = False
        self.current.save(update_fields=['is_active'])
        self.next_term.is_active = False
        self.next_term.save(update_fields=['is_active'])

        response = self.client.get(reverse('academic_year_list'))

        self.assertContains(response, 'but is still')
        self.assertTrue(response.context['active_term_ended'])

    def test_no_banner_when_a_live_term_is_active(self):
        response = self.client.get(reverse('academic_year_list'))

        self.assertNotContains(response, 'No active academic term')
