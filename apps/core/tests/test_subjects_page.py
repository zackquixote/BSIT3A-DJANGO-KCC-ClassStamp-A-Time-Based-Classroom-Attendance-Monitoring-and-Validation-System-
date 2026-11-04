"""
# // ==============================================================================
# // KCC CLASSSTAMP - SUBJECT CATALOGUE TESTS
# // ==============================================================================
# // Subject catalogue listing, retirement guards, and unit-change warnings.
# ==============================================================================
"""

from datetime import date, time
from urllib.parse import parse_qs

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
    CurriculumVersion,
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


class SubjectCatalogueListingTests(SubjectBase):
    def test_catalogue_shows_used_and_unmapped_subjects_without_usage_filter(self):
        self._class_and_slot()
        Curriculum.objects.create(program=self.program, year_level=1, semester=1, subject=self.unused)

        response = self.client.get(reverse('subject_list'))

        codes = [subject.code for subject in response.context['subjects']]
        self.assertIn('IT311', codes)
        self.assertIn('IT999', codes)
        self.assertNotContains(response, 'All Usage')
        self.assertNotContains(response, 'Unused only')

    def test_empty_results_show_active_filters_and_a_reset_action(self):
        response = self.client.get(
            reverse('subject_list'),
            {'q': 'does-not-exist', 'status': 'active'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No subjects match these filters.')
        self.assertContains(response, 'Search: does-not-exist')
        self.assertContains(response, 'Status: Active')
        self.assertContains(response, 'Clear filters')

    def test_pagination_preserves_filters_and_sort_order(self):
        for index in range(14):
            Subject.objects.create(code=f'IT{500 + index}', name=f'Test Subject {index}')

        response = self.client.get(
            reverse('subject_list'),
            {'status': 'active', 'sort': 'placement'},
        )

        self.assertEqual(response.status_code, 200)
        next_query = parse_qs(response.context['next_page_query'])
        self.assertEqual(next_query['page'], ['2'])
        self.assertEqual(next_query['status'], ['active'])
        self.assertEqual(next_query['sort'], ['placement'])
        self.assertRegex(response.content.decode(), r'href="\?[^"]*page=2[^"]*"')
        self.assertRegex(response.content.decode(), r'href="\?[^"]*sort=placement[^"]*"')


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


class SubjectCurriculumPlacementTests(SubjectBase):
    def test_year_filter_is_available_without_selecting_a_program(self):
        response = self.client.get(reverse('subject_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="filterYear"')
        self.assertIn(1, response.context['year_filter_choices'])

    def test_year_filter_limits_catalogue_to_matching_curriculum_placements(self):
        Curriculum.objects.create(
            program=self.program,
            year_level=2,
            semester=1,
            subject=self.subject,
        )
        Curriculum.objects.create(
            program=self.program,
            year_level=1,
            semester=1,
            subject=self.unused,
        )

        response = self.client.get(
            reverse('subject_list'),
            {'year_level': '2'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [subject.code for subject in response.context['subjects']],
            ['IT311'],
        )
        self.assertEqual(response.context['subjects'][0].placements[0]['year_level'], 2)

    def test_program_and_year_filters_use_the_selected_year_placement(self):
        draft = CurriculumVersion.objects.create(
            program=self.program,
            version_number=1,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        Curriculum.objects.create(
            program=self.program,
            version=draft,
            year_level=1,
            semester=1,
            subject=self.subject,
        )
        Curriculum.objects.create(
            program=self.program,
            version=draft,
            year_level=2,
            semester=1,
            subject=self.unused,
        )

        response = self.client.get(
            reverse('subject_list'),
            {'program': self.program.pk, 'year_level': '2'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [subject.code for subject in response.context['subjects']],
            ['IT999'],
        )
        self.assertEqual(response.context['subjects'][0].placements[0]['year_level'], 2)

    def test_add_subject_form_offers_program_year_semester_and_major(self):
        response = self.client.get(reverse('subject_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="subjectCurriculumProgram"')
        self.assertContains(response, 'id="subjectCurriculumYear"')
        self.assertContains(response, 'id="subjectCurriculumSemester"')
        self.assertContains(response, 'id="subjectCurriculumMajor"')
        self.assertContains(response, 'id="subjectCurriculumProgram" name="curriculum_program_id" class="form-control" required')
        self.assertContains(response, 'id="subjectCurriculumMajor" name="curriculum_is_major" class="form-control" disabled required')
        self.assertContains(response, 'data-years="4"')

    def _create_and_assign(self, **placement):
        return self.client.post(reverse('subject_save'), {
            'code': 'NEW201',
            'name': 'New Program Subject',
            'description': '',
            'units': '3',
            'is_active': '1',
            **placement,
        })

    def test_new_subject_can_be_assigned_to_program_year_and_major_flag(self):
        response = self._create_and_assign(
            curriculum_program_id=self.program.pk,
            curriculum_year_level='2',
            curriculum_semester='2',
            curriculum_is_major='1',
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['curriculum_entry']['is_major'])
        self.assertEqual(payload['curriculum_entry']['year_level'], 2)
        self.assertEqual(payload['curriculum_entry']['semester'], 2)
        self.assertIn('BSIT Year 2', payload['message'])
        self.assertEqual(
            Curriculum.objects.get(subject__code='NEW201').version.status,
            CurriculumVersion.STATUS_DRAFT,
        )

    def test_assignment_to_approved_curriculum_creates_draft_and_preserves_entries(self):
        approved = CurriculumVersion.objects.create(
            program=self.program,
            version_number=1,
            status=CurriculumVersion.STATUS_APPROVED,
            effective_from=self.year,
        )
        Curriculum.objects.create(
            program=self.program,
            version=approved,
            year_level=1,
            semester=1,
            subject=self.subject,
            is_major=True,
        )

        response = self._create_and_assign(
            curriculum_program_id=self.program.pk,
            curriculum_year_level='2',
            curriculum_semester='1',
            curriculum_is_major='0',
        )

        self.assertEqual(response.status_code, 200, response.content)
        draft = CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        draft_entries = list(Curriculum.objects.filter(version=draft).order_by('subject__code'))
        self.assertEqual(len(draft_entries), 2)
        copied_entry = next(entry for entry in draft_entries if entry.subject == self.subject)
        new_entry = next(entry for entry in draft_entries if entry.subject.code == 'NEW201')
        self.assertTrue(copied_entry.is_major)
        self.assertFalse(new_entry.is_major)
        self.assertEqual(new_entry.year_level, 2)

    def test_incomplete_curriculum_placement_does_not_create_subject(self):
        response = self._create_and_assign(
            curriculum_program_id=self.program.pk,
            curriculum_year_level='2',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Choose a program, year level', response.json()['error'])
        self.assertFalse(Subject.objects.filter(code='NEW201').exists())

    def test_new_subject_cannot_be_created_without_curriculum_placement(self):
        response = self._create_and_assign()

        self.assertEqual(response.status_code, 400)
        self.assertIn('program, year level, semester', response.json()['error'])
        self.assertFalse(Curriculum.objects.filter(subject__code='NEW201').exists())

    def test_program_filter_lists_all_subjects_from_its_current_draft(self):
        draft = CurriculumVersion.objects.create(
            program=self.program,
            version_number=1,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        Curriculum.objects.create(
            program=self.program,
            version=draft,
            year_level=2,
            semester=2,
            subject=self.subject,
            is_major=True,
        )

        response = self.client.get(
            reverse('subject_list'),
            {'program': self.program.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [subject.code for subject in response.context['subjects']],
            ['IT311'],
        )
        listed_subject = response.context['subjects'][0]
        self.assertEqual(listed_subject.placements[0]['year_level'], 2)
        self.assertTrue(listed_subject.placements[0]['is_major'])
        self.assertContains(response, 'Draft v1')
        self.assertContains(response, 'Major')
        self.assertContains(response, 'Open full curriculum matrix')
