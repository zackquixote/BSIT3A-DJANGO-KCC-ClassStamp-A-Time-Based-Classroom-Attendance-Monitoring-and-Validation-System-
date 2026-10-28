"""
# // ==============================================================================
# // KCC CLASSSTAMP - WEEK 8 TESTS: A-20 ORGANISATION FLOW CONSOLIDATION
# // ==============================================================================
# // Subsystem: Quality Assurance / Regression Guard
# // Description: Covers Phase 1 (section identity & enlistment polish):
# //   - Directory "Enrolled Section(s)" scoped to the active academic year,
# //     pending enrollments shown separately, __unassigned__ filter sentinel.
# //   - Class roster GET candidate scoping by program/year.
# //   - Batch enlistment endpoint (capacity, duplicates, audit, permissions).
# // ==============================================================================
"""

from datetime import date, time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Curriculum,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.tests.test_week5 import BaseWeek5FixtureMixin


# // ==============================================================================
# // A-20 PHASE 1a: DIRECTORY SECTION IDENTITY SCOPING
# // ==============================================================================
class DirectorySectionScopeTests(TestCase, BaseWeek5FixtureMixin):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()
        self.academic_year = self._make_academic_year()
        self.admin = self._make_admin('w8_admin')
        self.teacher_user, self.teacher_profile = self._make_teacher('w8_teacher')
        self.subject = Subject.objects.create(code='W8-SUBJ', name='Week 8 Subject')
        self.class_obj = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
            program=self.program, year_level=1, grace_minutes=10,
        )
        _, self.s1 = self._make_student('w8_s1', '2026-8001', year_level=1)
        _, self.s2 = self._make_student('w8_s2', '2026-8002', year_level=1)

    def _enroll(self, student, class_obj, status=Enrollment.STATUS_ACTIVE):
        return Enrollment.objects.create(
            student_profile=student, class_obj=class_obj, status=status,
        )

    def test_active_enrollment_renders_clickable_section_tag(self):
        self._enroll(self.s1, self.class_obj)
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'href="?section=BSIT-1A"')

    def test_pending_enrollment_renders_pending_tag(self):
        self._enroll(self.s1, self.class_obj, status=Enrollment.STATUS_PENDING)
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'))
        self.assertContains(res, 'Pending: BSIT-1A')

    def test_old_academic_year_enrollment_not_shown(self):
        old_ay = AcademicYear.objects.create(
            name='2024-2025', starts_on=date(2024, 6, 1),
            ends_on=date(2025, 3, 31), is_active=False,
        )
        old_class = Class.objects.create(
            academic_year=old_ay, class_code='OLD-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
            program=self.program, year_level=1, grace_minutes=10,
        )
        self._enroll(self.s1, old_class)
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'))
        self.assertNotContains(res, 'OLD-1A')
        self.assertContains(res, 'unassigned-tag')

    def test_section_filter_scoped_to_active_academic_year(self):
        old_ay = AcademicYear.objects.create(
            name='2024-2025', starts_on=date(2024, 6, 1),
            ends_on=date(2025, 3, 31), is_active=False,
        )
        old_class = Class.objects.create(
            academic_year=old_ay, class_code='OLD-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
            program=self.program, year_level=1, grace_minutes=10,
        )
        self._enroll(self.s2, old_class)
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'), {'section': 'OLD-1A'})
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, '2026-8002')
        res_active = self.client.get(reverse('student_directory'), {'section': 'BSIT-1A'})
        self.assertNotContains(res_active, '2026-8001')

    def test_unassigned_filter_lists_only_students_without_active_section(self):
        self._enroll(self.s1, self.class_obj)
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'), {'section': '__unassigned__'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '2026-8002')
        self.assertNotContains(res, '2026-8001')

    def test_sections_dropdown_lists_active_ay_classes_only(self):
        old_ay = AcademicYear.objects.create(
            name='2024-2025', starts_on=date(2024, 6, 1),
            ends_on=date(2025, 3, 31), is_active=False,
        )
        Class.objects.create(
            academic_year=old_ay, class_code='OLD-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
            program=self.program, year_level=1, grace_minutes=10,
        )
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'))
        self.assertContains(res, 'BSIT-1A')
        self.assertNotContains(res, 'OLD-1A')


