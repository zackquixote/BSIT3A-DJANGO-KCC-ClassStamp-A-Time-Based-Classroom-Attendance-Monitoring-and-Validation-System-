"""
# // ==============================================================================
# // KCC CLASSSTAMP - SECTION BUILDER WIZARD TESTS
# // ==============================================================================
# // Covers the three fixes to /classes/setup/:
# //   - existing sections grouped by section_code instead of raw class codes
# //   - section-code availability checked at step 3, with a correct suggestion
# //   - stepper exposed to keyboard and assistive technology
# ==============================================================================
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    Class,
    Curriculum,
    Department,
    Profile,
    Program,
    Subject,
)

User = get_user_model()


class WizardBase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
            years_total=4,
        )
        self.academic_year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='wiz_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.admin_user = User.objects.create_user(username='wiz_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.subjects = {
            code: Subject.objects.create(code=code, name=f'Subject {code}')
            for code in ('IT103', 'GE101', 'IT311')
        }
        for code, subject in self.subjects.items():
            Curriculum.objects.create(
                program=self.program, year_level=1, semester=1, subject=subject,
            )

    def _class(self, class_code):
        subject_code = class_code.split('-')[-1]
        return Class.objects.create(
            academic_year=self.academic_year,
            class_code=class_code,
            subject=self.subjects.get(subject_code) or self.subjects['IT103'],
            teacher_profile=self.teacher_profile,
            program=self.program,
            year_level=1,
        )

    def _options(self):
        return self.client.get(reverse('class_wizard_options'), {
            'program_id': self.program.pk,
            'year_level': 1,
            'semester': 1,
            'ay_id': self.academic_year.pk,
        })


class GroupedSectionsTests(WizardBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def test_sections_are_grouped_with_subject_counts(self):
        self._class('BSIT-1A-IT103')
        self._class('BSIT-1A-GE101')
        self._class('BSIT-1B-IT103')

        payload = self._options().json()

        sections = {s['section_code']: s for s in payload['existing_sections']}
        self.assertEqual(sections['BSIT-1A']['subject_count'], 2)
        self.assertEqual(sections['BSIT-1A']['subjects'], ['GE101', 'IT103'])
        self.assertEqual(sections['BSIT-1B']['subject_count'], 1)
        # The legacy flat list stays, so older callers keep working.
        self.assertIn('BSIT-1A-IT103', payload['existing_codes'])

    def test_empty_term_reports_no_sections(self):
        payload = self._options().json()

        self.assertEqual(payload['existing_sections'], [])


class CodeAvailabilityTests(WizardBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def _check(self, code, subject='IT103'):
        return self.client.get(reverse('class_wizard_code_check'), {
            'code': code,
            'ay': self.academic_year.pk,
            'subject': subject,
        })

    def test_free_code_is_available(self):
        response = self._check('BSIT-1A')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['available'])

    def test_taken_code_is_refused_with_a_suggestion(self):
        self._class('BSIT-1A')

        response = self._check('BSIT-1A', subject='IT103')

        payload = response.json()
        self.assertFalse(payload['available'])
        self.assertEqual(payload['clash']['subject'], 'IT103')
        self.assertEqual(payload['suggestion'], 'BSIT-1A-IT103')
        self.assertIn('already used', payload['message'])

    def test_code_is_case_insensitive(self):
        self._class('BSIT-1A')

        payload = self._check('bsit-1a').json()

        self.assertFalse(payload['available'])

    def test_suggestion_is_omitted_when_it_is_also_taken(self):
        self._class('BSIT-1A')
        self._class('BSIT-1A-IT103')

        payload = self._check('BSIT-1A', subject='IT103').json()

        self.assertFalse(payload['available'])
        self.assertEqual(payload['suggestion'], '')

    def test_blank_code_is_rejected(self):
        response = self._check('   ')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['available'])

    def test_teacher_cannot_call_the_endpoint(self):
        self.client.force_login(self.teacher_user)

        response = self._check('BSIT-1A')

        self.assertEqual(response.status_code, 302)


class StepperAccessibilityTests(WizardBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_user)

    def test_stepper_is_keyboard_reachable(self):
        response = self.client.get(reverse('class_wizard_setup'))
        body = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('<nav id="wizard-progress"', body)
        self.assertIn('aria-label="Section builder steps"', body)
        self.assertIn('role="button"', body)
        self.assertIn('aria-label="Step 1 of 5: Curriculum"', body)
        self.assertIn('aria-current="step"', body)
        self.assertIn('id="wiz-code-status"', body)
        self.assertIn('data-code-check-url', body)
