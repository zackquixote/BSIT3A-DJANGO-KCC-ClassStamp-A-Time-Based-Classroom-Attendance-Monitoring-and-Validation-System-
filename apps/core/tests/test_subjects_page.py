"""
# // ==============================================================================
# // KCC CLASSSTAMP - SUBJECT CATALOGUE TESTS
# // ==============================================================================
# // Three additions to /subjects/:
# //   - an unused-only filter (no classes, no curriculum mapping)
# //   - retirement refused while an attendance session is open
# //   - a warning when changing units under active sections
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

User = get_user_model()


class SubjectBase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='subj_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development', units=3)
        self.unused = Subject.objects.create(code='IT999', name='Retired Elective', units=2)
        self.teacher_user = User.objects.create_user(username='subj_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.client.force_login(self.admin_user)

    def _class_and_slot(self, subject=None):
        class_obj = Class.objects.create(
            academic_year=self.year,
            class_code=f'BSIT-1A-{(subject or self.subject).code}',
            subject=subject or self.subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=1,
        )
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        return class_obj, slot

    def _session(self, slot, status=ClassSession.STATUS_OPEN):
        return ClassSession.objects.create(
            slot=slot, session_date=timezone.localdate(), status=status,
            opened_by=self.teacher_user, created_by=self.teacher_user,
        )


class UnusedFilterTests(SubjectBase):
    def test_unused_filter_shows_only_unmapped_subjects(self):
        self._class_and_slot()  # makes IT311 used

        response = self.client.get(reverse('subject_list'), {'usage': 'unused'})

        codes = [s.code for s in response.context['subjects']]
        self.assertIn('IT999', codes)
        self.assertNotIn('IT311', codes)

    def test_no_filter_shows_both(self):
        self._class_and_slot()

        response = self.client.get(reverse('subject_list'))

        codes = [s.code for s in response.context['subjects']]
        self.assertIn('IT311', codes)
        self.assertIn('IT999', codes)

    def test_curriculum_only_subject_counts_as_used(self):
        Curriculum.objects.create(program=self.program, year_level=1, semester=1, subject=self.unused)

        response = self.client.get(reverse('subject_list'), {'usage': 'unused'})

        codes = [s.code for s in response.context['subjects']]
        self.assertNotIn('IT999', codes)


class SubjectRetirementGuardTests(SubjectBase):
    def test_open_session_blocks_retirement(self):
        _, slot = self._class_and_slot()
        self._session(slot)

        response = self.client.post(reverse('subject_delete', args=[self.subject.pk]))

        self.assertEqual(response.status_code, 400)
        self.assertIn('open attendance session', response.json()['error'])
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)

    def test_closed_session_allows_retirement(self):
        _, slot = self._class_and_slot()
        self._session(slot, status=ClassSession.STATUS_CLOSED)

        response = self.client.post(reverse('subject_delete', args=[self.subject.pk]))

        self.assertEqual(response.status_code, 200)
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_active)
        self.assertEqual(response.json()['type'], 'deactivated')


class UnitsChangeWarningTests(SubjectBase):
    def _save(self, units):
        return self.client.post(reverse('subject_save'), {
            'subject_id': self.subject.pk,
            'code': 'IT311',
            'name': 'Web Development',
            'description': '',
            'units': str(units),
            'is_active': '1',
        })

    def test_changing_units_under_active_sections_warns(self):
        self._class_and_slot()

        response = self._save(2)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('1 active section', payload['warning'])
        self.assertIn('3 unit(s)', payload['warning'])
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.units, 2)

    def test_no_warning_when_units_unchanged(self):
        self._class_and_slot()

        response = self._save(3)

        self.assertEqual(response.json()['warning'], '')

    def test_no_warning_without_active_sections(self):
        response = self._save(2)

        self.assertEqual(response.json()['warning'], '')

    def test_warning_ignores_sections_in_a_closed_term(self):
        Class.objects.create(
            academic_year=self.year, class_code='BSIT-2A-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=2, is_active=False,
        )

        response = self._save(2)

        self.assertEqual(response.json()['warning'], '')
