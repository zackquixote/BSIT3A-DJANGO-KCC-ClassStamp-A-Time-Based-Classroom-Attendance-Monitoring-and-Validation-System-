"""
# // ==============================================================================
# // KCC CLASSSTAMP - FEATURE VIEW REGRESSION TESTS
# // ==============================================================================
# // Covers the hardening added to the Week 7+ feature views:
# //   - timetable aggregation and prefetch behaviour (no N+1)
# //   - CSV formula-injection protection on both new exports
# //   - academic-year parameter validation on the period report
# //   - room-verification authorization and mismatch handling
# // ==============================================================================
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    Profile,
    Program,
    Subject,
)

User = get_user_model()


class FeatureViewBase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name='BS Information Technology',
            years_total=4,
        )
        self.academic_year = AcademicYear.objects.create(
            name='2026-2027',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )

        self.admin_user = User.objects.create_user(username='feature_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.teacher_user = User.objects.create_user(username='feature_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )

        self.student_user = User.objects.create_user(
            username='feature_student',
            first_name='Carlos',
            last_name='Yulo',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            program=self.program,
            year_level=1,
            student_number='2025-0001',
            approval_status=Profile.APPROVAL_APPROVED,
        )

        # Formula prefixes are deliberately used as data to prove exports are
        # neutralised rather than passed through to a spreadsheet.
        self.subject = Subject.objects.create(code='IT101', name='=2+2')
        self.class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1A',
            section_code='BSIT-1A',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            program=self.program,
            year_level=1,
        )
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj,
            weekday=0,
            starts_at=time(8, 0),
            ends_at=time(9, 0),
            room='=cmd|calc',
        )
        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.session = ClassSession.objects.create(
            slot=self.slot,
            session_date=date(2026, 11, 2),
            status=ClassSession.STATUS_CLOSED,
            opened_at=timezone.now(),
            closed_at=timezone.now(),
            created_by=self.teacher_user,
            opened_by=self.teacher_user,
            closed_by=self.teacher_user,
        )
        AttendanceRecord.objects.create(
            session=self.session,
            student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_PRESENT,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
            marked_by=self.teacher_user,
        )


class TimetableTests(FeatureViewBase):
    def test_timetable_renders_aggregated_workload(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('teacher_timetable'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_classes'], 1)
        self.assertEqual(response.context['total_slots'], 1)
        self.assertEqual(response.context['schedule'][0]['students'], 1)
        self.assertEqual(response.context['total_hours'], 1.0)

    def test_timetable_query_count_does_not_scale_with_classes(self):
        self.client.force_login(self.teacher_user)
        with CaptureQueriesContext(connection) as one_class:
            self.client.get(reverse('teacher_timetable'))

        second_class = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1B',
            section_code='BSIT-1B',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            program=self.program,
            year_level=1,
        )
        ClassSlot.objects.create(
            class_obj=second_class,
            weekday=1,
            starts_at=time(8, 0),
            ends_at=time(9, 0),
            room='Room 2',
        )
        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=second_class,
            status=Enrollment.STATUS_ACTIVE,
        )

        with CaptureQueriesContext(connection) as two_classes:
            response = self.client.get(reverse('teacher_timetable'))

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(two_classes), len(one_class) + 1)

    def test_timetable_export_neutralises_formula_cells(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('teacher_timetable_export'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("'=2+2", content)
        self.assertIn("'=cmd|calc", content)


class AttendancePeriodReportTests(FeatureViewBase):
    def test_export_neutralises_formula_cells_and_includes_records(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('attendance_period_report_export'),
            {'academic_year': self.academic_year.pk},
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('2025-0001', content)
        self.assertIn("'=2+2", content)

    def test_export_rejects_non_numeric_academic_year(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('attendance_period_report_export'),
            {'academic_year': 'not-a-year'},
        )

        self.assertEqual(response.status_code, 400)

    def test_export_rejects_unknown_academic_year(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('attendance_period_report_export'),
            {'academic_year': '999999'},
        )

        self.assertEqual(response.status_code, 400)

    def test_page_lists_record_count_and_rejects_invalid_year(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('attendance_period_report'),
            {'academic_year': self.academic_year.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['record_count'], 1)

        invalid = self.client.get(
            reverse('attendance_period_report'),
            {'academic_year': 'nope'},
        )
        self.assertEqual(invalid.status_code, 400)


class RoomVerificationTests(FeatureViewBase):
    def test_teacher_verifies_the_assigned_room(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('verify_classroom', args=[self.session.pk]),
            {'room': self.slot.room},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

    def test_room_mismatch_is_rejected(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('verify_classroom', args=[self.session.pk]),
            {'room': 'Somewhere Else'},
        )

        self.assertEqual(response.status_code, 400)

    def test_another_teacher_cannot_verify_the_room(self):
        other_user = User.objects.create_user(username='other_teacher')
        Profile.objects.create(
            user=other_user,
            role=Profile.ROLE_TEACHER,
            department=self.department,
        )
        self.client.force_login(other_user)

        response = self.client.post(
            reverse('verify_classroom', args=[self.session.pk]),
            {'room': self.slot.room},
        )

        self.assertEqual(response.status_code, 403)
