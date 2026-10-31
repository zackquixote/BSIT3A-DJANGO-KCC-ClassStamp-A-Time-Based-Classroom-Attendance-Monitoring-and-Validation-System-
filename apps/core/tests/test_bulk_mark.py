"""
# // ==============================================================================
# // KCC CLASSSTAMP - BULK MARK ATTENDANCE TESTS
# // ==============================================================================
# // The "camera died" path: one request marks every enrolled student without a
# // stamp. Covers authorization, idempotency, and the audit trail.
# ==============================================================================
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
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


class BulkMarkAttendanceTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )

        self.teacher_user = User.objects.create_user(username='bulk_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.other_teacher = User.objects.create_user(username='bulk_other')
        Profile.objects.create(
            user=self.other_teacher, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1A',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            grace_minutes=10,
        )

        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.session = ClassSession.objects.create(
            slot=self.slot, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user,
            created_by=self.teacher_user,
        )

        self.students = [self._student(i) for i in range(3)]
        for profile in self.students:
            Enrollment.objects.create(
                student_profile=profile, class_obj=self.class_obj,
                status=Enrollment.STATUS_ACTIVE,
            )

        self.client.force_login(self.teacher_user)

    def _student(self, index):
        user = User.objects.create_user(username=f'bulk_student_{index}', first_name=f'Student{index}')
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=f'2026-50{index:02d}',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

    def _bulk(self, status='PRESENT', session=None):
        return self.client.post(
            reverse('teacher_session_bulk_mark', args=[(session or self.session).pk]),
            {'status': status},
        )

    def test_marks_every_unstamped_student(self):
        response = self._bulk()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['marked'], 3)
        self.assertEqual(
            AttendanceRecord.objects.filter(
                session=self.session, status=AttendanceRecord.STATUS_PRESENT,
                method=AttendanceRecord.METHOD_MANUAL,
            ).count(),
            3,
        )
        self.assertTrue(AuditEvent.objects.filter(action='BULK_MARK_ATTENDANCE').exists())

    def test_does_not_overwrite_existing_stamps(self):
        stamped = self.students[0]
        AttendanceRecord.objects.create(
            session=self.session, student_profile=stamped,
            status=AttendanceRecord.STATUS_LATE,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(), late_minutes=12,
        )

        response = self._bulk()

        self.assertEqual(response.json()['marked'], 2)
        record = AttendanceRecord.objects.get(session=self.session, student_profile=stamped)
        self.assertEqual(record.status, AttendanceRecord.STATUS_LATE)
        self.assertEqual(record.method, AttendanceRecord.METHOD_QR)

    def test_running_twice_marks_nothing_the_second_time(self):
        self._bulk()
        second = self._bulk()

        self.assertEqual(second.json()['marked'], 0)
        self.assertEqual(AttendanceRecord.objects.filter(session=self.session).count(), 3)

    def test_closed_session_is_refused(self):
        self.session.status = ClassSession.STATUS_CLOSED
        self.session.save(update_fields=['status'])

        response = self._bulk()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(AttendanceRecord.objects.filter(session=self.session).exists())

    def test_other_teacher_cannot_bulk_mark(self):
        self.client.force_login(self.other_teacher)

        response = self._bulk()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(AttendanceRecord.objects.filter(session=self.session).exists())

    def test_unsupported_status_is_rejected(self):
        response = self._bulk(status='ABSENT')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(AttendanceRecord.objects.filter(session=self.session).exists())
