"""Tests for the timetable Excel export and the per-program filter."""

import datetime
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.core.models import (
    AcademicYear, Class, ClassSlot, Department, Profile, Program, Subject,
)
from apps.core.services.timetable_export import build_timetable_workbook
from apps.core.views.timetable_views import build_timetable_context, build_section_sheet


class TimetableExportTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CMAT', name='College of Management')
        self.bsit = Program.objects.create(
            code='BSIT', name='Bachelor of Science in Information Technology',
            department=self.department,
        )
        self.bsa = Program.objects.create(
            code='BSA', name='Bachelor of Science in Accountancy', department=self.department,
        )
        self.term = AcademicYear.objects.create(
            name='2026-2027 1st Sem', starts_on=datetime.date(2026, 8, 1),
            ends_on=datetime.date(2027, 5, 31), is_active=True,
        )
        user = get_user_model().objects.create_user(
            username='t.tabligan', password='x', first_name='Lezeth Rose', last_name='Tabligan',
        )
        self.teacher = Profile.objects.create(user=user, role=Profile.ROLE_TEACHER)

        subject = Subject.objects.create(code='CC 101', name='Introduction to Computing', units=3)
        self.class_obj = Class.objects.create(
            academic_year=self.term, section_code='BSIT-1A', class_code='BSIT-1A-CC-101',
            subject=subject, teacher_profile=self.teacher, program=self.bsit,
            year_level=1, is_active=True,
        )
        ClassSlot.objects.create(class_obj=self.class_obj, weekday=0, starts_at=datetime.time(13, 0),
                                 ends_at=datetime.time(14, 0), room='LAB 1')
        ClassSlot.objects.create(class_obj=self.class_obj, weekday=1, starts_at=datetime.time(13, 0),
                                 ends_at=datetime.time(14, 0), room='LAB 1')
        ClassSlot.objects.create(class_obj=self.class_obj, weekday=2, starts_at=datetime.time(13, 0),
                                 ends_at=datetime.time(16, 0), room='LAB 1')

        admin = get_user_model().objects.create_user(
            username='admin_tt', password='x', first_name='Ada', last_name='Min',
        )
        Profile.objects.create(user=admin, role=Profile.ROLE_ADMIN)
        self.client.force_login(admin)

    # ------------------------------------------------------------------ export
    def test_export_returns_xlsx_attachment(self):
        response = self.client.get(reverse('section_timetable_export'), {'program': 'BSIT'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('BSIT-Section-Timetable-2026-2027.xlsx', response['Content-Disposition'])

    def test_export_workbook_mirrors_the_registrar_layout(self):
        response = self.client.get(reverse('section_timetable_export'), {'program': 'BSIT'})
        workbook = load_workbook(io.BytesIO(response.content))
        sheet = workbook.active

        rows = [
            [cell for cell in row if cell is not None]
            for row in sheet.iter_rows(values_only=True)
        ]
        flat = [' | '.join(str(c) for c in row) for row in rows if row]

        self.assertIn(
            'Bachelor of Science in Information Technology | First Semester, '
            'A.Y. 2026-2027 | 3 units, 1 subjects',
            flat[0],
        )
        self.assertEqual(flat[1], 'BSIT 1A')
        self.assertEqual(flat[2], 'SUBJECTS')
        self.assertEqual(flat[3], 'Code | Description | Faculty | Day | Time | Room | Units | Hrs/Wk')
        self.assertEqual(flat[4], 'CC 101 | Introduction to Computing | Lezeth Rose Tabligan | '
                                  'MT | 1:00 PM - 2:00 PM | LAB 1 | 3 | 2')
        self.assertEqual(flat[5], 'CC 101 | Introduction to Computing | Lezeth Rose Tabligan | '
                                  'W | 1:00 PM - 4:00 PM | LAB 1 | 3 | 3')
        self.assertEqual(flat[6], 'Total — 1 subjects | 3 | 5')

    def test_export_works_for_program_without_timetable(self):
        response = self.client.get(reverse('section_timetable_export'), {'program': 'BSA'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('BSA-Section-Timetable', response['Content-Disposition'])

        workbook = load_workbook(io.BytesIO(response.content))
        flat = [
            str(cell) for row in workbook.active.iter_rows(values_only=True)
            for cell in row if cell is not None
        ]
        self.assertTrue(any('No timetable is on file for BSA' in text for text in flat))

    def test_export_filename_includes_program_and_year(self):
        response = self.client.get(reverse('section_timetable_export'), {'program': 'BSIT'})
        self.assertIn('filename="BSIT-Section-Timetable-2026-2027.xlsx"', response['Content-Disposition'])

    def test_build_workbook_handles_empty_context(self):
        data = build_timetable_workbook({
            'sheets': [], 'program': self.bsa, 'semester_label': 'First Semester',
            'academic_year_label': '2026-2027', 'no_data_reason': 'No timetable is on file.',
        })
        workbook = load_workbook(io.BytesIO(data))
        flat = [
            str(cell) for row in workbook.active.iter_rows(values_only=True)
            for cell in row if cell is not None
        ]
        self.assertTrue(any('No timetable is on file.' in text for text in flat))

    # ------------------------------------------------------- program filter
    def test_each_program_renders_without_error(self):
        for code in ('BSIT', 'BSA', 'BSTM', 'BSBA', 'BSCRIM', 'AB-ELS', 'BEED'):
            response = self.client.get(reverse('section_timetable'), {'program': code})
            self.assertEqual(response.status_code, 200, msg=code)

    def test_program_without_timetable_shows_reason(self):
        response = self.client.get(reverse('section_timetable'), {'program': 'BSA'})
        self.assertContains(response, 'No timetable for this selection')
        self.assertContains(response, 'No timetable is on file for BSA')

    def test_unknown_program_does_not_break_the_page(self):
        response = self.client.get(reverse('section_timetable'), {'program': 'NOTREAL'})
        self.assertEqual(response.status_code, 200)

    def test_program_filter_scopes_to_that_program(self):
        other_subject = Subject.objects.create(code='ACCT 1', name='Principles of Accounting', units=3)
        Class.objects.create(
            academic_year=self.term, section_code='BSA-1A', class_code='BSA-1A-ACCT-1',
            subject=other_subject, teacher_profile=self.teacher, program=self.bsa,
            year_level=1, is_active=True,
        )

        bsit_context = build_timetable_context(
            type('Request', (), {'GET': {'program': 'BSIT'}})()
        )
        self.assertEqual(len(bsit_context['sheets']), 1)
        self.assertEqual(bsit_context['sheets'][0]['section'], 'BSIT 1A')

        bsa_context = build_timetable_context(
            type('Request', (), {'GET': {'program': 'BSA'}})()
        )
        self.assertEqual(len(bsa_context['sheets']), 1)
        self.assertEqual(bsa_context['sheets'][0]['section'], 'BSA 1A')

    def test_section_filter_that_misses_explains_itself(self):
        response = self.client.get(
            reverse('section_timetable'), {'program': 'BSIT', 'section': 'BSIT 4C'},
        )
        self.assertContains(response, 'is not on file for')

    def test_sheet_caption_matches_workbook_wording(self):
        sheet = build_section_sheet('BSIT-1A', [self.class_obj])
        self.assertEqual(sheet['caption'], '3 units, 1 subjects')
        self.assertEqual(sheet['total_hours_label'], '5')

    def test_term_dropdown_hides_years_without_classes(self):
        # Cohorts that only exist because a curriculum document mentioned them
        # (no class ever filed there) must not clutter the filter.
        empty_term = AcademicYear.objects.create(
            name='2024-2025 1st Sem', starts_on=datetime.date(2024, 8, 1),
            ends_on=datetime.date(2025, 5, 31), is_active=False,
        )
        response = self.client.get(reverse('section_timetable'))
        terms = list(response.context['terms'])
        self.assertIn(self.term, terms)
        self.assertNotIn(empty_term, terms)

    def test_active_term_is_always_offered_even_when_empty(self):
        # A brand-new active year with no classes yet still has to be selectable.
        new_active = AcademicYear.objects.create(
            name='2027-2028 1st Sem', starts_on=datetime.date(2027, 8, 1),
            ends_on=datetime.date(2028, 5, 31), is_active=True,
        )
        AcademicYear.objects.filter(pk=self.term.pk).update(is_active=False)

        response = self.client.get(reverse('section_timetable'))
        terms = list(response.context['terms'])
        self.assertIn(new_active, terms)

    def test_program_list_is_scoped_to_the_department(self):
        other_dept = Department.objects.create(code='CEAS', name='College of Education')
        Program.objects.create(code='BEED', name='Bachelor of Elementary Education', department=other_dept)

        response = self.client.get(reverse('section_timetable'), {'department': 'CMAT'})
        codes = [p.code for p in response.context['programs']]
        self.assertIn('BSIT', codes)
        self.assertIn('BSA', codes)
        self.assertNotIn('BEED', codes)

    def test_department_is_derived_from_the_program(self):
        response = self.client.get(reverse('section_timetable'), {'program': 'BSIT'})
        self.assertEqual(response.context['department'].code, 'CMAT')

    def test_program_from_another_department_is_reset(self):
        other_dept = Department.objects.create(code='CEAS', name='College of Education')
        beed = Program.objects.create(
            code='BEED', name='Bachelor of Elementary Education', department=other_dept,
        )
        # CEAS is chosen but BSIT (CMAT) is still in the querystring.
        response = self.client.get(
            reverse('section_timetable'), {'department': 'CEAS', 'program': 'BSIT'},
        )
        self.assertEqual(response.context['department'].code, 'CEAS')
        self.assertNotEqual(response.context['program'].code, 'BSIT')
        self.assertTrue(all(p.department_id == other_dept.id for p in response.context['programs']))

    def test_department_without_timetable_explains_itself(self):
        Department.objects.create(code='CEAS', name='College of Education')
        response = self.client.get(reverse('section_timetable'), {'department': 'CEAS'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No timetable for this selection')

    def test_empty_state_does_not_leak_admin_internals(self):
        # The page is shown to a panel, so it must not expose the CLI command or
        # advertise which other programs already have a timetable.
        Department.objects.create(code='CEAS', name='College of Education')
        response = self.client.get(reverse('section_timetable'), {'department': 'CEAS'})
        self.assertNotContains(response, 'manage.py')
        self.assertNotContains(response, 'import_section_timetable')
        self.assertNotContains(response, 'Timetable available for')

    def test_export_follows_the_department_filter(self):
        response = self.client.get(
            reverse('section_timetable_export'), {'department': 'CMAT', 'program': 'BSIT'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('BSIT-Section-Timetable', response['Content-Disposition'])

    def test_page_extends_the_app_shell(self):
        # Guards against dropping {% extends %}: without it the page still
        # renders data but loses every stylesheet and the navigation chrome.
        response = self.client.get(reverse('section_timetable'))
        html = response.content.decode('utf-8')
        self.assertIn('rel="stylesheet"', html)
        self.assertIn('class="sidebar', html)
        self.assertIn('<style>', html)

    def test_export_page_also_extends_the_shell(self):
        response = self.client.get(reverse('section_timetable'), {'program': 'BSA'})
        html = response.content.decode('utf-8')
        self.assertIn('rel="stylesheet"', html)

    def test_no_inline_handlers_are_used(self):
        # The CSP allows 'self' + nonce only, so onchange="..." never runs. Every
        # control has to be wired from the nonce'd script instead.
        response = self.client.get(reverse('section_timetable'))
        html = response.content.decode('utf-8')
        self.assertNotIn('onchange=', html)
        self.assertNotIn('onclick=', html)
        self.assertIn("addEventListener('change'", html)
        self.assertIn('ttPrintBtn', html)

    def test_filter_form_supports_enter_submission(self):
        response = self.client.get(reverse('section_timetable'))
        html = response.content.decode('utf-8')
        self.assertIn('id="ttFiltersForm"', html)
        self.assertIn('tt-submit-hidden', html)
        self.assertIn("event.key === 'Enter'", html)