# // ==============================================================================
# // A-20 PHASE 1b: ROSTER CANDIDATE SCOPING (GET)
# // ==============================================================================
class RosterGetScopeTests(TestCase, BaseWeek5FixtureMixin):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()
        self.other_program = Program.objects.create(
            department=self.department, code='BSCS',
            name='BS Computer Science', years_total=4,
        )
        self.academic_year = self._make_academic_year()
        self.admin = self._make_admin('w8_admin2')
        self.teacher_user, self.teacher_profile = self._make_teacher('w8_teacher2')
        self.subject = Subject.objects.create(code='W8-SUBJ2', name='Week 8 Subject 2')
        self.class_obj = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
            program=self.program, year_level=1, grace_minutes=10,
        )
        _, self.s1 = self._make_student('w8_r1', '2026-8101', year_level=1)
        _, self.s2 = self._make_student('w8_r2', '2026-8102', year_level=1)
        s3_user, self.s3 = self._make_student('w8_r3', '2026-8103', year_level=1)
        self.s3.program = self.other_program
        self.s3.save(update_fields=['program'])

    def test_available_defaults_to_class_program_and_year(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('class_roster_get', args=[self.class_obj.id]))
        data = res.json()
        available_ids = [s['profile_id'] for s in data['available']]
        self.assertIn(self.s1.id, available_ids)
        self.assertIn(self.s2.id, available_ids)
        self.assertNotIn(self.s3.id, available_ids)

    def test_available_override_by_query_params(self):
        self.client.force_login(self.admin)
        res = self.client.get(
            reverse('class_roster_get', args=[self.class_obj.id]),
            {'program_id': str(self.other_program.id)},
        )
        data = res.json()
        available_ids = [s['profile_id'] for s in data['available']]
        self.assertIn(self.s3.id, available_ids)
        self.assertNotIn(self.s1.id, available_ids)

    def test_payload_exposes_section_scope_and_capacity(self):
        self.class_obj.capacity = 40
        self.class_obj.save(update_fields=['capacity'])
        self.client.force_login(self.admin)
        res = self.client.get(reverse('class_roster_get', args=[self.class_obj.id]))
        data = res.json()
        self.assertEqual(data['class_program_id'], self.program.id)
        self.assertEqual(data['class_year_level'], 1)
        self.assertEqual(data['remaining_capacity'], 40)

    def test_roster_get_requires_admin(self):
        res = self.client.get(reverse('class_roster_get', args=[self.class_obj.id]))
        self.assertEqual(res.status_code, 302)


# // ==============================================================================
# // A-20 PHASE 1c: BATCH ENLISTMENT
# // ==============================================================================
class RosterBatchEnlistTests(TestCase, BaseWeek5FixtureMixin):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()
        self.academic_year = self._make_academic_year()
        self.admin = self._make_admin('w8_admin3')
        self.teacher_user, self.teacher_profile = self._make_teacher('w8_teacher3')
        self.subject = Subject.objects.create(code='W8-SUBJ3', name='Week 8 Subject 3')
        self.class_obj = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
            program=self.program, year_level=1, grace_minutes=10,
        )
        _, self.s1 = self._make_student('w8_b1', '2026-8201', year_level=1)
        _, self.s2 = self._make_student('w8_b2', '2026-8202', year_level=1)
        _, self.s3 = self._make_student('w8_b3', '2026-8203', year_level=2)

    def _batch(self, client, extra=None):
        payload = dict(extra or {})
        return client.post(
            reverse('class_roster_enroll_batch', args=[self.class_obj.id]), payload,
        )

    def test_batch_enlists_matching_program_and_year(self):
        self.client.force_login(self.admin)
        res = self._batch(self.client)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['enrolled_count'], 2)
        active = Enrollment.objects.filter(
            class_obj=self.class_obj, status=Enrollment.STATUS_ACTIVE,
        ).values_list('student_profile_id', flat=True)
        self.assertCountEqual(active, [self.s1.id, self.s2.id])

    def test_batch_skips_students_already_active_in_section(self):
        Enrollment.objects.create(
            student_profile=self.s1, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.admin)
        res = self._batch(self.client)
        self.assertEqual(res.json()['enrolled_count'], 1)

    def test_batch_reactivates_withdrawn_enrollment(self):
        Enrollment.objects.create(
            student_profile=self.s1, class_obj=self.class_obj,
            status=Enrollment.STATUS_WITHDRAWN,
        )
        self.client.force_login(self.admin)
        res = self._batch(self.client)
        self.assertEqual(res.json()['enrolled_count'], 2)
        status = Enrollment.objects.get(
            student_profile=self.s1, class_obj=self.class_obj,
        ).status
        self.assertEqual(status, Enrollment.STATUS_ACTIVE)

    def test_batch_respects_capacity(self):
        self.class_obj.capacity = 2
        self.class_obj.save(update_fields=['capacity'])
        Enrollment.objects.create(
            student_profile=self.s1, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.admin)
        res = self._batch(self.client)
        data = res.json()
        self.assertEqual(data['enrolled_count'], 1)
        self.assertIn('capacity', data['message'])

    def test_batch_override_scope_by_params(self):
        self.client.force_login(self.admin)
        res = self._batch(self.client, {'year_level': '2'})
        data = res.json()
        self.assertEqual(data['enrolled_count'], 1)
        self.assertTrue(Enrollment.objects.filter(
            class_obj=self.class_obj, student_profile=self.s3,
            status=Enrollment.STATUS_ACTIVE,
        ).exists())

    def test_batch_rejects_invalid_year_level(self):
        self.client.force_login(self.admin)
        res = self._batch(self.client, {'year_level': 'abc'})
        self.assertEqual(res.status_code, 400)

    def test_batch_audits_each_enrollment(self):
        self.client.force_login(self.admin)
        self._batch(self.client)
        events = AuditEvent.objects.filter(
            actor=self.admin, action='ENROLL_STUDENT',
            object_type='Enrollment',
        )
        self.assertEqual(events.count(), 2)
        self.assertTrue(all('Batch-enlisted' in e.reason for e in events))

    def test_batch_requires_admin(self):
        res = self._batch(self.client)
        self.assertEqual(res.status_code, 302)
        self.client.force_login(self.teacher_user)
        res = self._batch(self.client)
        self.assertEqual(res.status_code, 302)

    def test_batch_requires_post(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('class_roster_enroll_batch', args=[self.class_obj.id]))
        self.assertEqual(res.status_code, 405)
