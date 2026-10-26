"""
# // ==============================================================================
# // KCC CLASSSTAMP - ANOMALY / FRAUD DETECTION TESTS
# // ==============================================================================
# // Covers the automated detector rules wired into the attendance scan pipeline
# // and the adjudication workflow consequences:
# //   - token replay across sessions flags the original record
# //   - duplicate stamp attempts flag the existing record
#   - token brute-force storms raise session-level flags
#   - off-schedule stamps (before start / after end) are flagged
#   - rapid-scan proxy bursts are flagged
#   - post-close manual overrides are flagged
#   - adjudication decisions map to statuses and mutate records
# // ==============================================================================
"""

from datetime import datetime, time
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AnomalyFlag,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    Profile,
    Program,
    ReviewAction,
    Subject,
)
from apps.core.services.anomaly_service import (
    RULE_DUPLICATE_STAMP_ATTEMPT,
    RULE_POST_CLOSE_OVERRIDE,
    RULE_RAPID_SCAN_PROXY,
    RULE_STAMP_AFTER_CLASS_END,
    RULE_STAMP_BEFORE_CLASS_START,
    RULE_TOKEN_BRUTE_FORCE,
    RULE_TOKEN_REPLAY_ACROSS_SESSION,
    raise_flag,
)
from apps.core.services.qr_service import build_payload, current_token

User = get_user_model()


