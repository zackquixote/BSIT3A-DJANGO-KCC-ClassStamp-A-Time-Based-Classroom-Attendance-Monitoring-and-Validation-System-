"""
# // ==============================================================================
# // KCC CLASSSTAMP - SECTION MEMBERSHIP & DERIVATION TESTS
# // ==============================================================================
# // Covers the section identity layer:
# //   - derive_section_code across every convention found in real data
# //   - Class.save() auto-filling the section key
# //   - student_section_summary for regular / irregular / unassigned students
# //   - batch promotion refusing to advance non-regular students
# // ==============================================================================
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import (
    AcademicYear,
    Class,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)
from apps.core.models.classroom import derive_section_code
from apps.core.services.academic_service import _advance_approved_students
from apps.core.services.section_service import (
    section_codes_for,
    student_section_summary,
)

User = get_user_model()


class DeriveSectionCodeTests(TestCase):
    def test_section_plus_subject(self):
        self.assertEqual(derive_section_code('BSIT-1A-IT103'), 'BSIT-1A')

    def test_space_separated_variant(self):
        self.assertEqual(derive_section_code('BSIT-3A WEBDEV'), 'BSIT-3A')

    def test_bare_section(self):
        self.assertEqual(derive_section_code('BSIT-3A'), 'BSIT-3A')

    def test_unparseable_code_is_kept_whole(self):
        self.assertEqual(derive_section_code('W7-OLD'), 'W7-OLD')
        self.assertEqual(derive_section_code('BSIT-OLD'), 'BSIT-OLD')

    def test_case_and_whitespace_are_normalised(self):
        self.assertEqual(derive_section_code('  bsit-2b-it211 '), 'BSIT-2B')

    def test_empty_input(self):
        self.assertEqual(derive_section_code(''), '')
        self.assertEqual(derive_section_code(None), '')


class ClassSectionAutoFillTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT103', name='Computer Programming')
        self.teacher_user = User.objects.create_user(username='sec_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.academic_year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31), is_active=True,
        )

    def _make_class(self, code):
        return Class.objects.create(
            academic_year=self.academic_year,
            class_code=code,
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            program=self.program,
            year_level=1,
        )

    def test_save_fills_section_code(self):
        class_obj = self._make_class('BSIT-1A-IT103')
        self.assertEqual(class_obj.section_code, 'BSIT-1A')

    def test_two_subjects_share_one_section_code(self):
        first = self._make_class('BSIT-1A-IT103')
        other_subject = Subject.objects.create(code='GE101', name='Understanding the Self')
        second = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1A-GE101',
            subject=other_subject,
            teacher_profile=self.teacher_profile,
        )
        self.assertEqual(first.section_code, second.section_code)
        self.assertEqual(first.section_code, 'BSIT-1A')

    def test_explicit_section_code_wins(self):
        class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='IRREG-SPECIAL',
            section_code='BSIT-4C',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
        )
        self.assertEqual(class_obj.section_code, 'BSIT-4C')

    def test_migration_backfill_fills_legacy_rows(self):
        import importlib

        from django.apps import apps as global_apps

        class_obj = self._make_class('BSIT-1A-IT103')
        # Simulate a row written before the column existed.
        Class.objects.filter(pk=class_obj.pk).update(section_code='')

        migration = importlib.import_module('apps.core.migrations.0013_class_section_code')
        migration.backfill_section_codes(global_apps, None)

        class_obj.refresh_from_db()
        self.assertEqual(class_obj.section_code, 'BSIT-1A')


class StudentSectionSummaryTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology', years_total=4,
        )
        self.teacher_user = User.objects.create_user(username='sum_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.current_year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31), is_active=True,
        )
        self.old_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31), is_active=False,
        )
        self.subjects = {
            code: Subject.objects.create(code=code, name=f'Subject {code}')
            for code in ('IT103', 'IT104', 'IT211', 'IT212')
        }

    def _student(self, number, student_type=Profile.STUDENT_TYPE_REGULAR, year=1):
        user = User.objects.create_user(username=f'user_{number}', first_name='Test', last_name=number)
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=number,
            program=self.program,
            year_level=year,
            student_type=student_type,
            approval_status=Profile.APPROVAL_APPROVED,
        )

    def _class(self, code, academic_year=None, year_level=1):
        return Class.objects.create(
            academic_year=academic_year or self.current_year,
            class_code=code,
            subject=self.subjects[code.split('-')[-1]],
            teacher_profile=self.teacher_profile,
            program=self.program,
            year_level=year_level,
        )

    def _enroll(self, profile, class_obj, status=Enrollment.STATUS_ACTIVE):
        return Enrollment.objects.create(
            student_profile=profile, class_obj=class_obj, status=status,
        )

    def test_regular_student_collapses_to_one_section(self):
        student = self._student('2026-0001')
        self._enroll(student, self._class('BSIT-1A-IT103'))
        self._enroll(student, self._class('BSIT-1A-IT104'))

        summary = student_section_summary(student)

        self.assertEqual(summary['sections'], ['BSIT-1A'])
        self.assertEqual(summary['home_section'], 'BSIT-1A')
        self.assertTrue(summary['is_single_section'])
        self.assertEqual(summary['section_count'], 1)

    def test_irregular_student_has_no_home_section(self):
        student = self._student('2026-0002', Profile.STUDENT_TYPE_IRREGULAR, year=3)
        self._enroll(student, self._class('BSIT-2A-IT211', year_level=2))
        self._enroll(student, self._class('BSIT-3B-IT212', year_level=3))

        summary = student_section_summary(student)

        self.assertEqual(summary['sections'], ['BSIT-2A', 'BSIT-3B'])
        self.assertIsNone(summary['home_section'])
        self.assertFalse(summary['is_single_section'])
        self.assertEqual(summary['classification'], Profile.STUDENT_TYPE_IRREGULAR)

    def test_unassigned_student_has_no_section(self):
        student = self._student('2026-0003')

        summary = student_section_summary(student)

        self.assertEqual(summary['sections'], [])
        self.assertIsNone(summary['home_section'])
        self.assertEqual(summary['section_count'], 0)

    def test_pending_enrollment_does_not_count(self):
        student = self._student('2026-0004')
        self._enroll(student, self._class('BSIT-1A-IT103'), status=Enrollment.STATUS_PENDING)

        self.assertEqual(section_codes_for(student), [])

    def test_previous_term_is_excluded(self):
        student = self._student('2026-0005')
        self._enroll(student, self._class('BSIT-1A-IT103', academic_year=self.old_year))

        self.assertEqual(section_codes_for(student, self.current_year), [])
        self.assertEqual(section_codes_for(student, self.old_year), ['BSIT-1A'])


class PromotionClassificationTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology', years_total=4,
        )

    def _student(self, number, student_type):
        user = User.objects.create_user(username=f'promo_{number}')
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=number,
            program=self.program,
            year_level=1,
            student_type=student_type,
            approval_status=Profile.APPROVAL_APPROVED,
        )

    def test_only_regular_students_are_advanced(self):
        regular = self._student('P-1', Profile.STUDENT_TYPE_REGULAR)
        irregular = self._student('P-2', Profile.STUDENT_TYPE_IRREGULAR)
        transferee = self._student('P-3', Profile.STUDENT_TYPE_TRANSFEREE)
        unclassified = self._student('P-4', None)
        unknown = self._student('P-5', 'FRESHMAN')

        promoted = _advance_approved_students()

        for profile in (regular, irregular, transferee, unclassified, unknown):
            profile.refresh_from_db()

        self.assertEqual(promoted, 2)
        self.assertEqual(regular.year_level, 2)
        self.assertEqual(unclassified.year_level, 2)
        self.assertEqual(irregular.year_level, 1, 'Irregular standing is earned by credits, not time.')
        self.assertEqual(transferee.year_level, 1)
        self.assertEqual(unknown.year_level, 1, 'Unrecognised classifications need a human decision.')
