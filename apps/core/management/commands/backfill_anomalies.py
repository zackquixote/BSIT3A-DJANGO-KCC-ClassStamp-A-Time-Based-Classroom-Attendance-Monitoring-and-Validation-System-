"""
// ==============================================================================
// KCC CLASSSTAMP - ANOMALY BACKFILL MANAGEMENT COMMAND
// ==============================================================================
// Usage: python manage.py backfill_anomalies [--dry-run] [--since YYYY-MM-DD]
//        [--session-id N] [--rules RULE_A,RULE_B] [--no-reopen]
// Description: Replays the deterministic fraud detectors over historical
//   attendance data so the Anomalies review panel reflects past sessions, not
//   just scans that happened after detection went live. Idempotent via
//   raise_flag uniqueness; re-opens resolved flags on re-trigger unless
//   --no-reopen is passed.
// ==============================================================================
"""

from collections import deque
from datetime import datetime
from unittest import mock

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.core.models import (
    AnomalyFlag,
    AttendanceRecord,
    AuditEvent,
    ClassSession,
    StampAttempt,
)
from apps.core.services import anomaly_service
from apps.core.services.anomaly_service import (
    BRUTE_FORCE_MIN_ATTEMPTS,
    BRUTE_FORCE_WINDOW_MINUTES,
    RAPID_SCAN_MIN_DISTINCT_STUDENTS,
    RAPID_SCAN_WINDOW_SECONDS,
    RULE_DUPLICATE_STAMP_ATTEMPT,
    RULE_POST_CLOSE_OVERRIDE,
    RULE_RAPID_SCAN_PROXY,
    RULE_SCHEDULE_CONFLICT,
    RULE_STAMP_AFTER_CLASS_END,
    RULE_STAMP_BEFORE_CLASS_START,
    RULE_TOKEN_BRUTE_FORCE,
)

ALL_RULES = [
    RULE_STAMP_AFTER_CLASS_END,
    RULE_STAMP_BEFORE_CLASS_START,
    RULE_DUPLICATE_STAMP_ATTEMPT,
    RULE_RAPID_SCAN_PROXY,
    RULE_SCHEDULE_CONFLICT,
    RULE_POST_CLOSE_OVERRIDE,
    RULE_TOKEN_BRUTE_FORCE,
]


