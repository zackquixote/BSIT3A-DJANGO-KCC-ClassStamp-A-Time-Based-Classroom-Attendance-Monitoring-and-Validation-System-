"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT PORTAL ADDITIONS TESTS
# // ==============================================================================
# // Covers the three new student capabilities:
# //   - a printable term record
# //   - a date range on the attendance log
# //   - disputing a recorded status, and the instructor's uphold/correct reply
# ==============================================================================
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceDispute,
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


class StudentPortalBase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(
            username='sp_teacher', first_name='Glenn', last_name='Azuelo',
        )
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3A-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
        )
        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.student_user = User.objects.create_user(
            username='sp_student', first_name='Ana', last_name='Cruz',
        )
        self.student = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-7700',
            program=self.program,
            year_level=3,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        Enrollment.objects.create(
            student_profile=self.student, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.client.force_login(self.student_user)

    def _record(self, days_ago, status=AttendanceRecord.STATUS_PRESENT):
        session = ClassSession.objects.create(
            slot=self.slot,
            session_date=timezone.localdate() - timedelta(days=days_ago),
            status=ClassSession.STATUS_CLOSED,
        )
        return AttendanceRecord.objects.create(
            session=session,
            student_profile=self.student,
            status=status,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
        )


class TermRecordTests(StudentPortalBase):
    def test_record_page_shows_subject_and_totals(self):
        self._record(2, AttendanceRecord.STATUS_PRESENT)
        self._record(1, AttendanceRecord.STATUS_ABSENT)

        response = self.client.get(reverse('student_term_record'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 1)
        self.assertEqual(response.context['totals']['meetings'], 2)
        self.assertEqual(response.context['totals']['present'], 1)
        self.assertEqual(response.context['totals']['absent'], 1)
        self.assertEqual(response.context['overall'], 50.0)
        self.assertContains(response, 'Print / Save as PDF')

    def test_record_page_without_enrolments_is_empty_but_valid(self):
        Enrollment.objects.all().delete()

        response = self.client.get(reverse('student_term_record'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['rows'], [])


class AttendanceDateRangeTests(StudentPortalBase):
    def test_range_narrows_the_log(self):
        old = self._record(30, AttendanceRecord.STATUS_ABSENT)
        recent = self._record(1, AttendanceRecord.STATUS_PRESENT)

        response = self.client.get(reverse('student_attendance_log'), {
            'from': (timezone.localdate() - timedelta(days=5)).isoformat(),
            'to': timezone.localdate().isoformat(),
        })

        ids = [r.pk for r in response.context['records']]
        self.assertIn(recent.pk, ids)
        self.assertNotIn(old.pk, ids)

    def test_reversed_range_is_normalised(self):
        self._record(1, AttendanceRecord.STATUS_PRESENT)

        response = self.client.get(reverse('student_attendance_log'), {
            'from': timezone.localdate().isoformat(),
            'to': (timezone.localdate() - timedelta(days=5)).isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['records']), 1)


class StudentDisputeTests(StudentPortalBase):
    def _file(self, record, reason='I scanned at 7:55 but it shows absent'):
        return self.client.post(reverse('student_dispute_open'), {
            'record_id': record.pk,
            'reason': reason,
        })

    def test_student_can_file_a_dispute(self):
        record = self._record(1, AttendanceRecord.STATUS_ABSENT)

        response = self._file(record)

        self.assertEqual(response.status_code, 302)
        dispute = AttendanceDispute.objects.get(record=record)
        self.assertEqual(dispute.status, AttendanceDispute.STATUS_PENDING)
        self.assertTrue(AuditEvent.objects.filter(action='ATTENDANCE_DISPUTE_FILED').exists())

    def test_short_reason_is_rejected(self):
        record = self._record(1, AttendanceRecord.STATUS_ABSENT)

        self._file(record, reason='wrong')

        self.assertFalse(AttendanceDispute.objects.exists())

    def test_cannot_dispute_someone_elses_record(self):
        other_user = User.objects.create_user(username='sp_other')
        other = Profile.objects.create(
            user=other_user, role=Profile.ROLE_STUDENT, student_number='2026-7701',
            program=self.program, approval_status=Profile.APPROVAL_APPROVED,
        )
        foreign = AttendanceRecord.objects.create(
            session=ClassSession.objects.create(
                slot=self.slot, session_date=timezone.localdate() - timedelta(days=1),
                status=ClassSession.STATUS_CLOSED,
            ),
            student_profile=other,
            status=AttendanceRecord.STATUS_ABSENT,
            method=AttendanceRecord.METHOD_SYSTEM,
        )

        self._file(foreign)

        self.assertFalse(AttendanceDispute.objects.exists())

    def test_excused_record_cannot_be_disputed(self):
        record = self._record(1, AttendanceRecord.STATUS_EXCUSED)

        self._file(record)

        self.assertFalse(AttendanceDispute.objects.exists())

    def test_duplicate_dispute_is_refused(self):
        record = self._record(1, AttendanceRecord.STATUS_ABSENT)
        self._file(record)

        self._file(record, reason='Filing the exact same complaint twice')

        self.assertEqual(AttendanceDispute.objects.filter(record=record).count(), 1)


class DisputeResolutionTests(StudentPortalBase):
    def setUp(self):
        super().setUp()
        self.record = self._record(1, AttendanceRecord.STATUS_ABSENT)
        self.dispute = AttendanceDispute.objects.create(
            record=self.record, student_profile=self.student, reason='I was present at 7:55',
        )

    def _resolve(self, action, status=None, note='Checked the camera log'):
        payload = {'action': action, 'note': note}
        if status:
            payload['status'] = status
        return self.client.post(reverse('dispute_resolve', args=[self.dispute.pk]), payload)

    def test_teacher_can_uphold(self):
        self.client.force_login(self.teacher_user)

        response = self._resolve('uphold')

        self.assertEqual(response.status_code, 302)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, AttendanceDispute.STATUS_UPHELD)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, AttendanceRecord.STATUS_ABSENT)
        self.assertTrue(AuditEvent.objects.filter(action='ATTENDANCE_DISPUTE_RESOLVED').exists())

    def test_teacher_can_correct_the_record(self):
        self.client.force_login(self.teacher_user)

        self._resolve('correct', status='PRESENT')

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, AttendanceRecord.STATUS_PRESENT)
        self.assertEqual(self.record.method, AttendanceRecord.METHOD_MANUAL)
        self.assertIn('Dispute #', self.record.correction_reason)

        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, AttendanceDispute.STATUS_CORRECTED)
        self.assertEqual(self.dispute.resolved_by, self.teacher_user)

    def test_resolved_dispute_cannot_be_resolved_again(self):
        self.client.force_login(self.teacher_user)
        self._resolve('uphold')

        self._resolve('correct', status='PRESENT')

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, AttendanceRecord.STATUS_ABSENT)

    def test_other_teacher_cannot_resolve(self):
        other_user = User.objects.create_user(username='sp_teacher_b')
        Profile.objects.create(
            user=other_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.client.force_login(other_user)

        self._resolve('correct', status='PRESENT')

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, AttendanceRecord.STATUS_ABSENT)
        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, AttendanceDispute.STATUS_PENDING)

    def test_pending_dispute_appears_in_the_teacher_queue(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('teacher_excuse_slips'))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.dispute, list(response.context['pending_disputes']))
