"""
# // ==============================================================================
# // KCC CLASSSTAMP - CHED 20% ABSENCE RADAR TESTS (T-01)
# // ==============================================================================
# // Covers:
# //   - classify_absence_rate band boundaries (SAFE <10, WATCH 10-19, CRITICAL >=20)
# //   - absence_radar_for_class band membership counts
# //   - absence_radar_for_students defaults (zero records -> SAFE / 0%)
# //   - EXCUSED records never count as unexcused absences
# //   - Teacher dashboard renders class radar chips
# //   - Live scanner roster carries per-student radar telemetry
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
from apps.core.views.helpers.absence_radar import (
    BAND_CRITICAL,
    BAND_SAFE,
    BAND_WATCH,
    absence_radar_for_class,
    absence_radar_for_students,
    classify_absence_rate,
)

User = get_user_model()


class AbsenceRateClassificationTests(TestCase):
    """Band boundaries per CHED policy: <10 Safe, 10-19.9 Watchlist, >=20 Critical."""

    def test_below_ten_is_safe(self):
        self.assertEqual(classify_absence_rate(0.0), BAND_SAFE)
        self.assertEqual(classify_absence_rate(9.9), BAND_SAFE)

    def test_ten_to_nineteen_is_watchlist(self):
        self.assertEqual(classify_absence_rate(10.0), BAND_WATCH)
        self.assertEqual(classify_absence_rate(19.9), BAND_WATCH)

    def test_twenty_and_above_is_critical(self):
        self.assertEqual(classify_absence_rate(20.0), BAND_CRITICAL)
        self.assertEqual(classify_absence_rate(55.5), BAND_CRITICAL)


class AbsenceRadarTests(TestCase):
    """Aggregated radar computation over attendance records."""

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

        self.teacher_user = User.objects.create_user(username='radar_teacher', password='Teacher!Pass123')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
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

        # 10 distinct concluded sessions on the same slot
        self.sessions = []
        for i in range(10):
            self.sessions.append(ClassSession.objects.create(
                slot=self.slot,
                session_date=today - timedelta(days=40 - i),
                status=ClassSession.STATUS_CLOSED,
            ))

        self.students = {}
        for idx, (username, number) in enumerate([
                ('radar_a', '2026-2001'),
                ('radar_b', '2026-2002'),
                ('radar_c', '2026-2003'),
                ('radar_d', '2026-2004'),
        ]):
            user = User.objects.create_user(
                username=username, password='Student!Pass123',
                first_name=f'Radar{idx}', last_name='Student',
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
            self.students[username] = profile

        # Student A: 1 unexcused absence of 10 records -> 10.0% WATCH
        for i, session in enumerate(self.sessions):
            AttendanceRecord.objects.create(
                session=session, student_profile=self.students['radar_a'],
                status=AttendanceRecord.STATUS_ABSENT if i == 0 else AttendanceRecord.STATUS_PRESENT,
                method=AttendanceRecord.METHOD_SYSTEM,
            )
        # Student B: 1 unexcused absence of 5 records -> 20.0% CRITICAL
        for session in self.sessions[:5]:
            AttendanceRecord.objects.create(
                session=session, student_profile=self.students['radar_b'],
                status=AttendanceRecord.STATUS_ABSENT if session == self.sessions[0] else AttendanceRecord.STATUS_PRESENT,
                method=AttendanceRecord.METHOD_SYSTEM,
            )
        # Student C: only EXCUSED + PRESENT records -> 0% SAFE
        AttendanceRecord.objects.create(
            session=self.sessions[0], student_profile=self.students['radar_c'],
            status=AttendanceRecord.STATUS_EXCUSED, method=AttendanceRecord.METHOD_MANUAL,
        )
        AttendanceRecord.objects.create(
            session=self.sessions[1], student_profile=self.students['radar_c'],
            status=AttendanceRecord.STATUS_PRESENT, method=AttendanceRecord.METHOD_SYSTEM,
        )
        # Student D: no records at all

    def test_class_radar_band_counts(self):
        counts = absence_radar_for_class(self.class_obj)
        self.assertEqual(counts[BAND_SAFE], 1)
        self.assertEqual(counts[BAND_WATCH], 1)
        self.assertEqual(counts[BAND_CRITICAL], 1)

    def test_per_student_radar_rates(self):
        radar = absence_radar_for_students(
            self.class_obj, [p.id for p in self.students.values()]
        )
        a = radar[self.students['radar_a'].id]
        self.assertEqual(a['absent'], 1)
        self.assertEqual(a['total'], 10)
        self.assertEqual(a['rate'], 10.0)
        self.assertEqual(a['band'], BAND_WATCH)

        b = radar[self.students['radar_b'].id]
        self.assertEqual(b['absent'], 1)
        self.assertEqual(b['total'], 5)
        self.assertEqual(b['rate'], 20.0)
        self.assertEqual(b['band'], BAND_CRITICAL)

        # EXCUSED is not an unexcused absence
        c = radar[self.students['radar_c'].id]
        self.assertEqual(c['absent'], 0)
        self.assertEqual(c['rate'], 0.0)
        self.assertEqual(c['band'], BAND_SAFE)

    def test_zero_records_defaults_to_safe(self):
        radar = absence_radar_for_students(self.class_obj, [self.students['radar_d'].id])
        entry = radar[self.students['radar_d'].id]
        self.assertEqual(entry, {'absent': 0, 'total': 0, 'rate': 0.0, 'band': BAND_SAFE})

    def test_radar_scoped_to_class(self):
        other_class = Class.objects.create(
            academic_year=self.academic_year,
            class_code='BSIT-1B',
            subject=self.subject,
            teacher_profile=self.teacher_profile,
            grace_minutes=10,
        )
        counts = absence_radar_for_class(other_class)
        self.assertEqual(counts, {BAND_SAFE: 0, BAND_WATCH: 0, BAND_CRITICAL: 0})


class AbsenceRadarViewTests(TestCase):
    """Radar telemetry renders on teacher dashboard and live scanner."""

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

        self.teacher_user = User.objects.create_user(username='view_teacher', password='Teacher!Pass123')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
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

        student_user = User.objects.create_user(
            username='view_student', password='Student!Pass123', first_name='Ana', last_name='Cruz',
        )
        self.student_profile = Profile.objects.create(
            user=student_user, role=Profile.ROLE_STUDENT, student_number='2026-3001',
            program=self.program, year_level=1,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='a' * 64,
        )
        Enrollment.objects.create(
            student_profile=self.student_profile, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

        # 5 closed sessions: 1 ABSENT + 4 PRESENT -> 20.0% CRITICAL
        closed_sessions = []
        for i in range(5):
            closed_sessions.append(ClassSession.objects.create(
                slot=self.slot, session_date=today - timedelta(days=30 - i),
                status=ClassSession.STATUS_CLOSED,
            ))
        for i, cs in enumerate(closed_sessions):
            AttendanceRecord.objects.create(
                session=cs, student_profile=self.student_profile,
                status=AttendanceRecord.STATUS_ABSENT if i == 0 else AttendanceRecord.STATUS_PRESENT,
                method=AttendanceRecord.METHOD_SYSTEM,
            )

        self.client.force_login(self.teacher_user)

    def test_teacher_dashboard_renders_radar_chip(self):
        res = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'FDA risk')
        self.assertContains(res, '1 FDA risk')

    def test_scanner_roster_carries_radar_telemetry(self):
        res = self.client.get(reverse('teacher_session_scan', args=[self.session.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'FDA risk')
        self.assertContains(res, '20.0%')
        self.assertContains(res, '1/5 meetings')
