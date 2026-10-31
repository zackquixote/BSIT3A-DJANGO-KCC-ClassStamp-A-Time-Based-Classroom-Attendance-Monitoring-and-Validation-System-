"""
# // ==============================================================================
# // KCC CLASSSTAMP - ADMIN FLOW GAP TESTS
# // ==============================================================================
# // The three holes found while mapping the admin flow:
# //   1. approved students with no section are invisible on the dashboard
# //   2. deactivating a class left its open sessions scannable
# //   3. rejection was terminal — no path back into the queue
# ==============================================================================
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AuditEvent,
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


class FlowGapBase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
            years_total=4,
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username='gap_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.teacher_user = User.objects.create_user(username='gap_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A', subject=self.subject,
            teacher_profile=self.teacher_profile, program=self.program, year_level=1,
        )
        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.client.force_login(self.admin_user)

    def _student(self, number, status=Profile.APPROVAL_APPROVED):
        user = User.objects.create_user(username=f'user_{number}', first_name='Test', last_name=number)
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=number,
            program=self.program,
            year_level=1,
            approval_status=status,
        )


class UnassignedKpiTests(FlowGapBase):
    def test_approved_student_without_section_is_counted(self):
        self._student('2026-9001')

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['unassigned_count'], 1)
        self.assertContains(response, 'not enrolled in any section')

    def test_enrolled_student_is_not_counted(self):
        student = self._student('2026-9002')
        Enrollment.objects.create(
            student_profile=student, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.context['unassigned_count'], 0)
        self.assertNotContains(response, 'not enrolled in any section')

    def test_pending_student_is_not_counted(self):
        self._student('2026-9003', status=Profile.APPROVAL_PENDING)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.context['unassigned_count'], 0)


class ClassDeactivationGuardTests(FlowGapBase):
    def _session(self, status=ClassSession.STATUS_OPEN):
        return ClassSession.objects.create(
            slot=self.slot, session_date=timezone.localdate(), status=status,
            opened_by=self.teacher_user, created_by=self.teacher_user,
        )

    def test_open_session_blocks_deactivation(self):
        self._session()

        response = self.client.post(reverse('class_toggle', args=[self.class_obj.pk]))

        self.assertEqual(response.status_code, 302)
        self.class_obj.refresh_from_db()
        self.assertTrue(self.class_obj.is_active, 'Deactivation must be refused while a session is open.')
        self.assertTrue(AuditEvent.objects.filter(action='BLOCKED_CLASS_DEACTIVATION').exists())

    def test_closed_session_does_not_block(self):
        self._session(status=ClassSession.STATUS_CLOSED)

        self.client.post(reverse('class_toggle', args=[self.class_obj.pk]))

        self.class_obj.refresh_from_db()
        self.assertFalse(self.class_obj.is_active)

    def test_no_sessions_toggles_normally(self):
        self.client.post(reverse('class_toggle', args=[self.class_obj.pk]))

        self.class_obj.refresh_from_db()
        self.assertFalse(self.class_obj.is_active)
        self.assertTrue(AuditEvent.objects.filter(action='TOGGLE_CLASS').exists())


class ReopenRejectedRegistrationTests(FlowGapBase):
    def _rejected(self, number='2026-9100'):
        student = self._student(number, status=Profile.APPROVAL_REJECTED)
        student.approved_by = self.admin_user
        student.approved_at = timezone.now()
        student.approval_note = 'Blurred COR'
        student.save(update_fields=['approved_by', 'approved_at', 'approval_note'])
        return student

    def test_reopen_returns_the_student_to_the_queue(self):
        student = self._rejected()

        response = self.client.post(
            reverse('validation_reopen', args=[student.student_number]),
            {'reason': 'Student brought a clear COR'},
        )

        self.assertEqual(response.status_code, 302)
        student.refresh_from_db()
        self.assertEqual(student.approval_status, Profile.APPROVAL_PENDING)
        self.assertIsNone(student.approval_note)
        self.assertIsNone(student.approved_by)
        self.assertIsNone(student.approved_at)

        event = AuditEvent.objects.get(action='REOPEN_STUDENT_REGISTRATION')
        self.assertIn('Blurred COR', event.old_value)
        self.assertEqual(event.new_value, 'PENDING')

    def test_reopen_accepts_a_replacement_document(self):
        student = self._rejected('2026-9101')
        upload = SimpleUploadedFile('cor.pdf', b'%PDF-1.4\n%test\n', content_type='application/pdf')

        self.client.post(
            reverse('validation_reopen', args=[student.student_number]),
            {'registration_proof': upload},
        )

        student.refresh_from_db()
        self.assertEqual(student.approval_status, Profile.APPROVAL_PENDING)
        self.assertTrue(student.registration_proof)
        event = AuditEvent.objects.get(action='REOPEN_STUDENT_REGISTRATION')
        self.assertIn('document replaced', event.new_value)

    def test_open_rejected_is_refused(self):
        student = self._student('2026-9102')  # APPROVED, not rejected

        self.client.post(reverse('validation_reopen', args=[student.student_number]))

        student.refresh_from_db()
        self.assertEqual(student.approval_status, Profile.APPROVAL_APPROVED)
        self.assertFalse(AuditEvent.objects.filter(action='REOPEN_STUDENT_REGISTRATION').exists())

    def test_only_post_is_allowed(self):
        student = self._rejected('2026-9103')

        response = self.client.get(reverse('validation_reopen', args=[student.student_number]))

        self.assertEqual(response.status_code, 405)
