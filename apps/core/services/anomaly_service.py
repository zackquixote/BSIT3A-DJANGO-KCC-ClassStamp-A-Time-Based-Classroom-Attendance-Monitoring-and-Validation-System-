"""
// ==============================================================================
// KCC CLASSSTAMP - ATTENDANCE ANOMALY / FRAUD DETECTION SERVICE
// ==============================================================================
// Subsystem: Security Intelligence & Fraud Detection
// Description: Raises immutable AnomalyFlag records from scan-time signals.
//   Detectors are invoked by the attendance scan pipeline and the manual
//   override controller. All detectors are idempotent (unique per
//   attendance_record + rule_code, or per session + student + rule_code for
//   session-level rules) and must be called fail-open so detection errors
//   never break the attendance flow.
// References: apps/core/models/audit.py | docs/02_SECURITY.md
// ==============================================================================
"""

import logging
from datetime import datetime, timedelta

from django.utils import timezone

from apps.core.models import (
    AnomalyFlag,
    AttendanceRecord,
    AuditEvent,
    ClassSession,
    ClassSlot,
    Enrollment,
    StampAttempt,
)

logger = logging.getLogger(__name__)


# // ==============================================================================
# // RULE MNEMONICS
# // ==============================================================================
RULE_TOKEN_REPLAY_ACROSS_SESSION = 'RULE_TOKEN_REPLAY_ACROSS_SESSION'
RULE_DUPLICATE_STAMP_ATTEMPT = 'RULE_DUPLICATE_STAMP_ATTEMPT'
RULE_RAPID_SCAN_PROXY = 'RULE_RAPID_SCAN_PROXY'
RULE_STAMP_AFTER_CLASS_END = 'RULE_STAMP_AFTER_CLASS_END'
RULE_STAMP_BEFORE_CLASS_START = 'RULE_STAMP_BEFORE_CLASS_START'
RULE_SCHEDULE_CONFLICT = 'RULE_SCHEDULE_CONFLICT'
RULE_TOKEN_BRUTE_FORCE = 'RULE_TOKEN_BRUTE_FORCE'
RULE_POST_CLOSE_OVERRIDE = 'RULE_POST_CLOSE_OVERRIDE'

# // ==============================================================================
# // DETECTOR TUNING CONSTANTS
# // ==============================================================================
RAPID_SCAN_WINDOW_SECONDS = 120
RAPID_SCAN_MIN_DISTINCT_STUDENTS = 8
AFTER_CLASS_END_TOLERANCE_MINUTES = 45
BEFORE_CLASS_START_TOLERANCE_MINUTES = 30
BRUTE_FORCE_WINDOW_MINUTES = 10
BRUTE_FORCE_MIN_ATTEMPTS = 5


# // ==============================================================================
# // CORE: IDEMPOTENT FLAG RAISING
# // ==============================================================================
def raise_flag(*, record=None, session=None, student_profile=None,
               rule_code=None, reason='', risk_score=None, reopen=True):
    """
    // [Service] Idempotently create an AnomalyFlag.
    // Record-anchored rules key on (attendance_record, rule_code) via the model
    // unique_together. Session-level rules (no accepted record, e.g. brute force)
    // key on (session, student_profile, rule_code, attendance_record IS NULL).
    // Re-trigger policy: when an existing RESOLVED flag fires again, it is
    // re-opened (status OPEN, resolved_at cleared, reason appended, risk raised
    // to the stronger score) and an AuditEvent is emitted — a dismissed or
    // adjudicated flag does not silently swallow repeat offenses.
    // Returns (flag, created).
    """
    if record is not None:
        session = session or record.session
        student_profile = student_profile or record.student_profile
        flag, created = AnomalyFlag.objects.get_or_create(
            attendance_record=record,
            rule_code=rule_code,
            defaults={
                'session': session,
                'student_profile': student_profile,
                'reason': reason,
                'risk_score': risk_score,
            },
        )
    else:
        flag, created = AnomalyFlag.objects.get_or_create(
            attendance_record=None,
            session=session,
            student_profile=student_profile,
            rule_code=rule_code,
            defaults={'reason': reason, 'risk_score': risk_score},
        )

    if (
        not created
        and reopen
        and flag.status != AnomalyFlag.STATUS_OPEN
    ):
        flag.status = AnomalyFlag.STATUS_OPEN
        flag.resolved_at = None
        flag.reason = (
            f"{flag.reason}\n"
            f"[Re-triggered {timezone.now().strftime('%Y-%m-%d %H:%M')}] {reason}"
        )
        if risk_score is not None and (flag.risk_score is None or risk_score > flag.risk_score):
            flag.risk_score = risk_score
        flag.save(update_fields=['status', 'resolved_at', 'reason', 'risk_score'])
        AuditEvent.objects.create(
            actor=None,
            action='ANOMALY_REOPENED',
            object_type='AnomalyFlag',
            object_id=str(flag.id),
            old_value='RESOLVED',
            new_value=AnomalyFlag.STATUS_OPEN,
            reason=f'{rule_code}: {reason}',
        )
        logger.info('Re-opened anomaly flag #%s (%s) on rule re-trigger', flag.id, rule_code)

    return flag, created


