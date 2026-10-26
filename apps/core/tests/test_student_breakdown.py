"""
# // ==============================================================================
# // KCC CLASSSTAMP - PER-SUBJECT ATTENDANCE BREAKDOWN TESTS (S-03)
# // ==============================================================================
# // Covers:
# //   - Student dashboard renders one breakdown card per enrolled class
# //   - Per-class Present/Late/Absent/Excused counts and compliance %
# //   - Expandable meeting-by-meeting log
# //   - Classes with no records yet show "No meetings yet"
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


class StudentBreakdownTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31), is_active=True,
        )
        self.subject_a = Subject.objects.create(code='IT101', name='Intro to Computing')
        self.subject_b = Subject.objects.create(code='IT202', name='Data Structures')
        self.subject_c = Subject.objects.create(code='IT303', name='Networking')

        self.teacher_user = User.objects.create_user(
            username='bk_teacher', password='Teacher!Pass123', first_name='Juan', last_name='Dela Cruz',
        )
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.student_user = User.objects.create_user(
            username='bk_student', password='Student!Pass123', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT, student_number='2026-6001',
            program=self.program, year_level=1,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='a' * 64,
        )

        today = timezone.localdate()
        self.class_a = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1A',
            subject=self.subject_a, teacher_profile=self.teacher_profile, grace_minutes=10,
        )
        self.class_b = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1B',
            subject=self.subject_b, teacher_profile=self.teacher_profile, grace_minutes=10,
        )
        self.class_c = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1C',
            subject=self.subject_c, teacher_profile=self.teacher_profile, grace_minutes=10,
        )
        for class_obj in (self.class_a, self.class_b, self.class_c):
            Enrollment.objects.create(
                student_profile=self.student_profile, class_obj=class_obj,
                status=Enrollment.STATUS_ACTIVE,
            )

        # Class A: 4 meetings -> 2 PRESENT, 1 LATE, 1 ABSENT -> compliance 75.0%
        # Class B: 1 meeting -> 1 PRESENT -> compliance 100.0%
        # Class C: no meetings
        for class_obj, specs in [
                (self.class_a, ['PRESENT', 'PRESENT', 'LATE', 'ABSENT']),
                (self.class_b, ['PRESENT']),
        ]:
            slot = ClassSlot.objects.create(
                class_obj=class_obj, weekday=today.weekday(),
                starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
            )
            for i, status in enumerate(specs):
                session = ClassSession.objects.create(
                    slot=slot, session_date=today - timedelta(days=30 - i),
                    status=ClassSession.STATUS_CLOSED,
                )
                AttendanceRecord.objects.create(
                    session=session, student_profile=self.student_profile,
                    status=status,
                    method=AttendanceRecord.METHOD_SYSTEM,
                    stamped_at=timezone.now() - timedelta(days=30 - i),
                    late_minutes=7 if status == 'LATE' else 0,
                )

        self.client.force_login(self.student_user)

    def test_dashboard_renders_breakdown_cards(self):
        res = self.client.get(reverse('student_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'IT101')
        self.assertContains(res, 'IT202')
        self.assertContains(res, 'IT303')
        self.assertContains(res, 'Juan Dela Cruz')
        self.assertContains(res, '75.0%')
        self.assertContains(res, '100.0%')
        self.assertContains(res, 'No meetings yet')
        self.assertContains(res, 'Meeting log')

    def test_meeting_log_lists_records(self):
        res = self.client.get(reverse('student_dashboard'))
        self.assertContains(res, 'Meeting log (4)')
        self.assertContains(res, 'Meeting log (1)')
        self.assertContains(res, 'Late +7m')