class AnomalyDetectionTests(TestCase):
    def setUp(self):
        cache.clear()

        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.academic_year = AcademicYear.objects.create(
            name='2025-2026', starts_on=timezone.localdate(), ends_on=timezone.localdate(),
            is_active=True,
        )

        self.teacher_user = User.objects.create_user(username='anom_teacher', password='Teacher!Pass123')
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
        self.slot_one = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.slot_two = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(10, 0), ends_at=time(11, 0), room='Room 2',
        )

        self.session_one = ClassSession.objects.create(
            slot=self.slot_one, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user, created_by=self.teacher_user,
        )
        self.session_two = ClassSession.objects.create(
            slot=self.slot_two, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user, created_by=self.teacher_user,
        )

        self.student_profile = self._make_student(0)

        self.client.force_login(self.teacher_user)

    def _make_student(self, index):
        user = User.objects.create_user(
            username=f'anom_student_{index}', password='Student!Pass123',
            first_name=f'Student{index}', last_name='Test',
        )
        profile = Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=f'2026-{1000 + index}',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
            qr_secret='a' * 64,
        )
        Enrollment.objects.create(
            student_profile=profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        return profile

    def _scan(self, session, token=None, payload=None, student_profile=None):
        target = student_profile or self.student_profile
        if payload is None:
            payload = build_payload(target, token or current_token(target))
        return self.client.post(reverse('attendance_scan_api'), {
            'session_id': session.pk,
            'qr_payload': payload,
        })

    # ── Detector rules ───────────────────────────────────────────────────

    def test_replay_across_sessions_flags_original_record(self):
        token = current_token(self.student_profile)

        self.assertEqual(self._scan(self.session_one, token=token).status_code, 200)
        replay = self._scan(self.session_two, token=token)

        self.assertEqual(replay.status_code, 400)
        flag = AnomalyFlag.objects.get(rule_code=RULE_TOKEN_REPLAY_ACROSS_SESSION)
        self.assertEqual(flag.attendance_record.session, self.session_one)
        self.assertEqual(flag.attendance_record.student_profile, self.student_profile)
        self.assertEqual(flag.session, self.session_one)
        self.assertEqual(flag.student_profile, self.student_profile)

    def test_duplicate_stamp_flags_existing_record(self):
        self.assertEqual(self._scan(self.session_one).status_code, 200)
        self.assertEqual(self._scan(self.session_one).status_code, 400)

        flag = AnomalyFlag.objects.get(rule_code=RULE_DUPLICATE_STAMP_ATTEMPT)
        self.assertEqual(flag.attendance_record.session, self.session_one)
        self.assertEqual(flag.attendance_record.student_profile, self.student_profile)

    def test_token_bruteforce_raises_session_level_flag(self):
        with mock.patch('apps.core.views.session_views.verify_token', return_value=False), \
                mock.patch('apps.core.views.session_views.token_details', return_value=None):
            for _ in range(5):
                self._scan(self.session_one, token='000000')

        flag = AnomalyFlag.objects.get(rule_code=RULE_TOKEN_BRUTE_FORCE)
        self.assertIsNone(flag.attendance_record)
        self.assertEqual(flag.session, self.session_one)
        self.assertEqual(flag.student_profile, self.student_profile)

    def test_stamp_after_class_end_is_flagged(self):
        today = timezone.localdate()
        fixed_now = timezone.make_aware(datetime.combine(today, time(12, 0)))
        with mock.patch('apps.core.views.session_views.timezone.now', return_value=fixed_now):
            response = self._scan(self.session_one)

        self.assertEqual(response.status_code, 200)
        AnomalyFlag.objects.get(rule_code=RULE_STAMP_AFTER_CLASS_END)

    def test_stamp_before_class_start_is_flagged(self):
        today = timezone.localdate()
        slot_future = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(14, 0), ends_at=time(15, 0), room='Room 3',
        )
        session_future = ClassSession.objects.create(
            slot=slot_future, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user, created_by=self.teacher_user,
        )
        fixed_now = timezone.make_aware(datetime.combine(today, time(10, 0)))
        with mock.patch('apps.core.views.session_views.timezone.now', return_value=fixed_now):
            response = self._scan(session_future)

        self.assertEqual(response.status_code, 200)
        AnomalyFlag.objects.get(rule_code=RULE_STAMP_BEFORE_CLASS_START)

    def test_rapid_scan_proxy_burst_is_flagged(self):
        students = [self._make_student(i) for i in range(1, 9)]
        for sp in students:
            response = self._scan(self.session_one, token=current_token(sp), student_profile=sp)
            self.assertEqual(response.status_code, 200)

        AnomalyFlag.objects.get(rule_code=RULE_RAPID_SCAN_PROXY)

    def test_post_close_override_is_flagged(self):
        close_response = self.client.post(
            reverse('teacher_session_close', args=[self.session_one.pk])
        )
        self.assertEqual(close_response.status_code, 302)

        override = self.client.post(
            reverse('teacher_manual_override_ajax', args=[self.session_one.pk]),
            {'student_id': self.student_profile.pk, 'status': 'EXCUSED', 'reason': 'Medical'},
        )
        self.assertEqual(override.status_code, 200)

        flag = AnomalyFlag.objects.get(rule_code=RULE_POST_CLOSE_OVERRIDE)
        self.assertEqual(flag.attendance_record.session, self.session_one)

    # ── Adjudication workflow ────────────────────────────────────────────

    def _make_open_flag(self):
        record = AttendanceRecord.objects.create(
            session=self.session_one,
            student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_PRESENT,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
            marked_by=self.teacher_user,
        )
        flag, _ = raise_flag(
            record=record,
            rule_code=RULE_DUPLICATE_STAMP_ATTEMPT,
            reason='Test flag',
            risk_score=0.35,
        )
        admin = User.objects.create_superuser('anom_admin', 'admin@test.com', 'Admin!Pass123')
        self.client.force_login(admin)
        return flag, record

    def test_adjudicate_excuse_maps_status_and_record_and_blocks_reopen(self):
        flag, record = self._make_open_flag()
        url = reverse('anomaly_adjudicate', args=[flag.pk])

        response = self.client.post(url, {'decision': 'EXCUSE', 'reason': 'Valid medical slip'})

        self.assertEqual(response.status_code, 302)
        flag.refresh_from_db()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_EXCUSED)
        record.refresh_from_db()
        self.assertEqual(record.status, AttendanceRecord.STATUS_EXCUSED)
        self.assertEqual(ReviewAction.objects.filter(anomaly_flag=flag).count(), 1)

        # Re-adjudication of a resolved flag is blocked
        self.client.post(url, {'decision': 'DISMISS', 'reason': 'second attempt'})
        flag.refresh_from_db()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_EXCUSED)
        self.assertEqual(ReviewAction.objects.filter(anomaly_flag=flag).count(), 1)

    def test_adjudicate_confirm_proxy_demotes_record(self):
        flag, record = self._make_open_flag()
        url = reverse('anomaly_adjudicate', args=[flag.pk])

        self.client.post(url, {'decision': 'CONFIRM_PROXY', 'reason': 'Verified proxy'})

        flag.refresh_from_db()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_CONFIRMED)
        record.refresh_from_db()
        self.assertEqual(record.status, AttendanceRecord.STATUS_ABSENT)

    def test_bulk_action_excuse_maps_to_excused(self):
        flag, record = self._make_open_flag()

        response = self.client.post(reverse('anomaly_bulk_action'), {
            'decision': 'EXCUSE',
            'ids[]': [flag.pk],
            'reason': 'Bulk excuse',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['new_status'], AnomalyFlag.STATUS_EXCUSED)
        flag.refresh_from_db()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_EXCUSED)
        record.refresh_from_db()
        self.assertEqual(record.status, AttendanceRecord.STATUS_EXCUSED)

    def test_anomaly_list_tolerates_invalid_status_filter(self):
        admin = User.objects.create_superuser('list_admin', 'list@test.com', 'Admin!Pass123')
        self.client.force_login(admin)

        response = self.client.get(reverse('anomaly_list'), {'status': 'BOGUS'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['status_filter'], AnomalyFlag.STATUS_OPEN)

    # ── Re-trigger policy & backfill command ─────────────────────────────

    def test_raise_flag_reopens_resolved_flag_on_retrigger(self):
        record = AttendanceRecord.objects.create(
            session=self.session_one,
            student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_PRESENT,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=timezone.now(),
            marked_by=self.teacher_user,
        )
        flag, created = raise_flag(
            record=record,
            rule_code=RULE_DUPLICATE_STAMP_ATTEMPT,
            reason='first trigger',
            risk_score=0.30,
        )
        self.assertTrue(created)
        flag.status = AnomalyFlag.STATUS_DISMISSED
        flag.resolved_at = timezone.now()
        flag.save(update_fields=['status', 'resolved_at'])

        flag2, created2 = raise_flag(
            record=record,
            rule_code=RULE_DUPLICATE_STAMP_ATTEMPT,
            reason='second trigger',
            risk_score=0.50,
        )

        self.assertFalse(created2)
        flag2.refresh_from_db()
        self.assertEqual(flag2.status, AnomalyFlag.STATUS_OPEN)
        self.assertIsNone(flag2.resolved_at)
        self.assertIn('Re-triggered', flag2.reason)
        self.assertEqual(flag2.risk_score, 0.50)
        self.assertTrue(AuditEvent.objects.filter(action='ANOMALY_REOPENED').exists())

    def _create_late_qr_record(self):
        today = timezone.localdate()
        late_stamp = timezone.make_aware(datetime.combine(today, time(12, 0)))
        return AttendanceRecord.objects.create(
            session=self.session_one,
            student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_LATE,
            method=AttendanceRecord.METHOD_QR,
            stamped_at=late_stamp,
            late_minutes=180,
            marked_by=self.teacher_user,
        )

    def test_backfill_creates_flags_and_is_idempotent(self):
        self._create_late_qr_record()

        call_command('backfill_anomalies', stdout=StringIO())

        flag = AnomalyFlag.objects.get(rule_code=RULE_STAMP_AFTER_CLASS_END)
        self.assertIsNotNone(flag.attendance_record)

        before = AnomalyFlag.objects.count()
        call_command('backfill_anomalies', stdout=StringIO())
        self.assertEqual(AnomalyFlag.objects.count(), before)

    def test_backfill_dry_run_writes_nothing(self):
        self._create_late_qr_record()

        out = StringIO()
        call_command('backfill_anomalies', '--dry-run', stdout=out)

        self.assertFalse(
            AnomalyFlag.objects.filter(rule_code=RULE_STAMP_AFTER_CLASS_END).exists()
        )
        self.assertIn('would create', out.getvalue())

    def test_backfill_reopens_resolved_flag(self):
        record = self._create_late_qr_record()
        flag, _ = raise_flag(
            record=record,
            rule_code=RULE_STAMP_AFTER_CLASS_END,
            reason='old evidence',
            risk_score=0.55,
        )
        flag.status = AnomalyFlag.STATUS_DISMISSED
        flag.resolved_at = timezone.now()
        flag.save(update_fields=['status', 'resolved_at'])

        call_command('backfill_anomalies', stdout=StringIO())

        flag.refresh_from_db()
        self.assertEqual(flag.status, AnomalyFlag.STATUS_OPEN)
        self.assertIsNone(flag.resolved_at)