# // ==============================================================================
# // DETECTOR: Token Replay Across Sessions (proxy forwarding)
# // ==============================================================================
def detect_token_replay(*, original_session, student_profile, replay_session):
    """
    // A (student, token) pair already consumed in one session was re-presented
    // in another. The strongest proxy-sharing signal: a screenshot/forwarded QR
    // credential reaching a second classroom within the anti-replay TTL.
    // Anchors the flag on the ORIGINAL session's record.
    """
    if original_session is None or original_session.pk == replay_session.pk:
        return None
    record = AttendanceRecord.objects.filter(
        session=original_session,
        student_profile=student_profile,
    ).first()
    if record is None:
        return None
    reason = (
        f"Student's TOTP token was consumed in session #{original_session.id} and "
        f"re-presented in session #{replay_session.id} within the anti-replay window. "
        f"Indicates a forwarded or screenshotted QR credential (proxy sharing)."
    )
    return raise_flag(
        record=record,
        rule_code=RULE_TOKEN_REPLAY_ACROSS_SESSION,
        reason=reason,
        risk_score=0.8500,
    )


# // ==============================================================================
# // DETECTOR: Duplicate Stamp Attempt (buddy scanning)
# // ==============================================================================
def detect_duplicate_stamp(record):
    """
    // An already-stamped student presented another cryptographically valid token
    // in the same session — typically one device being scanned for classmates.
    """
    duplicate_attempts = StampAttempt.objects.filter(
        session=record.session,
        student_profile=record.student_profile,
        outcome=StampAttempt.OUTCOME_DUPLICATE,
    ).count()
    reason = (
        f"Student was already stamped {record.status} in this session yet presented "
        f"another valid TOTP token ({duplicate_attempts} duplicate attempt(s) logged). "
        f"Possible buddy-scanning with a shared device."
    )
    return raise_flag(
        record=record,
        rule_code=RULE_DUPLICATE_STAMP_ATTEMPT,
        reason=reason,
        risk_score=0.3500,
    )


# // ==============================================================================
# // DETECTOR: Rapid Scan Proxy Burst (one terminal, many students)
# // ==============================================================================
def detect_rapid_scan(session, scanned_by, now=None):
    """
    // One operator terminal ACCEPTED too many distinct students inside a short
    // window — physically implausible for individual in-person scanning and a
    // hallmark of one device checking in a proxy ring. DB-based (not cache) so
    // the signal survives multi-process deployments.
    """
    now = now or timezone.now()
    cutoff = now - timedelta(seconds=RAPID_SCAN_WINDOW_SECONDS)
    accepted = StampAttempt.objects.filter(
        session=session,
        scanned_by=scanned_by,
        outcome=StampAttempt.OUTCOME_ACCEPTED,
        attempted_at__gte=cutoff,
        student_profile__isnull=False,
    )
    distinct_students = accepted.values('student_profile').distinct().count()
    if distinct_students < RAPID_SCAN_MIN_DISTINCT_STUDENTS:
        return None
    last_attempt = accepted.order_by('-attempted_at').first()
    record = AttendanceRecord.objects.filter(
        session=session,
        student_profile=last_attempt.student_profile,
    ).first()
    if record is None:
        return None
    operator = scanned_by.get_username()
    reason = (
        f"Operator terminal '{operator}' stamped {distinct_students} distinct students "
        f"within {RAPID_SCAN_WINDOW_SECONDS}s in session #{session.id}. Suggests a single "
        f"device checking in multiple classmates (proxy ring)."
    )
    return raise_flag(
        record=record,
        rule_code=RULE_RAPID_SCAN_PROXY,
        reason=reason,
        risk_score=0.5000,
    )


