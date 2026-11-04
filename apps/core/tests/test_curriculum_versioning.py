"""Curriculum versioning workflow tests (Change 2)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    Curriculum,
    CurriculumVersion,
    Department,
    Profile,
    Program,
    Subject,
)


User = get_user_model()


class CurriculumVersionBase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name='Information Technology',
            years_total=4,
        )
        self.term = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.later_term = AcademicYear.objects.create(
            name='2027-2028',
            starts_on=date(2027, 6, 1),
            ends_on=date(2028, 3, 31),
            is_active=False,
        )
        self.intro = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.programming = Subject.objects.create(code='IT102', name='Computer Programming')

        self.admin_user = User.objects.create_user(username='version_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.client.force_login(self.admin_user)

    def _assign(self, subject, year_level=1, semester=1, is_major=False):
        return self.client.post(reverse('program_curriculum_assign'), {
            'program_id': self.program.pk,
            'subject_id': subject.pk,
            'year_level': year_level,
            'semester': semester,
            'is_major': 'true' if is_major else 'false',
        })

    def _approve(self, effective_from=None):
        payload = {}
        if effective_from is not None:
            payload['effective_from'] = effective_from.pk
        return self.client.post(
            reverse('program_curriculum_approve', args=[self.program.pk]),
            payload,
        )

    def _create_draft(self):
        return self.client.post(
            reverse('program_curriculum_draft_create', args=[self.program.pk]),
        )

    def _set_major(self, entry_id, is_major=True):
        return self.client.post(
            reverse('program_curriculum_major_update', args=[entry_id]),
            {'is_major': 'true' if is_major else 'false'},
        )

    def _create_approved_v1(self, subjects, effective_from=None):
        for subject in subjects:
            response = self._assign(subject)
            self.assertEqual(response.status_code, 200, response.content)
        response = self._approve(effective_from=effective_from or self.term)
        self.assertEqual(response.status_code, 200, response.content)
        return CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_APPROVED,
        )

    def _wizard_subject_codes(self, term, year_level=1, semester=1):
        response = self.client.get(reverse('class_wizard_options'), {
            'program_id': self.program.pk,
            'year_level': year_level,
            'semester': semester,
            'ay_id': term.pk,
        })
        self.assertEqual(response.status_code, 200, response.content)
        return [subject['code'] for subject in response.json()['subjects']]

    def test_wizard_marks_major_subject_for_selected_year_and_semester(self):
        self._assign(self.intro, year_level=2, semester=2, is_major=True)
        self._assign(self.programming, year_level=2, semester=2)
        self.assertEqual(self._approve(effective_from=self.term).status_code, 200)

        response = self.client.get(reverse('class_wizard_options'), {
            'program_id': self.program.pk,
            'year_level': 2,
            'semester': 2,
            'ay_id': self.term.pk,
        })

        self.assertEqual(response.status_code, 200)
        subjects = {subject['code']: subject for subject in response.json()['subjects']}
        self.assertTrue(subjects['IT101']['is_major'])
        self.assertFalse(subjects['IT102']['is_major'])


class DraftVersionTests(CurriculumVersionBase):
    def test_first_assignment_creates_draft_version(self):
        response = self._assign(self.intro)

        self.assertEqual(response.status_code, 200)
        entry = Curriculum.objects.get(pk=response.json()['entry']['id'])
        self.assertIsNotNone(entry.version_id)
        self.assertEqual(entry.version.status, CurriculumVersion.STATUS_DRAFT)
        self.assertEqual(entry.version.version_number, 1)
        self.assertEqual(entry.version.created_by, self.admin_user)

    def test_program_list_counts_only_official_entries(self):
        self._assign(self.intro)

        response = self.client.get(reverse('program_list'))
        row = next(p for p in response.context['programs'] if p.pk == self.program.pk)

        self.assertEqual(row.curriculum_count, 0)
        self.assertEqual(row.draft_version_count, 1)
        self.assertContains(response, 'Draft pending')

    def test_matrix_shows_draft_and_allows_editing(self):
        self._assign(self.intro)

        response = self.client.get(
            reverse('program_curriculum_list', args=[self.program.pk])
        )
        payload = response.json()

        self.assertTrue(payload['ok'])
        self.assertTrue(payload['can_edit'])
        self.assertFalse(payload['is_legacy'])
        self.assertEqual(payload['version']['status'], CurriculumVersion.STATUS_DRAFT)
        self.assertEqual(payload['draft_version']['version_number'], 1)
        self.assertEqual(len(payload['entries']), 1)

    def test_existing_draft_entry_can_be_marked_major(self):
        self._assign(self.intro, year_level=2, semester=2)
        entry = Curriculum.objects.get(subject=self.intro)

        response = self._set_major(entry.pk)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['entry']['is_major'])
        entry.refresh_from_db()
        self.assertTrue(entry.is_major)

    def test_approved_curriculum_entry_cannot_be_reclassified(self):
        approved = self._create_approved_v1([self.intro])
        entry = Curriculum.objects.get(version=approved)

        response = self._set_major(entry.pk)

        self.assertEqual(response.status_code, 400)
        self.assertIn('read-only', response.json()['error'])
        entry.refresh_from_db()
        self.assertFalse(entry.is_major)

    def test_major_flag_is_saved_and_returned_in_matrix(self):
        response = self._assign(self.intro, year_level=2, semester=2, is_major=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['entry']['is_major'])

        matrix = self.client.get(
            reverse('program_curriculum_list', args=[self.program.pk])
        ).json()
        entry = matrix['entries'][0]
        self.assertEqual((entry['year_level'], entry['semester']), (2, 2))
        self.assertTrue(entry['is_major'])

    def test_major_flag_is_preserved_when_creating_draft_from_approved(self):
        response = self._assign(self.intro, is_major=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._approve(effective_from=self.term).status_code, 200)

        self.assertEqual(self._create_draft().status_code, 200)
        draft = CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        self.assertTrue(Curriculum.objects.get(version=draft).is_major)

    def test_create_draft_clones_approved_entries(self):
        approved = self._create_approved_v1([self.intro])

        response = self._create_draft()
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['created'])
        draft = CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        self.assertEqual(draft.version_number, 2)
        draft_entries = Curriculum.objects.filter(version=draft)
        self.assertEqual(draft_entries.count(), 1)
        self.assertEqual(draft_entries.get().subject, self.intro)
        self.assertEqual(
            Curriculum.objects.filter(version=approved).count(),
            1,
        )
        self.assertEqual(payload['version']['version_number'], 2)

    def test_create_draft_is_idempotent_while_a_draft_exists(self):
        self._assign(self.intro)

        response = self._create_draft()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['created'])
        self.assertEqual(
            CurriculumVersion.objects.filter(
                program=self.program,
                status=CurriculumVersion.STATUS_DRAFT,
            ).count(),
            1,
        )


class ApprovalWorkflowTests(CurriculumVersionBase):
    def test_approve_sets_metadata_and_effective_term(self):
        self._assign(self.intro)

        response = self._approve(effective_from=self.term)

        self.assertEqual(response.status_code, 200)
        version = CurriculumVersion.objects.get(program=self.program)
        self.assertEqual(version.status, CurriculumVersion.STATUS_APPROVED)
        self.assertEqual(version.effective_from, self.term)
        self.assertEqual(version.approved_by, self.admin_user)
        self.assertIsNotNone(version.approved_at)

    def test_approving_successor_archives_previous_version(self):
        first = self._create_approved_v1([self.intro], effective_from=self.term)
        self._create_draft()
        draft = CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        draft_entry = Curriculum.objects.get(version=draft, subject=self.intro)
        remove = self.client.post(
            reverse('program_curriculum_remove', args=[draft_entry.pk])
        )
        self.assertEqual(remove.status_code, 200)
        self._assign(self.programming)

        response = self._approve(effective_from=self.later_term)

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(first.status, CurriculumVersion.STATUS_ARCHIVED)
        self.assertEqual(draft.status, CurriculumVersion.STATUS_APPROVED)
        self.assertEqual(draft.effective_from, self.later_term)
        self.assertEqual(draft.entries.get().subject, self.programming)

    def test_approved_curriculum_rejects_assignment_until_draft_exists(self):
        self._create_approved_v1([self.intro])

        response = self._assign(self.programming)

        self.assertEqual(response.status_code, 400)
        self.assertIn('read-only', response.json()['error'])

    def test_approved_entry_cannot_be_removed(self):
        approved = self._create_approved_v1([self.intro])
        entry = Curriculum.objects.get(version=approved)

        response = self.client.post(
            reverse('program_curriculum_remove', args=[entry.pk])
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('read-only', response.json()['error'])
        self.assertTrue(Curriculum.objects.filter(pk=entry.pk).exists())

    def test_approve_requires_a_subject(self):
        self._create_draft()

        response = self._approve(effective_from=self.term)

        self.assertEqual(response.status_code, 400)
        self.assertIn('at least one subject', response.json()['error'])
        self.assertFalse(
            CurriculumVersion.objects.filter(
                program=self.program,
                status=CurriculumVersion.STATUS_APPROVED,
            ).exists()
        )

    def test_matrix_is_read_only_when_approved(self):
        self._create_approved_v1([self.intro])

        payload = self.client.get(
            reverse('program_curriculum_list', args=[self.program.pk])
        ).json()

        self.assertFalse(payload['can_edit'])
        self.assertEqual(payload['version']['status'], CurriculumVersion.STATUS_APPROVED)


class ApprovedVersionWizardTests(CurriculumVersionBase):
    def test_wizard_uses_approved_version_for_selected_term(self):
        first = self._create_approved_v1([self.intro], effective_from=self.term)
        self._create_draft()
        draft = CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        draft_entry = Curriculum.objects.get(version=draft, subject=self.intro)
        self.client.post(reverse('program_curriculum_remove', args=[draft_entry.pk]))
        self._assign(self.programming)
        self._approve(effective_from=self.later_term)
        first.refresh_from_db()

        self.assertEqual(self._wizard_subject_codes(self.term), ['IT101'])
        self.assertEqual(self._wizard_subject_codes(self.later_term), ['IT102'])

    def test_wizard_ignores_drafts(self):
        self._create_approved_v1([self.intro], effective_from=self.term)
        self._create_draft()
        draft = CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        Curriculum.objects.create(
            program=self.program,
            version=draft,
            year_level=1,
            semester=1,
            subject=self.programming,
        )

        self.assertEqual(self._wizard_subject_codes(self.term), ['IT101'])

    def test_wizard_falls_back_to_legacy_unversioned_rows(self):
        Curriculum.objects.create(
            program=self.program,
            year_level=1,
            semester=1,
            subject=self.intro,
        )

        self.assertEqual(self._wizard_subject_codes(self.term), ['IT101'])

    def test_wizard_save_rejects_subject_outside_approved_curriculum(self):
        self._create_approved_v1([self.intro], effective_from=self.term)
        teacher_user = User.objects.create_user(username='version_teacher')
        teacher = Profile.objects.create(
            user=teacher_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )

        response = self.client.post(reverse('class_wizard_save'), {
            'program_id': self.program.pk,
            'year_level': 1,
            'semester': 1,
            'subject_id': self.programming.pk,
            'teacher_profile_id': teacher.pk,
            'ay_id': self.term.pk,
            'class_code': 'BSIT-1A-IT102',
            'capacity': '40',
            'grace_minutes': '10',
            'slots': (
                '[{"weekday": 0, "starts_at": "08:00", '
                '"ends_at": "09:00", "room": "RM-1"}]'
            ),
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('not part of the approved curriculum', response.json()['message'])


class OfficialCurriculumReportingTests(CurriculumVersionBase):
    def test_readiness_ignores_draft_only_curriculum(self):
        self._assign(self.intro)

        response = self.client.get(reverse('curriculum_readiness_report'))

        self.assertEqual(response.status_code, 200)
        report = response.context['report']
        row = report['program_rows'][0]
        self.assertEqual(row['mapped_count'], 0)
        self.assertEqual(row['status'], 'not_configured')
        self.assertEqual(report['totals']['incomplete_programs'], 0)

    def test_readiness_uses_approved_snapshot_not_draft(self):
        self._create_approved_v1([self.intro], effective_from=self.term)
        self._create_draft()
        draft = CurriculumVersion.objects.get(
            program=self.program,
            status=CurriculumVersion.STATUS_DRAFT,
        )
        Curriculum.objects.create(
            program=self.program,
            version=draft,
            year_level=1,
            semester=2,
            subject=self.programming,
        )

        report = self.client.get(
            reverse('curriculum_readiness_report')
        ).context['report']
        semester_codes = {
            row['semester']: [subject['code'] for subject in row['subjects']]
            for row in report['coverage_rows']
            if row['year_level'] == 1
        }

        self.assertEqual(semester_codes[1], ['IT101'])
        self.assertEqual(semester_codes[2], [])

    def test_subject_catalogue_counts_only_official_mappings(self):
        self._assign(self.intro)

        response = self.client.get(reverse('subject_list'))
        row = next(
            subject for subject in response.context['subjects']
            if subject.pk == self.intro.pk
        )

        self.assertEqual(row.curriculum_count, 0)
        self.assertEqual(row.placements, [])
