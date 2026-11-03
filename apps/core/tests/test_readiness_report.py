"""Read-only curriculum and term readiness report tests."""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    Class,
    ClassSlot,
    Curriculum,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)


User = get_user_model()


class ReadinessBase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name='Information Technology',
            years_total=1,
        )
        self.subjects = [
            Subject.objects.create(code='IT101', name='Introduction to Computing'),
            Subject.objects.create(code='IT102', name='Computer Programming'),
            Subject.objects.create(code='IT103', name='Data Structures'),
        ]
        for semester, subject in enumerate(self.subjects, start=1):
            Curriculum.objects.create(
                program=self.program,
                year_level=1,
                semester=semester,
                subject=subject,
            )

        self.term = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username='readiness_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.teacher_user = User.objects.create_user(username='readiness_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        self.student_user = User.objects.create_user(username='readiness_student')
        self.student = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-2001',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.term,
            class_code='BSIT-1A-IT101',
            section_code='BSIT-1A',
            subject=self.subjects[0],
            teacher_profile=self.teacher,
            program=self.program,
            year_level=1,
        )
        ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=0,
            starts_at=time(8, 0),
            ends_at=time(9, 0),
            room='Room 1',
        )
        Enrollment.objects.create(
            student_profile=self.student,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.admin_user)

    def _report(self, **params):
        return self.client.get(reverse('curriculum_readiness_report'), params)


class ReadinessEmptyTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='empty_readiness_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.client.force_login(self.admin_user)

    def test_empty_database_renders_safely(self):
        response = self.client.get(reverse('curriculum_readiness_report'))

        self.assertEqual(response.status_code, 200)
        report = response.context['report']
        self.assertEqual(report['program_rows'], [])
        self.assertEqual(report['term_rows'], [])
        self.assertEqual(report['class_issues'], [])
        self.assertEqual(report['totals']['programs'], 0)
        self.assertEqual(report['totals']['classes'], 0)


class ReadinessReportTests(ReadinessBase):
    def test_report_requires_admin(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('curriculum_readiness_report'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_complete_program_and_class_have_no_gaps(self):
        response = self._report()

        self.assertEqual(response.status_code, 200)
        report = response.context['report']
        self.assertEqual(report['totals']['programs'], 1)
        self.assertEqual(report['totals']['complete_programs'], 1)
        self.assertEqual(report['totals']['empty_slots'], 0)
        self.assertEqual(report['totals']['inactive_mappings'], 0)
        self.assertEqual(report['program_rows'][0]['status'], 'complete')
        self.assertEqual(report['class_issues'], [])

    def test_inactive_subject_is_flagged_for_review(self):
        self.subjects[1].is_active = False
        self.subjects[1].save(update_fields=['is_active', 'updated_at'])

        report = self._report().context['report']

        self.assertEqual(report['totals']['inactive_mappings'], 1)
        self.assertEqual(report['program_rows'][0]['status'], 'inactive_subjects')
        semester_rows = report['program_rows'][0]['years'][0]['semesters']
        self.assertEqual(semester_rows[1]['status'], 'inactive')
        self.assertEqual(semester_rows[1]['status_label'], 'Inactive subjects only')
        self.assertFalse(semester_rows[1]['subjects'][0]['is_active'])

    def test_empty_curriculum_slot_is_distinct_from_a_configured_program(self):
        Curriculum.objects.filter(
            program=self.program,
            year_level=1,
            semester=3,
        ).delete()

        report = self._report().context['report']

        self.assertEqual(report['totals']['empty_slots'], 1)
        self.assertEqual(report['program_rows'][0]['status'], 'incomplete')
        semester_rows = report['program_rows'][0]['years'][0]['semesters']
        self.assertEqual(semester_rows[2]['status'], 'empty')
        self.assertEqual(semester_rows[2]['subjects'], [])

    def test_unconfigured_program_is_not_reported_as_empty_slots(self):
        self.program.curriculum_entries.all().delete()

        report = self._report().context['report']

        self.assertEqual(report['totals']['unconfigured_programs'], 1)
        self.assertEqual(report['totals']['empty_slots'], 3)
        self.assertEqual(report['program_rows'][0]['status'], 'not_configured')

    def test_class_gaps_and_duplicate_offering_are_reported(self):
        self.class_obj.slots.all().delete()
        self.class_obj.enrollments.all().delete()
        self.teacher_user.is_active = False
        self.teacher_user.save(update_fields=['is_active'])

        duplicate = Class.objects.create(
            academic_year=self.term,
            class_code='BSIT-1A-IT101-B',
            section_code='BSIT-1A',
            subject=self.subjects[0],
            teacher_profile=self.teacher,
            program=self.program,
            year_level=1,
        )
        unmapped_subject = Subject.objects.create(code='IT999', name='Elective')
        Class.objects.create(
            academic_year=self.term,
            class_code='BSIT-1A-IT999',
            section_code='BSIT-1A',
            subject=unmapped_subject,
            teacher_profile=self.teacher,
            program=self.program,
            year_level=1,
        )

        report = self._report().context['report']

        self.assertEqual(report['totals']['classes_with_issues'], 3)
        self.assertEqual(report['totals']['missing_schedules'], 3)
        self.assertEqual(report['totals']['missing_rosters'], 3)
        self.assertEqual(report['totals']['inactive_teachers'], 3)

        issues_by_code = {
            row['class_obj'].class_code: ' | '.join(row['issues'])
            for row in report['class_issues']
        }
        self.assertIn('No active schedule', issues_by_code[self.class_obj.class_code])
        self.assertIn('No active roster', issues_by_code[self.class_obj.class_code])
        self.assertIn('Teacher account is inactive', issues_by_code[self.class_obj.class_code])
        self.assertIn('Duplicate section and subject', issues_by_code[duplicate.class_code])
        self.assertIn('Subject is not mapped', issues_by_code['BSIT-1A-IT999'])

    def test_program_filter_scopes_coverage_and_classes(self):
        other_program = Program.objects.create(
            department=self.department,
            code='BSCS',
            name='Computer Science',
            years_total=1,
        )
        other_subject = Subject.objects.create(code='CS101', name='Computing Fundamentals')
        Curriculum.objects.create(
            program=other_program,
            year_level=1,
            semester=1,
            subject=other_subject,
        )

        report = self._report(program=other_program.pk).context['report']

        self.assertEqual(len(report['program_rows']), 1)
        self.assertEqual(report['program_rows'][0]['program'].code, 'BSCS')
        self.assertEqual(report['totals']['classes'], 0)
        self.assertEqual(report['class_issues'], [])

    def test_coverage_csv_exports_every_slot(self):
        response = self.client.get(
            reverse('curriculum_readiness_export', args=['coverage'])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        content = response.content.decode('utf-8')
        self.assertIn('Department,Program,Program Title', content)
        self.assertIn('IT101', content)
        self.assertIn('Complete', content)

    def test_issues_csv_exports_operational_gaps(self):
        self.class_obj.slots.all().delete()
        self.class_obj.enrollments.all().delete()
        self.teacher_user.is_active = False
        self.teacher_user.save(update_fields=['is_active'])

        response = self.client.get(
            reverse('curriculum_readiness_export', args=['issues'])
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('No active schedule', content)
        self.assertIn('No active roster', content)
        self.assertIn('Teacher account is inactive', content)

    def test_unknown_export_type_is_rejected(self):
        response = self.client.get(
            reverse('curriculum_readiness_export', args=['summary'])
        )

        self.assertEqual(response.status_code, 404)
