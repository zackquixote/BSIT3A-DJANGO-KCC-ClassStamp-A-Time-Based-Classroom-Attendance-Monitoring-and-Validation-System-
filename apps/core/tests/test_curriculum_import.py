"""
# // ==============================================================================
# // KCC CLASSSTAMP - CURRICULUM DOCUMENT IMPORT
# // ==============================================================================
# // Rehearses `manage.py import_curriculum_docs --apply` end to end against an
# // isolated test database: every programme in docs/curriculum must land with a
# // complete, duplicate-free prospectus, and a second run must change nothing.
# //
# // Skipped automatically where the source documents are absent (they are not
# // shipped with every deployment).
# // ==============================================================================
"""

import io
import pathlib
import unittest

from django.core.management import call_command
from django.test import TestCase

from apps.core.models import (
    Curriculum,
    CurriculumVersion,
    Department,
    Program,
    Subject,
)

DOCS = pathlib.Path('docs/curriculum')
HAS_DOCS = (DOCS / 'Appendix-F.1-BSIT-Curriculum-2023-2024.docx').exists()

EXPECTED = {
    'BSIT': 58,
    'BSA': 63,
    'BSBA': 50,
    'BSTM': 53,
    'BSCRIM': 65,
}


@unittest.skipUnless(HAS_DOCS, 'curriculum source documents are not present')
class CurriculumImportTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cmat = Department.objects.create(
            code='CMAT', name='College of Management, Accountancy, and Technology',
        )
        Department.objects.create(code='CEAS', name='College of Education, Arts, and Sciences')
        Department.objects.create(code='COC', name='College of Criminology')
        Program.objects.create(code='BSIT', name='BS Information Technology',
                               department=cls.cmat, years_total=4)
        Program.objects.create(code='BSA', name='BS Accountancy',
                               department=cls.cmat, years_total=4)
        Program.objects.create(code='BSBA', name='BS Business Administration',
                               department=cls.cmat, years_total=4)

    def test_import_builds_a_complete_prospectus(self):
        call_command('import_curriculum_docs', '--apply', stdout=io.StringIO())

        for code, expected in EXPECTED.items():
            program = Program.objects.get(code=code)
            approved = CurriculumVersion.objects.get(
                program=program, status=CurriculumVersion.STATUS_APPROVED,
            )
            rows = Curriculum.objects.filter(program=program, version=approved)
            self.assertEqual(rows.count(), expected, f'{code} row count')
            self.assertIsNotNone(approved.effective_from, f'{code} effective term')

            keys = list(rows.values_list('year_level', 'semester', 'subject_id'))
            self.assertEqual(len(keys), len(set(keys)), f'{code} has duplicate rows')

            for year, semester, _subject in keys:
                self.assertGreaterEqual(year, 1, f'{code} has an invalid year level')
                self.assertIn(semester, (1, 2, 3), f'{code} has an invalid semester')

    def test_imported_subjects_are_usable(self):
        call_command('import_curriculum_docs', '--apply', stdout=io.StringIO())
        for subject in Subject.objects.all():
            self.assertTrue(subject.name.strip(), f'{subject.code} has no title')
            self.assertGreater(subject.units, 0, f'{subject.code} has no units')
            self.assertLessEqual(len(subject.code), 40)

    def test_second_run_is_a_no_op(self):
        call_command('import_curriculum_docs', '--apply', stdout=io.StringIO())
        rows_after_first = Curriculum.objects.count()
        versions_after_first = CurriculumVersion.objects.count()

        call_command('import_curriculum_docs', '--apply', stdout=io.StringIO())

        self.assertEqual(Curriculum.objects.count(), rows_after_first)
        self.assertEqual(CurriculumVersion.objects.count(), versions_after_first)

    def test_dry_run_writes_nothing(self):
        call_command('import_curriculum_docs', stdout=io.StringIO())
        self.assertEqual(Curriculum.objects.count(), 0)
        self.assertEqual(CurriculumVersion.objects.count(), 0)
        self.assertEqual(Program.objects.filter(code='BSTM').count(), 0)
