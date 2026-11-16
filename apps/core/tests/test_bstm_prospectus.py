"""Tests for the BSTM prospectus sync command."""

import datetime
import io
import os
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from openpyxl import Workbook

from apps.core.models import (
    AcademicYear, Curriculum, CurriculumVersion, Department, Program, Subject,
)
from apps.core.management.commands.update_bstm_prospectus import (
    RENAME_SKIP, clean_units, parse_workbook,
)


def build_prospectus(path):
    """Two years, two semesters side by side, like the registrar's file."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Final 10-31'

    sheet.append(['Kabankalan Catholic College, Inc.'])
    sheet.append([])
    sheet.append(['BACHELOR OF SCIENCE IN TOURISM MANAGEMENT'])
    sheet.append(['Effective School Year 2025-2026'])
    sheet.append(['F I R S T   Y E A R'])
    sheet.append(['FIRST SEMESTER', None, None, None, None, 'SECOND SEMESTER'])
    sheet.append(['CODE', None, 'COURSE TITLE', 'UNITS', 'PRE REQUISITE',
                  'CODE', None, 'COURSE TITLE', 'UNITS', 'PRE REQUISITE'])

    sheet.append(['Theology', '1', 'Revelation and Faith', '[2]', None,
                  'Theology', '2', 'Church History', '[2]', 'Theology 1'])
    sheet.append(['GE', '1', 'Understanding the Self', 3, None,
                  'GE', '3', 'The Contemporary World', 3, None])
    sheet.append([None, None, 'Total Units', 5, None, None, None, 'Total Units', 5, None])

    sheet.append(['SECOND YEAR'])
    sheet.append(['FIRST SEMESTER', None, None, None, None, 'SECOND SEMESTER'])
    sheet.append(['CODE', None, 'COURSE TITLE', 'UNITS', 'PRE REQUISITE',
                  'CODE', None, 'COURSE TITLE', 'UNITS', 'PRE REQUISITE'])
    sheet.append(['Theology', '3', 'Sacraments and Liturgy', '[2]', None,
                  'Theology', '4', 'Christology', '[2]', None])
    sheet.append(['TMC', '1', 'Macro Perspective', 3, None,
                  'TMC', '2', 'Micro Perspective', 3, None])

    workbook.save(path)


class ParserTests(TestCase):
    def test_clean_units_handles_brackets(self):
        self.assertEqual(clean_units('[2]'), 2)
        self.assertEqual(clean_units(' 3 '), 3)
        self.assertIsNone(clean_units('Total Units'))
        self.assertIsNone(clean_units(None))

    def test_parse_workbook_reads_both_semesters(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / 'bstm.xlsx'
        build_prospectus(path)
        try:
            entries = parse_workbook(path)
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)

        self.assertEqual(len(entries), 8)
        self.assertIn((1, 1, 'Theology 1', 'Revelation and Faith', 2), entries)
        self.assertIn((1, 2, 'Theology 2', 'Church History', 2), entries)
        self.assertIn((2, 1, 'Theology 3', 'Sacraments and Liturgy', 2), entries)
        self.assertIn((2, 2, 'TMC 2', 'Micro Perspective', 3), entries)

    def test_total_rows_are_skipped(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / 'bstm.xlsx'
        build_prospectus(path)
        try:
            entries = parse_workbook(path)
        finally:
            os.unlink(path)
            os.rmdir(tmpdir)
        self.assertFalse(any('Total' in title for _y, _s, _c, title, _u in entries))

    def test_theology_two_is_not_renamed(self):
        # Shared with BSA / BSBA / BSIT / BSCRIM, so a rename would relabel them.
        self.assertIn('THEOLOGY2', RENAME_SKIP)


class CommandTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CMAT', name='College of Management')
        self.program = Program.objects.create(
            code='BSTM', name='Bachelor of Science in Tourism Management',
            department=self.department,
        )
        self.version = CurriculumVersion.objects.create(
            program=self.program, version_number=1, status=CurriculumVersion.STATUS_APPROVED,
        )
        AcademicYear.objects.create(
            name='2025-2026 1st Sem', starts_on=datetime.date(2025, 8, 1),
            ends_on=datetime.date(2026, 5, 31), is_active=True,
        )
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / 'bstm.xlsx'
        build_prospectus(self.path)

    def tearDown(self):
        try:
            os.unlink(self.path)
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def run_sync(self, *extra):
        out = io.StringIO()
        call_command(
            'update_bstm_prospectus', '--file', str(self.path),
            *extra, stdout=out,
        )
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self.run_sync('--dry-run')
        self.assertIn('DRY RUN', output)
        self.assertEqual(Curriculum.objects.filter(program=self.program).count(), 0)

    def test_apply_creates_the_matrix(self):
        self.run_sync('--apply')
        self.assertEqual(Curriculum.objects.filter(program=self.program).count(), 8)
        codes = set(
            Curriculum.objects.filter(program=self.program).values_list('subject__code', flat=True)
        )
        self.assertEqual(
            codes,
            {'Theology 1', 'Theology 2', 'GE 1', 'GE 3',
             'Theology 3', 'Theology 4', 'TMC 1', 'TMC 2'},
        )

    def test_rerun_is_idempotent(self):
        self.run_sync('--apply')
        before = Curriculum.objects.filter(program=self.program).count()
        self.run_sync('--apply')
        self.assertEqual(Curriculum.objects.filter(program=self.program).count(), before)

    def test_existing_subject_is_moved_not_duplicated(self):
        # GE 1 already filed under year 2; the file says year 1.
        subject = Subject.objects.create(code='GE 1', name='Understanding the Self', units=3)
        Curriculum.objects.create(
            program=self.program, version=self.version, subject=subject,
            year_level=2, semester=1, is_major=True,
        )

        self.run_sync('--apply')

        entries = Curriculum.objects.filter(program=self.program, subject=subject)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual((entry.year_level, entry.semester), (1, 1))

    def test_typo_title_is_corrected(self):
        Subject.objects.create(code='GE 11', name='The Enterpreneurial Mind', units=3)
        self.run_sync('--apply')
        # Not in the sample workbook, so it must stay untouched.
        self.assertEqual(
            Subject.objects.get(code='GE 11').name, 'The Enterpreneurial Mind'
        )

    def test_units_come_from_the_workbook(self):
        Subject.objects.create(code='Theology 1', name='Old Title', units=3)
        self.run_sync('--apply')
        self.assertEqual(Subject.objects.get(code='Theology 1').units, 2)