class Command(BaseCommand):
    help = 'Replays fraud detectors over historical attendance data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report would-be flags without writing anything',
        )
        parser.add_argument(
            '--since',
            type=str,
            default='',
            help='Only sessions on or after this date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--session-id',
            type=int,
            default=None,
            help='Restrict the backfill to a single session',
        )
        parser.add_argument(
            '--rules',
            type=str,
            default='',
            help='Comma-separated rule subset to run (default: all)',
        )
        parser.add_argument(
            '--no-reopen',
            action='store_true',
            help='Do not re-open flags that were already resolved',
        )

    def handle(self, *args, **options):
        since = None
        if options['since']:
            try:
                since = datetime.strptime(options['since'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('--since must be formatted YYYY-MM-DD')

        selected = ALL_RULES
        if options['rules']:
            selected = [r.strip() for r in options['rules'].split(',') if r.strip()]
            unknown = [r for r in selected if r not in ALL_RULES]
            if unknown:
                raise CommandError(f'Unknown rule code(s): {", ".join(unknown)}')

        if options['session_id']:
            self.stdout.write(f"[BACKFILL] Scope: session #{options['session_id']}")
        elif since:
            self.stdout.write(f'[BACKFILL] Scope: sessions since {since}')
        else:
            self.stdout.write('[BACKFILL] Scope: all sessions')

        included = set(selected)

        if options['dry_run']:
            stats = {rule: {'created': 0, 'reopened': 0} for rule in ALL_RULES}
            with mock.patch.object(anomaly_service, 'raise_flag', self._dry_run_raise(stats)):
                self._run_detectors(since, options['session_id'], included)
            self._report(stats, dry_run=True)
            return

        flags_before = self._flag_totals()
        reopens_before = AuditEvent.objects.filter(action='ANOMALY_REOPENED').count()

        if options['no_reopen']:
            original = anomaly_service.raise_flag

            def no_reopen_raise(**kwargs):
                kwargs['reopen'] = False
                return original(**kwargs)

            with mock.patch.object(anomaly_service, 'raise_flag', no_reopen_raise):
                self._run_detectors(since, options['session_id'], included)
        else:
            self._run_detectors(since, options['session_id'], included)

        flags_after = self._flag_totals()
        reopens_after = AuditEvent.objects.filter(action='ANOMALY_REOPENED').count()

        stats = {rule: {'created': 0, 'reopened': 0} for rule in ALL_RULES}
        for rule in selected:
            stats[rule]['created'] = max(0, flags_after.get(rule, 0) - flags_before.get(rule, 0))
        reopened_total = max(0, reopens_after - reopens_before)

        self._report(stats, dry_run=False, reopened_total=reopened_total)

    # ── Detector replay loops ────────────────────────────────────────────

    def _run_detectors(self, since, session_id, included):
        # Off-window and schedule-conflict share the QR record stream
        if (
            RULE_STAMP_AFTER_CLASS_END in included
            or RULE_STAMP_BEFORE_CLASS_START in included
            or RULE_SCHEDULE_CONFLICT in included
        ):
            qr_records = (
                AttendanceRecord.objects
                .filter(method=AttendanceRecord.METHOD_QR, stamped_at__isnull=False)
                .select_related('session__slot', 'student_profile')
            )
            if since:
                qr_records = qr_records.filter(session__session_date__gte=since)
            if session_id:
                qr_records = qr_records.filter(session_id=session_id)
            for record in qr_records.iterator():
                if RULE_STAMP_AFTER_CLASS_END in included or RULE_STAMP_BEFORE_CLASS_START in included:
                    anomaly_service.detect_off_window(record, record.session, now=record.stamped_at)
                if RULE_SCHEDULE_CONFLICT in included:
                    anomaly_service.detect_schedule_conflict(record, record.student_profile, record.session)

        if RULE_DUPLICATE_STAMP_ATTEMPT in included:
            duplicate_pairs = (
                StampAttempt.objects
                .filter(outcome=StampAttempt.OUTCOME_DUPLICATE, student_profile__isnull=False)
                .values_list('session_id', 'student_profile_id')
                .distinct()
            )
            if since:
                duplicate_pairs = duplicate_pairs.filter(session__session_date__gte=since)
            if session_id:
                duplicate_pairs = duplicate_pairs.filter(session_id=session_id)
            for sid, pid in duplicate_pairs:
                record = AttendanceRecord.objects.filter(session_id=sid, student_profile_id=pid).first()
                if record:
                    anomaly_service.detect_duplicate_stamp(record)

        if RULE_POST_CLOSE_OVERRIDE in included:
            manual_records = (
                AttendanceRecord.objects
                .filter(
                    method=AttendanceRecord.METHOD_MANUAL,
                    session__status=ClassSession.STATUS_CLOSED,
                )
                .select_related('session')
            )
            if since:
                manual_records = manual_records.filter(session__session_date__gte=since)
            if session_id:
                manual_records = manual_records.filter(session_id=session_id)
            for record in manual_records.iterator():
                if record.session.closed_at and record.updated_at > record.session.closed_at:
                    anomaly_service.detect_post_close_override(record, record.session)

        if RULE_RAPID_SCAN_PROXY in included:
            self._backfill_rapid_scan(since, session_id)

        if RULE_TOKEN_BRUTE_FORCE in included:
            self._backfill_bruteforce(since, session_id)

    def _backfill_rapid_scan(self, since, session_id):
        attempts = (
            StampAttempt.objects
            .filter(
                outcome=StampAttempt.OUTCOME_ACCEPTED,
                student_profile__isnull=False,
                scanned_by__isnull=False,
            )
            .select_related('session', 'scanned_by')
            .order_by('session_id', 'scanned_by_id', 'attempted_at')
        )
        if since:
            attempts = attempts.filter(session__session_date__gte=since)
        if session_id:
            attempts = attempts.filter(session_id=session_id)

        current_key = None
        window = deque()
        for attempt in attempts.iterator():
            key = (attempt.session_id, attempt.scanned_by_id)
            if key != current_key:
                current_key = key
                window.clear()
            window.append((attempt.attempted_at, attempt.student_profile_id))
            while window and (attempt.attempted_at - window[0][0]).total_seconds() > RAPID_SCAN_WINDOW_SECONDS:
                window.popleft()
            distinct = {pid for _, pid in window}
            if len(distinct) >= RAPID_SCAN_MIN_DISTINCT_STUDENTS:
                anomaly_service.detect_rapid_scan(
                    attempt.session, attempt.scanned_by, now=attempt.attempted_at
                )
                window.clear()

    def _backfill_bruteforce(self, since, session_id):
        attempts = (
            StampAttempt.objects
            .filter(
                outcome__in=[StampAttempt.OUTCOME_EXPIRED, StampAttempt.OUTCOME_INVALID],
                student_profile__isnull=False,
            )
            .select_related('session', 'student_profile')
            .order_by('session_id', 'student_profile_id', 'attempted_at')
        )
        if since:
            attempts = attempts.filter(session__session_date__gte=since)
        if session_id:
            attempts = attempts.filter(session_id=session_id)

        current_key = None
        window = deque()
        for attempt in attempts.iterator():
            key = (attempt.session_id, attempt.student_profile_id)
            if key != current_key:
                current_key = key
                window.clear()
            window.append(attempt.attempted_at)
            while window and (attempt.attempted_at - window[0]).total_seconds() > BRUTE_FORCE_WINDOW_MINUTES * 60:
                window.popleft()
            if len(window) >= BRUTE_FORCE_MIN_ATTEMPTS:
                anomaly_service.detect_token_bruteforce(
                    attempt.session, attempt.student_profile, now=attempt.attempted_at
                )
                window.clear()

    # ── Reporting helpers ────────────────────────────────────────────────

    def _flag_totals(self):
        return dict(
            AnomalyFlag.objects.values('rule_code')
            .annotate(total=Count('id'))
            .values_list('rule_code', 'total')
        )

    def _dry_run_raise(self, stats):
        def fake_raise(**kwargs):
            code = kwargs.get('rule_code')
            record = kwargs.get('record')
            session = kwargs.get('session')
            student = kwargs.get('student_profile')
            if record is not None:
                exists = AnomalyFlag.objects.filter(
                    attendance_record=record, rule_code=code
                ).exists()
            else:
                exists = AnomalyFlag.objects.filter(
                    attendance_record__isnull=True,
                    session=session,
                    student_profile=student,
                    rule_code=code,
                ).exists()
            bucket = stats.get(code)
            if bucket is not None:
                if exists:
                    bucket['reopened'] += 1
                else:
                    bucket['created'] += 1
            return None, not exists
        return fake_raise

    def _report(self, stats, dry_run, reopened_total=0):
        self.stdout.write('')
        self.stdout.write('[BACKFILL] Per-rule summary:')
        created_total = 0
        dry_reopened_total = 0
        for rule, bucket in stats.items():
            created = bucket['created']
            reopened = bucket['reopened']
            if created or reopened:
                verb = 'would create' if dry_run else 'created'
                self.stdout.write(f'  {rule}: {created} {verb}, {reopened} re-opened')
            created_total += created
            dry_reopened_total += reopened
        if not dry_run:
            dry_reopened_total = reopened_total
        self.stdout.write(
            self.style.SUCCESS(
                f'[BACKFILL] {created_total} flag(s) raised, {dry_reopened_total} re-opened.'
            )
        )
