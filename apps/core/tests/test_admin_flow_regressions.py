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
    Subject,
)
from apps.core.views.helpers.dashboard_helpers import _teacher_dashboard_stats

User = get_user_model()


class AdminTeacherFlowRegressionTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.active_year = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )

        self.admin_user = User.objects.create_user(
            username='flow_admin', password='Admin!Pass123', is_staff=True,
        )
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.teacher_user = User.objects.create_user(
            username='flow_teacher', password='Teacher!Pass123',
            email='flow.teacher@example.com',
        )
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.active_year,
            class_code='BSIT-1A',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
        )

    def test_teacher_analytics_returns_json(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('teacher_analytics_json', args=[self.teacher_profile.pk])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertNotIn('employee_id', payload['teacher'])

    def test_unassign_class_with_slots_only_removes_class(self):
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=timezone.localdate().weekday(),
            starts_at=time(8, 0),
            ends_at=time(9, 0),
            room='Room 1',
        )
        class_id = self.class_obj.pk
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('teacher_unassign_class_ajax', args=[self.teacher_profile.pk, class_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertFalse(Class.objects.filter(pk=class_id).exists())
        self.assertFalse(ClassSlot.objects.filter(pk=slot.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action='UNASSIGN_CLASS').exists())

    def test_slot_delete_retires_slot_with_session_history(self):
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=today.weekday(),
            starts_at=time(10, 0),
            ends_at=time(11, 0),
            room='Room 2',
        )
        ClassSession.objects.create(
            slot=slot,
            session_date=today,
            status=ClassSession.STATUS_CLOSED,
            opened_by=self.teacher_user,
            created_by=self.teacher_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('class_slot_delete', args=[slot.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertTrue(payload['archived'])
        slot.refresh_from_db()
        self.assertFalse(slot.is_active)
        self.assertTrue(AuditEvent.objects.filter(action='DEACTIVATE_CLASS_SLOT').exists())

    def test_adhoc_session_uses_today_weekday_when_no_today_slot_exists(self):
        today = timezone.localdate()
        other_weekday = (today.weekday() + 1) % 7
        ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=other_weekday,
            starts_at=time(13, 0),
            ends_at=time(14, 0),
            room='Room 3',
        )
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('teacher_session_open'),
            {'class_id': self.class_obj.pk},
        )

        self.assertEqual(response.status_code, 302)
        session = ClassSession.objects.filter(
            slot__class_obj=self.class_obj,
            session_date=today,
        ).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.slot.weekday, today.weekday())
        self.assertTrue(
            ClassSlot.objects.filter(
                class_obj=self.class_obj,
                weekday=today.weekday(),
                is_active=True,
            ).exists()
        )

    def test_teacher_assign_class_reassignment_is_audited(self):
        other_user = User.objects.create_user(
            username='flow_teacher_two', password='Teacher!Pass123',
        )
        other_profile = Profile.objects.create(
            user=other_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('teacher_assign_class_ajax', args=[other_profile.pk]),
            {
                'academic_year_id': self.active_year.pk,
                'subject_id': self.subject.pk,
                'class_code': self.class_obj.class_code,
                'grace_minutes': 10,
                'capacity': 45,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.teacher_profile, other_profile)
        event = AuditEvent.objects.get(action='REASSIGN_CLASS')
        self.assertIn('flow_teacher', event.old_value)
        self.assertIn('flow_teacher_two', event.new_value)

    def test_class_list_page_renders_with_wizard_as_only_create_path(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('class_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('class_wizard_setup'))
        self.assertNotContains(response, 'btn-edit-class')
        self.assertNotContains(response, 'openCreateClassBtn')

    def test_subject_list_page_has_no_curriculum_editor(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('subject_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'curriculumModal')
        self.assertNotContains(response, 'js-curriculum-btn')
        self.assertNotContains(response, 'curriculum_modal.js')
        self.assertContains(response, 'Managed in Programs')

    def test_teacher_dashboard_only_includes_active_academic_year(self):
        inactive_year = AcademicYear.objects.create(
            name='2025-2026',
            starts_on=date(2025, 6, 1),
            ends_on=date(2026, 3, 31),
            is_active=False,
        )
        Class.objects.create(
            academic_year=inactive_year,
            class_code='BSIT-OLD',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
        )

        stats = _teacher_dashboard_stats(self.teacher_profile)

        self.assertEqual([item.class_code for item in stats['classes']], ['BSIT-1A'])
        self.assertEqual(stats['class_count'], 1)
