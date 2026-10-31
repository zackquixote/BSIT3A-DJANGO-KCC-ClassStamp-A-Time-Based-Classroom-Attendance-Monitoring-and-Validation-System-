"""
# // ==============================================================================
# // KCC CLASSSTAMP - DEGREE PROGRAM DIRECTORY TESTS
# // ==============================================================================
# // Three fixes on /programs/:
# //   - curriculum coverage is visible (the Section Wizard depends on it)
# //   - duration cannot be shortened below existing students / curriculum years
# //   - retiring a program with an open session is refused
# ==============================================================================
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    Class,
    ClassSession,
    ClassSlot,
    Curriculum,
    Department,
    Profile,
    Program,
    Subject,
)
from apps.core.services.academic_service import create_or_update_program

User = get_user_model()


class ProgramBase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='prog_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
            years_total=4,
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.client.force_login(self.admin_user)

    def _student(self, number, year_level=1):
        user = User.objects.create_user(username=f'user_{number}')
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=number,
            program=self.program,
            year_level=year_level,
            approval_status=Profile.APPROVAL_APPROVED,
        )


class CurriculumBadgeTests(ProgramBase):
    def test_unconfigured_program_is_flagged(self):
        response = self.client.get(reverse('program_list'))

        row = next(p for p in response.context['programs'] if p.pk == self.program.pk)
        self.assertEqual(row.curriculum_count, 0)
        self.assertContains(response, 'Not configured')

    def test_configured_program_shows_subject_count(self):
        Curriculum.objects.create(program=self.program, year_level=1, semester=1, subject=self.subject)
        other = Subject.objects.create(code='GE101', name='Understanding the Self')
        Curriculum.objects.create(program=self.program, year_level=1, semester=1, subject=other)

        response = self.client.get(reverse('program_list'))

        row = next(p for p in response.context['programs'] if p.pk == self.program.pk)
        self.assertEqual(row.curriculum_count, 2)
        self.assertContains(response, '2 subjects')


class DurationGuardTests(ProgramBase):
    def _update(self, years_total):
        return create_or_update_program(
            actor=self.admin_user,
            dept_id=self.department.pk,
            code='BSIT',
            name='BS Information Technology',
            years_total=years_total,
            is_active=True,
            prog_id=self.program.pk,
        )

    def test_shortening_below_enrolled_year_is_refused(self):
        self._student('2026-7001', year_level=4)

        with self.assertRaises(ValueError) as ctx:
            self._update(3)

        self.assertIn('Year 4', str(ctx.exception))
        self.program.refresh_from_db()
        self.assertEqual(self.program.years_total, 4)

    def test_shortening_below_curriculum_year_is_refused(self):
        Curriculum.objects.create(program=self.program, year_level=4, semester=1, subject=self.subject)

        with self.assertRaises(ValueError):
            self._update(3)

    def test_shortening_to_the_highest_used_year_is_allowed(self):
        self._student('2026-7002', year_level=4)

        result = self._update(4)

        self.assertEqual(result['instance'].years_total, 4)

    def test_extending_duration_is_always_allowed(self):
        self._student('2026-7003', year_level=4)

        result = self._update(5)

        self.assertEqual(result['instance'].years_total, 5)

    def test_endpoint_reports_the_refusal(self):
        self._student('2026-7004', year_level=4)

        response = self.client.post(reverse('program_save'), {
            'id': self.program.pk,
            'code': 'BSIT',
            'name': 'BS Information Technology',
            'years_total': '2',
            'department_id': self.department.pk,
            'is_active': 'true',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Year 4', response.json()['error'])


class ProgramArchiveGuardTests(ProgramBase):
    def setUp(self):
        super().setUp()
        teacher_user = User.objects.create_user(username='prog_teacher')
        self.teacher = Profile.objects.create(
            user=teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=1,
        )
        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )

    def _session(self, status=ClassSession.STATUS_OPEN):
        return ClassSession.objects.create(
            slot=self.slot, session_date=timezone.localdate(), status=status,
            opened_by=self.teacher.user, created_by=self.teacher.user,
        )

    def _retire(self, ajax=True):
        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return self.client.post(reverse('program_delete', args=[self.program.pk]), **headers)

    def test_open_session_blocks_archiving(self):
        self._session()

        response = self._retire()

        self.assertEqual(response.status_code, 400)
        self.assertIn('open attendance session', response.json()['error'])
        self.program.refresh_from_db()
        self.assertTrue(self.program.is_active)

    def test_no_open_session_allows_archiving(self):
        self._session(status=ClassSession.STATUS_CLOSED)

        response = self._retire()

        self.assertEqual(response.status_code, 200)
        self.program.refresh_from_db()
        self.assertFalse(self.program.is_active)

    def test_program_with_classes_is_archived_not_deleted(self):
        # Class.program is SET_NULL: a hard delete would silently orphan the section.
        response = self._retire()

        self.assertEqual(response.status_code, 200)
        self.program.refresh_from_db()
        self.assertFalse(self.program.is_active)
        self.class_obj.refresh_from_db()
        self.assertEqual(self.class_obj.program_id, self.program.pk)

    def test_non_ajax_refusal_redirects(self):
        self._session()

        response = self._retire(ajax=False)

        self.assertEqual(response.status_code, 302)
        self.program.refresh_from_db()
        self.assertTrue(self.program.is_active)
