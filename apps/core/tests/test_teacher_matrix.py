"""
# // ==============================================================================
# // KCC CLASSSTAMP - TEACHER ATTENDANCE MATRIX TESTS
# // ==============================================================================
# // Verifies the read-only matrix is teacher-scoped, renders the grid, and
# // exports a CSV that matches the on-screen tallies.
# // ==============================================================================
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
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
from apps.core.services.attendance_service import build_attendance_matrix

User = get_user_model()


class TeacherAttendanceMatrixTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31), is_active=True,
        )

        self.teacher_user = User.objects.create_user(username='matrix_teacher', password='Teacher!Pass123')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.other_teacher_user = User.objects.create_user(username='matrix_other', password='Teacher!Pass123')
        self.other_teacher_profile = Profile.objects.create(
            user=self.other_teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.student_user = User.objects.create_user(
            username='matrix_student', password='Student!Pass123', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-3000',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-3A',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )
        self.other_class = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-3B',
            subject=self.subject, teacher_profile=self.other_teacher_profile,
        )
        self.empty_class = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-3C',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )

        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.session = ClassSession.objects.create(
            slot=self.slot, session_date=today, status=ClassSession.STATUS_CLOSED,
            opened_at=timezone.now(), closed_at=timezone.now(),
            opened_by=self.teacher_user, created_by=self.teacher_user,
        )

        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        AttendanceRecord.objects.create(
            session=self.session,
            student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_PRESENT,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
        )

        self.client.force_login(self.teacher_user)

    def test_teacher_can_view_own_class_matrix(self):
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BSIT-3A')
        self.assertContains(response, '2026-3000')
        self.assertContains(response, '100.0%')

    def test_matrix_csv_matches_grid(self):
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk]),
            {'format': 'csv'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment;', response['Content-Disposition'])

        body = response.content.decode('utf-8')
        self.assertIn('Student ID', body)
        self.assertIn('2026-3000', body)
        self.assertIn('PRESENT', body)
        self.assertIn('100.0%', body)

    def test_other_teacher_cannot_view_matrix(self):
        self.client.force_login(self.other_teacher_user)

        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('teacher_dashboard'))

    def test_student_cannot_view_matrix(self):
        self.client.force_login(self.student_user)

        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk])
        )

        self.assertEqual(response.status_code, 302)

    def test_matrix_anonymous_redirects_to_login(self):
        self.client.logout()

        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_matrix_handles_class_without_sessions(self):
        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.empty_class.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No class meetings have been recorded')

    def test_superuser_can_view_any_class_matrix(self):
        admin = User.objects.create_superuser(username='matrix_admin', password='Admin!Pass123')
        self.client.force_login(admin)

        response = self.client.get(
            reverse('teacher_attendance_matrix', args=[self.class_obj.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BSIT-3A')

    def test_admin_matrix_json_endpoint_still_aggregates(self):
        admin = User.objects.create_superuser(username='matrix_super', password='Admin!Pass123')
        self.client.force_login(admin)

        response = self.client.get(
            reverse('class_attendance_matrix', args=[self.class_obj.pk])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['summary']['total_students'], 1)
        self.assertEqual(payload['summary']['total_sessions'], 1)
        self.assertEqual(payload['students'][0]['present'], 1)
        self.assertEqual(payload['students'][0]['rate'], 100.0)

    def test_cancelled_sessions_do_not_dilute_attendance_rate(self):
        ClassSession.objects.create(
            slot=self.slot,
            session_date=timezone.localdate() + timedelta(days=1),
            status=ClassSession.STATUS_CANCELED,
        )

        matrix = build_attendance_matrix(self.class_obj)

        self.assertEqual(matrix['total_sessions'], 1)
        self.assertEqual(matrix['student_rows'][0]['rate'], 100.0)
        self.assertEqual(matrix['overall_rate'], 100.0)
