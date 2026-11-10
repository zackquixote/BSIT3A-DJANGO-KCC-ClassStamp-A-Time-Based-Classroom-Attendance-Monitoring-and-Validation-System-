"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC YEAR CLASS STRUCTURE CLONING TESTS (task 3.1 / 3.2)
# // ==============================================================================
# // Req 12: copy active classes and active slots into another term WITHOUT
# // enrollments, sessions, attendance, or join codes. Duplicates are reported
# // and never overwritten. One failed class must not leave a partial copy.
# // ==============================================================================
"""

from datetime import date, datetime, time, timedelta
from unittest import mock

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
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.services import clone_classes_academic_year

User = get_user_model()


class AcademicCloneFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(code='CCS', name='Computer Studies')
        cls.program = Program.objects.create(
            department=cls.department, code='BSIT', name='Information Technology',
        )
        cls.subject = Subject.objects.create(code='IT311', name='Web Development')
        cls.other_subject = Subject.objects.create(code='IT312', name='Mobile Development')
        cls.source = AcademicYear.objects.create(
            name='2025-2026',
            starts_on=date(2025, 6, 1),
            ends_on=date(2026, 3, 31),
            is_active=True,
        )
        cls.target = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=False,
        )
        User = get_user_model()
        cls.admin_user = User.objects.create_user(username='clone_admin')
        Profile.objects.create(user=cls.admin_user, role=Profile.ROLE_ADMIN)
        cls.teacher_user = User.objects.create_user(username='clone_teacher')
        cls.teacher = Profile.objects.create(
            user=cls.teacher_user, role=Profile.ROLE_TEACHER, department=cls.department,
        )

    def _class(self, code, subject=None, teacher=None, active=True, with_join_code=False):
        class_obj = Class.objects.create(
            academic_year=self.source,
            class_code=code,
            section_code=code.rsplit('-', 1)[0] if '-' in code else code,
            subject=subject or self.subject,
            teacher_profile=teacher or self.teacher,
            program=self.program,
            year_level=3,
            capacity=40,
            grace_minutes=10,
            is_active=active,
        )
        if with_join_code:
            class_obj.join_code_digest = 'HASHED-CODE'
            class_obj.join_code_active = True
            class_obj.join_code_created_at = timezone.make_aware(datetime(2025, 7, 1, 8, 0))
            class_obj.save(update_fields=[
                'join_code_digest', 'join_code_active', 'join_code_created_at', 'updated_at',
            ])
        return class_obj

    def _slot(self, class_obj, weekday=0, start=time(8, 0), end=time(10, 0), room='IT-Lab 1', active=True):
        return ClassSlot.objects.create(
            class_obj=class_obj, weekday=weekday,
            starts_at=start, ends_at=end, room=room, is_active=active,
        )


class AcademicCloneTests(AcademicCloneFixtureMixin, TestCase):
    def test_clones_active_classes_and_slots(self):
        class_a = self._class('BSIT-3A-IT311', with_join_code=True)
        class_b = self._class('BSIT-3A-IT312', subject=self.other_subject)
        self._slot(class_a, weekday=0, start=time(8, 0), end=time(10, 0), room='IT-Lab 1')
        self._slot(class_a, weekday=2, start=time(13, 0), end=time(15, 0), room='IT-Lab 2')
        self._slot(class_b, weekday=1, start=time(8, 0), end=time(10, 0), room='RM-301')

        result = clone_classes_academic_year(
            actor=self.admin_user, source_year=self.source, target_year=self.target,
        )

        self.assertEqual(result['copied_class_count'], 2)
        self.assertEqual(result['copied_slot_count'], 3)
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['class_mapping']), 2)

        cloned = Class.objects.filter(academic_year=self.target).order_by('class_code')
        self.assertEqual(cloned.count(), 2)
        clone_a = cloned.get(class_code='BSIT-3A-IT311')
        self.assertEqual(clone_a.subject_id, class_a.subject_id)
        self.assertEqual(clone_a.teacher_profile_id, class_a.teacher_profile_id)
        self.assertEqual(clone_a.program_id, class_a.program_id)
        self.assertEqual(clone_a.year_level, class_a.year_level)
        self.assertEqual(clone_a.capacity, 40)
        self.assertEqual(clone_a.grace_minutes, 10)
        self.assertEqual(clone_a.section_code, class_a.section_code)
        # Join codes are never copied.
        self.assertEqual(clone_a.join_code_digest, '')
        self.assertFalse(clone_a.join_code_active)
        self.assertIsNone(clone_a.join_code_created_at)

        self.assertEqual(
            ClassSlot.objects.filter(class_obj=clone_a, is_active=True).count(), 2,
        )
        rooms = list(
            ClassSlot.objects.filter(class_obj=clone_a)
            .order_by('weekday').values_list('room', flat=True)
        )
        self.assertEqual(rooms, ['IT-Lab 1', 'IT-Lab 2'])

        self.assertTrue(
            AuditEvent.objects.filter(
                action='CLONE_ACADEMIC_YEAR_CLASSES',
                actor=self.admin_user,
                object_id=str(self.target.pk),
            ).exists()
        )

    def test_does_not_copy_enrollments_sessions_or_attendance_context(self):
        class_obj = self._class('BSIT-3A-IT311')
        slot = self._slot(class_obj)
        student_user = User.objects.create_user(username='clone_student')
        student = Profile.objects.create(
            user=student_user, role=Profile.ROLE_STUDENT,
            student_number='2025-9001', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        Enrollment.objects.create(
            class_obj=class_obj, student_profile=student, status=Enrollment.STATUS_ACTIVE,
        )
        ClassSession.objects.create(
            slot=slot, session_date=date(2025, 8, 20), status=ClassSession.STATUS_CLOSED,
        )

        result = clone_classes_academic_year(
            actor=self.admin_user, source_year=self.source, target_year=self.target,
        )
        self.assertEqual(result['copied_class_count'], 1)
        cloned = Class.objects.get(academic_year=self.target, class_code='BSIT-3A-IT311')
        self.assertFalse(
            Enrollment.objects.filter(class_obj=cloned).exists(),
        )
        self.assertFalse(
            ClassSession.objects.filter(slot__class_obj=cloned).exists(),
        )

    def test_inactive_classes_and_inactive_slots_are_not_copied(self):
        active_class = self._class('BSIT-3A-IT311')
        self._slot(active_class, weekday=0, active=True)
        self._slot(active_class, weekday=1, active=False)
        self._class('BSIT-3B-IT311', active=False)

        result = clone_classes_academic_year(
            actor=self.admin_user, source_year=self.source, target_year=self.target,
        )
        self.assertEqual(result['copied_class_count'], 1)
        self.assertEqual(result['copied_slot_count'], 1)
        self.assertFalse(
            Class.objects.filter(academic_year=self.target, class_code='BSIT-3B-IT311').exists(),
        )
        cloned = Class.objects.get(academic_year=self.target, class_code='BSIT-3A-IT311')
        self.assertEqual(ClassSlot.objects.filter(class_obj=cloned).count(), 1)

    def test_duplicate_target_codes_are_reported_not_overwritten(self):
        source_class = self._class('BSIT-3A-IT311')
        self._slot(source_class)
        existing = Class.objects.create(
            academic_year=self.target,
            class_code='bsit-3a-it311',  # case-insensitive duplicate
            subject=self.other_subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
        )
        other = self._class('BSIT-3A-IT312', subject=self.other_subject)
        self._slot(other, weekday=1)

        result = clone_classes_academic_year(
            actor=self.admin_user, source_year=self.source, target_year=self.target,
        )
        self.assertEqual(result['copied_class_count'], 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('already exists', result['errors'][0]['reason'])
        self.assertEqual(result['errors'][0]['class_code'], 'BSIT-3A-IT311')

        existing.refresh_from_db()
        self.assertEqual(existing.subject_id, self.other_subject.pk)
        self.assertFalse(
            ClassSlot.objects.filter(class_obj=existing).exists(),
        )

    def test_same_year_is_rejected(self):
        with self.assertRaises(ValueError):
            clone_classes_academic_year(
                actor=self.admin_user, source_year=self.source, target_year=self.source,
            )

    def test_missing_year_raises_doesnotexist(self):
        with self.assertRaises(AcademicYear.DoesNotExist):
            clone_classes_academic_year(
                actor=self.admin_user, source_year=self.source, target_year=999999,
            )

    def test_one_failure_does_not_leave_a_partial_copy(self):
        good = self._class('BSIT-3A-IT311')
        self._slot(good)
        self._class('BSIT-3A-IT312', subject=self.other_subject)

        real_create = Class.objects.create

        def flaky_create(*args, **kwargs):
            if kwargs.get('class_code') == 'BSIT-3A-IT312':
                raise RuntimeError('boom')
            return real_create(*args, **kwargs)

        with mock.patch('apps.core.services.academic_service.Class.objects.create', side_effect=flaky_create):
            result = clone_classes_academic_year(
                actor=self.admin_user, source_year=self.source, target_year=self.target,
            )

        self.assertEqual(result['copied_class_count'], 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['errors'][0]['class_code'], 'BSIT-3A-IT312')
        self.assertIn('boom', result['errors'][0]['reason'])
        # The failed class must not exist, not even as an empty shell.
        self.assertFalse(
            Class.objects.filter(academic_year=self.target, class_code='BSIT-3A-IT312').exists(),
        )
        cloned = Class.objects.get(academic_year=self.target, class_code='BSIT-3A-IT311')
        self.assertEqual(ClassSlot.objects.filter(class_obj=cloned).count(), 1)


class AcademicCloneViewTests(AcademicCloneFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_view_clones_and_returns_summary(self):
        class_obj = self._class('BSIT-3A-IT311', with_join_code=True)
        self._slot(class_obj)

        response = self.client.post(reverse('academic_year_clone'), {
            'source_year_id': self.source.pk,
            'target_year_id': self.target.pk,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['copied_class_count'], 1)
        self.assertEqual(data['copied_slot_count'], 1)
        self.assertEqual(data['class_mapping'][0]['class_code'], 'BSIT-3A-IT311')
        self.assertEqual(data['errors'], [])

    def test_view_requires_admin(self):
        student_user = User.objects.create_user(username='clone_view_student')
        Profile.objects.create(
            user=student_user, role=Profile.ROLE_STUDENT,
            student_number='2025-9002', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.client.force_login(student_user)
        response = self.client.post(reverse('academic_year_clone'), {
            'source_year_id': self.source.pk,
            'target_year_id': self.target.pk,
        })
        # role_required redirects role mismatches to the dashboard fallback.
        self.assertEqual(response.status_code, 302)

    def test_view_rejects_get_and_missing_params(self):
        response = self.client.get(reverse('academic_year_clone'))
        self.assertEqual(response.status_code, 405)

        response = self.client.post(reverse('academic_year_clone'), {})
        self.assertEqual(response.status_code, 400)

        response = self.client.post(reverse('academic_year_clone'), {
            'source_year_id': self.source.pk,
            'target_year_id': self.source.pk,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('different', response.json()['error'])

    def test_view_reports_duplicates(self):
        class_obj = self._class('BSIT-3A-IT311')
        self._slot(class_obj)
        Class.objects.create(
            academic_year=self.target,
            class_code='BSIT-3A-IT311',
            subject=self.subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=3,
        )

        response = self.client.post(reverse('academic_year_clone'), {
            'source_year_id': self.source.pk,
            'target_year_id': self.target.pk,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['copied_class_count'], 0)
        self.assertEqual(len(data['errors']), 1)
        self.assertIn('already exists', data['errors'][0]['reason'])
