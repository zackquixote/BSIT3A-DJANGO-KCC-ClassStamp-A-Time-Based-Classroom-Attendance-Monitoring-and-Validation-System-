"""
# // ==============================================================================
# // KCC CLASSSTAMP - LIVE IN-SESSION MATRIX TESTS (T-02)
# // ==============================================================================
# // Covers:
# //   - Roster JSON endpoint returns per-student statuses and aggregate counters
# //   - Endpoint authorization (assigned teacher OK, other teacher 403, anon 302)
# //   - Scanner page renders live matrix UI (counter line, grid view, toggle)
# // ==============================================================================
"""

from datetime import date, time

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


class LiveMatrixEndpointTests(TestCase):
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
        self.other_teacher_user = User.objects.create_user(username='other_teacher', password='Teacher!Pass123')
        self.other_teacher_profile = Profile.objects.create(
            user=self.other_teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )

        self.class_obj = Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile, grace_minutes=10,
        )

        today = timezone.localdate()
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.session = ClassSession.objects.create(
            slot=self.slot, session_date=today,
            status=ClassSession.STATUS_OPEN, opened_at=timezone.now(), opened_by=self.teacher_user,
        )

        self.students = []
        for idx, (username, number) in enumerate([
                ('mx_a', '2026-4001'),
                ('mx_b', '2026-4002'),
                ('mx_c', '2026-4003'),
                ('mx_d', '2026-4004'),
        ]):
            user = User.objects.create_user(
                username=username, password='Student!Pass123',
                first_name=f'Matrix{idx}', last_name='Student',
            )
            profile = Profile.objects.create(
                user=user, role=Profile.ROLE_STUDENT, student_number=number,
                program=self.program, year_level=1,
                approval_status=Profile.APPROVAL_APPROVED, qr_secret='a' * 64,
            )
            Enrollment.objects.create(
                student_profile=profile, class_obj=self.class_obj,
                status=Enrollment.STATUS_ACTIVE,
            )
            self.students.append(profile)

        # 1 PRESENT, 1 LATE, 1 EXCUSED, 1 no record (PENDING) -> rate 50.0%
        AttendanceRecord.objects.create(
            session=self.session, student_profile=self.students[0],
            status=AttendanceRecord.STATUS_PRESENT, method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
        )
        AttendanceRecord.objects.create(
            session=self.session, student_profile=self.students[1],
            status=AttendanceRecord.STATUS_LATE, method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(), late_minutes=5,
        )
        AttendanceRecord.objects.create(
            session=self.session, student_profile=self.students[2],
            status=AttendanceRecord.STATUS_EXCUSED, method=AttendanceRecord.METHOD_MANUAL,
        )

    def test_roster_endpoint_returns_counts_and_statuses(self):
        self.client.force_login(self.teacher_user)
        res = self.client.get(reverse('teacher_session_roster_json', args=[self.session.pk]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['is_open'], True)
        self.assertEqual(data['counts'], {
            'present': 1, 'late': 1, 'absent': 0, 'excused': 1,
            'pending': 1, 'total': 4, 'attendance_rate': 50.0,
        })
        self.assertEqual(len(data['students']), 4)
        statuses = {s['student_id']: s['status'] for s in data['students']}
        self.assertEqual(statuses[self.students[0].id], 'PRESENT')
        self.assertEqual(statuses[self.students[1].id], 'LATE')
        self.assertEqual(statuses[self.students[2].id], 'EXCUSED')
        self.assertEqual(statuses[self.students[3].id], 'PENDING')

    def test_roster_endpoint_forbidden_for_other_teacher(self):
        self.client.force_login(self.other_teacher_user)
        res = self.client.get(reverse('teacher_session_roster_json', args=[self.session.pk]))
        self.assertEqual(res.status_code, 403)

    def test_roster_endpoint_requires_login(self):
        res = self.client.get(reverse('teacher_session_roster_json', args=[self.session.pk]))
        self.assertEqual(res.status_code, 302)

    def test_scan_page_renders_live_matrix_ui(self):
        self.client.force_login(self.teacher_user)
        res = self.client.get(reverse('teacher_session_scan', args=[self.session.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="liveCounterLine"')
        self.assertContains(res, 'id="viewGridBtn"')
        self.assertContains(res, 'id="rosterGridView"')
        self.assertContains(res, 'id="counterExcused"')
        self.assertContains(res, '50.0%')
        for student in self.students:
            self.assertContains(res, f'roster-grid-{student.id}')
