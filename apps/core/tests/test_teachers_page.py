"""
# // ==============================================================================
# // KCC CLASSSTAMP - FACULTY DIRECTORY TESTS
# // ==============================================================================
# // Three changes on /teachers/:
# //   - teaching load is scoped to the active academic year
# //   - deactivating a teacher with a live session is refused (toggle + bulk)
# //   - row selection is hidden behind a Bulk actions toggle
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
    Department,
    Profile,
    Program,
    Subject,
)

User = get_user_model()


class TeacherPageBase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='tch_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.current_year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.old_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=False,
        )
        self.teacher_user = User.objects.create_user(
            username='tch_teacher', first_name='Glenn', last_name='Azuelo',
        )
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.client.force_login(self.admin_user)

    def _class_in(self, year, code):
        class_obj = Class.objects.create(
            academic_year=year, class_code=code, subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=1,
        )
        slot = ClassSlot.objects.create(
            class_obj=class_obj, weekday=timezone.localdate().weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        return class_obj, slot


class TeachingLoadScopeTests(TeacherPageBase):
    def test_load_counts_only_the_active_term(self):
        self._class_in(self.old_year, 'BSIT-1A-IT311')     # history
        self._class_in(self.current_year, 'BSIT-2A-IT311')  # current

        response = self.client.get(reverse('teacher_list'))

        row = next(t for t in response.context['teachers'] if t.pk == self.teacher.pk)
        self.assertEqual(row.class_count, 1)

    def test_active_load_kpi_ignores_past_terms(self):
        other_user = User.objects.create_user(username='tch_old_only')
        other = Profile.objects.create(
            user=other_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        Class.objects.create(
            academic_year=self.old_year, class_code='BSIT-3A-IT311', subject=self.subject,
            teacher_profile=other, program=self.program, year_level=3,
        )
        self._class_in(self.current_year, 'BSIT-2A-IT311')

        response = self.client.get(reverse('teacher_list'))

        self.assertEqual(response.context['active_load_count'], 1)

    def test_pills_are_scoped_to_the_active_term(self):
        self._class_in(self.old_year, 'BSIT-1A-IT311')
        self._class_in(self.current_year, 'BSIT-2A-IT311')

        response = self.client.get(reverse('teacher_list'))

        row = next(t for t in response.context['teachers'] if t.pk == self.teacher.pk)
        codes = [c.class_code for c in row.taught_classes.all()]
        self.assertEqual(codes, ['BSIT-2A-IT311'])


class TeacherRetirementGuardTests(TeacherPageBase):
    def test_toggle_is_refused_while_a_session_is_open(self):
        _, slot = self._class_in(self.current_year, 'BSIT-2A-IT311')
        ClassSession.objects.create(
            slot=slot, session_date=timezone.localdate(), status=ClassSession.STATUS_OPEN,
            opened_by=self.teacher_user, created_by=self.teacher_user,
        )

        response = self.client.post(reverse('teacher_toggle', args=[self.teacher.pk]))

        self.assertEqual(response.status_code, 400)
        self.assertIn('open attendance session', response.json()['error'])
        self.teacher_user.refresh_from_db()
        self.assertTrue(self.teacher_user.is_active)

    def test_toggle_succeeds_without_open_sessions(self):
        self._class_in(self.current_year, 'BSIT-2A-IT311')

        response = self.client.post(reverse('teacher_toggle', args=[self.teacher.pk]))

        self.assertEqual(response.status_code, 200)
        self.teacher_user.refresh_from_db()
        self.assertFalse(self.teacher_user.is_active)


class NoBulkSelectionTests(TeacherPageBase):
    def test_roster_has_no_bulk_selection_ui(self):
        self._class_in(self.current_year, 'BSIT-2A-IT311')

        response = self.client.get(reverse('teacher_list'))
        body = response.content.decode('utf-8')

        self.assertNotIn('teacher-checkbox', body)
        self.assertNotIn('selectAllTeachers', body)
        self.assertNotIn('bulkActionsBar', body)
        self.assertNotIn('bulk_teacher_actions.js', body)

    def test_duplicate_stats_strip_is_gone(self):
        response = self.client.get(reverse('teacher_list'))

        self.assertNotContains(response, 'Teacher Stats Quick Filters')
