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
        self.assertContains(response, 'Edit Class Section')
        self.assertNotContains(response, 'openCreateClassBtn')

    def test_subject_list_page_has_no_curriculum_editor(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('subject_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'curriculumModal')
        self.assertNotContains(response, 'js-curriculum-btn')
        self.assertNotContains(response, 'curriculum_modal.js')
        self.assertContains(response, 'Managed in Programs')

    def test_class_save_rejects_create_without_class_id(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('class_save'),
            {
                'class_code': 'BSIT-2A',
                'subject_id': self.subject.pk,
                'teacher_profile_id': self.teacher_profile.pk,
                'academic_year_id': self.active_year.pk,
                'capacity': 40,
                'grace_minutes': 10,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('class_wizard_setup'))
        self.assertFalse(Class.objects.filter(class_code='BSIT-2A').exists())

    def test_class_save_edit_updates_existing_class(self):
        self.client.force_login(self.admin_user)
        other_subject = Subject.objects.create(code='IT202', name='Advanced Computing')

        response = self.client.post(
            reverse('class_save'),
            {
                'class_id': self.class_obj.pk,
                'class_code': 'BSIT-1A-RENAMED',
                'subject_id': other_subject.pk,
                'teacher_profile_id': self.teacher_profile.pk,
                'academic_year_id': self.active_year.pk,
                'capacity': 50,
                'grace_minutes': 15,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.class_code, 'BSIT-1A-RENAMED')
        self.assertEqual(self.class_obj.subject, other_subject)
        self.assertEqual(self.class_obj.capacity, 50)
        self.assertTrue(
            AuditEvent.objects.filter(
                action='UPDATE_CLASS',
                object_id=str(self.class_obj.pk),
            ).exists()
        )

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

    def test_subject_deactivation_blocked_with_live_class(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('subject_toggle', args=[self.subject.pk]))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)
        self.assertFalse(
            AuditEvent.objects.filter(action='SUBJECT_DEACTIVATED').exists()
        )

    def test_subject_toggle_writes_audit_when_no_live_class(self):
        self.class_obj.is_active = False
        self.class_obj.save(update_fields=['is_active'])
        self.client.force_login(self.admin_user)

        response = self.client.post(reverse('subject_toggle', args=[self.subject.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_active)
        event = AuditEvent.objects.get(action='SUBJECT_DEACTIVATED')
        self.assertEqual(event.object_type, 'Subject')
        self.assertEqual(event.object_id, str(self.subject.pk))
        self.assertEqual(event.old_value, 'is_active=True')
        self.assertEqual(event.new_value, 'is_active=False')

        response = self.client.post(reverse('subject_toggle', args=[self.subject.pk]))
        self.assertEqual(response.status_code, 200)
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)
        self.assertTrue(AuditEvent.objects.filter(action='SUBJECT_ACTIVATED').exists())