# // ==============================================================================
# // DETECTOR: Off-Schedule Window Stamps
# // ==============================================================================
def detect_off_window(record, session, now=None):
    """
    // Stamps landing far outside the slot's scheduled bounds: the scan pipeline
    // enforces no end bound, so a session left OPEN can accept stamps hours after
    // class ended — or abnormally early if opened ahead of schedule.
    """
    now = now or timezone.now()
    slot = session.slot
    scheduled_start = timezone.make_aware(
        datetime.combine(session.session_date, slot.starts_at)
    )
    scheduled_end = timezone.make_aware(
        datetime.combine(session.session_date, slot.ends_at)
    )

    if now > scheduled_end + timedelta(minutes=AFTER_CLASS_END_TOLERANCE_MINUTES):
        minutes = int((now - scheduled_end).total_seconds() // 60)
        reason = (
            f"Stamped {minutes} min after scheduled class end ({slot.ends_at.strftime('%I:%M %p')}). "
            f"Session #{session.id} remained open far beyond the class window."
        )
        return raise_flag(
            record=record,
            rule_code=RULE_STAMP_AFTER_CLASS_END,
            reason=reason,
            risk_score=0.5500,
        )

    if now < scheduled_start - timedelta(minutes=BEFORE_CLASS_START_TOLERANCE_MINUTES):
        minutes = int((scheduled_start - now).total_seconds() // 60)
        reason = (
            f"Stamped {minutes} min before scheduled class start ({slot.starts_at.strftime('%I:%M %p')}). "
            f"Session #{session.id} was opened abnormally early."
        )
        return raise_flag(
            record=record,
            rule_code=RULE_STAMP_BEFORE_CLASS_START,
            reason=reason,
            risk_score=0.4500,
        )

    return None


# // ==============================================================================
# // DETECTOR: Overlapping Schedule Conflict
# // ==============================================================================
def detect_schedule_conflict(record, student_profile, session):
    """
    // The student is stamped in a session whose slot overlaps another class they
    // are actively enrolled in — they cannot legitimately be in both rooms.
    """
    slot = session.slot
    overlap = (
        ClassSlot.objects
        .filter(
            class_obj__enrollments__student_profile=student_profile,
            class_obj__enrollments__status=Enrollment.STATUS_ACTIVE,
            weekday=slot.weekday,
            is_active=True,
            starts_at__lt=slot.ends_at,
            ends_at__gt=slot.starts_at,
        )
        .exclude(pk=slot.pk)
        .select_related('class_obj')
        .first()
    )
    if overlap is None:
        return None
    reason = (
        f"Student is actively enrolled in overlapping class '{overlap.class_obj.class_code}' "
        f"({overlap.starts_at.strftime('%I:%M %p')} - {overlap.ends_at.strftime('%I:%M %p')}) "
        f"at the time of this stamp — schedule conflict."
    )
    return raise_flag(
        record=record,
        rule_code=RULE_SCHEDULE_CONFLICT,
        reason=reason,
        risk_score=0.4500,
    )


# // ==============================================================================
# // DETECTOR: Token Brute Force (guessing storm)
# // ==============================================================================
def detect_token_bruteforce(session, student_profile, now=None):
    """
    // Many failed cryptographic verifications against one student in a short
    // span — a token-guessing / brute-force pattern against the QR credential.
    // Session-level rule: no accepted AttendanceRecord is required.
    """
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=BRUTE_FORCE_WINDOW_MINUTES)
    failed = StampAttempt.objects.filter(
        session=session,
        student_profile=student_profile,
        outcome__in=[StampAttempt.OUTCOME_EXPIRED, StampAttempt.OUTCOME_INVALID],
        attempted_at__gte=cutoff,
    ).count()
    if failed < BRUTE_FORCE_MIN_ATTEMPTS:
        return None
    reason = (
        f"{failed} failed cryptographic verification attempts against this student's QR "
        f"credential within {BRUTE_FORCE_WINDOW_MINUTES} min in session #{session.id} — "
        f"token guessing / brute-force pattern."
    )
    return raise_flag(
        session=session,
        student_profile=student_profile,
        rule_code=RULE_TOKEN_BRUTE_FORCE,
        reason=reason,
        risk_score=0.7000,
    )


# // ==============================================================================
# // DETECTOR: Post-Close Manual Override
# // ==============================================================================
def detect_post_close_override(record, session):
    """
    // Instructor modified an attendance record after the session was CLOSED.
    // Post-hoc edits bypass the live scan validation entirely — a known
    // collusion vector.
    """
    if session.status != ClassSession.STATUS_CLOSED:
        return None
    closed_label = (
        session.closed_at.strftime('%I:%M %p') if session.closed_at else 'unknown time'
    )
    reason = (
        f"Attendance record modified by instructor after session #{session.id} was "
        f"closed ({closed_label}). Post-hoc edits bypass live validation."
    )
    return raise_flag(
        record=record,
        rule_code=RULE_POST_CLOSE_OVERRIDE,
        reason=reason,
        risk_score=0.6000,
    )
