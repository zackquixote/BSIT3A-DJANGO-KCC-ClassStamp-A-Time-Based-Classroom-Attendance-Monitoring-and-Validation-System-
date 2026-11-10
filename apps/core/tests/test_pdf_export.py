"""
# // ==============================================================================
# // KCC CLASSSTAMP - ATTENDANCE MATRIX PDF EXPORT TESTS (task 4.7)
# // ==============================================================================
# // ?format=pdf on the existing matrix path: same dataset as CSV, attachment
# // download, class header + grid + timestamp + generating user. CSV stays.
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

User = get_user_model()


class MatrixPdfExportTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            username='pdf_admin', first_name='Ada', last_name='Admin',
        )
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.teacher_user = User.objects.create_user(username='pdf_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3A-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
        )
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.student_user = User.objects.create_user(username='pdf_student')
        self.student = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT,
            student_number='2026-9100', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        Enrollment.objects.create(
            student_profile=self.student, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        session = ClassSession.objects.create(
            slot=self.slot,
            session_date=timezone.localdate() - timedelta(days=1),
            status=ClassSession.STATUS_CLOSED,
        )
        AttendanceRecord.objects.create(
            session=session, student_profile=self.student,
            status=AttendanceRecord.STATUS_PRESENT,
            method=AttendanceRecord.METHOD_SYSTEM,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse('class_attendance_matrix', args=[self.class_obj.pk])

    def test_pdf_export_returns_attachment_with_pdf_signature(self):
        response = self.client.get(self.url, {'format': 'pdf'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.pdf', response['Content-Disposition'])
        self.assertIn('attendance_matrix_BSIT-3A-IT311', response['Content-Disposition'])
        body = b''.join(response.streaming_content) if response.streaming else response.content
        self.assertTrue(body.startswith(b'%PDF'))

    def test_csv_export_still_works(self):
        response = self.client.get(self.url, {'format': 'csv'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('attendance_matrix_BSIT-3A-IT311', response['Content-Disposition'])
        self.assertIn(b'2026-9100', response.content)

    def test_empty_roster_still_produces_a_valid_pdf(self):
        empty_class = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3C-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
        )
        url = reverse('class_attendance_matrix', args=[empty_class.pk])
        response = self.client.get(url, {'format': 'pdf'})

        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content) if response.streaming else response.content
        self.assertTrue(body.startswith(b'%PDF'))

    def test_unauthorized_user_cannot_export(self):
        outsider = User.objects.create_user(username='pdf_outsider')
        Profile.objects.create(
            user=outsider, role=Profile.ROLE_STUDENT,
            student_number='2026-9199', program=self.program, year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.client.force_login(outsider)
        # The matrix view is admin-only; role_required redirects mismatches.
        response = self.client.get(self.url, {'format': 'pdf'})
        self.assertEqual(response.status_code, 302)

        response = self.client.get(self.url, {'format': 'csv'})
        self.assertEqual(response.status_code, 302)
