"""
# // ==============================================================================
# // KCC CLASSSTAMP - ATTENDANCE SESSION & RECORD MODELS
# // ==============================================================================
# // Subsystem: Time-Based Attendance Engine
# // Description: Core attendance data layer:
# //   - ClassSession:      Daily concrete meeting instance of a ClassSlot.
# //                        Lifecycle: SCHEDULED → OPEN → CLOSED / CANCELED.
# //   - AttendanceRecord:  Finalized per-student status for a session
# //                        (PRESENT, LATE, ABSENT, EXCUSED).
# //   - StampAttempt:      Immutable audit log of every QR/code scan attempt
# //                        for anti-replay and fraud detection.
# // References: docs/02_SECURITY.md | docs/04_MODELS_REFERENCE.md § Attendance
# // ==============================================================================
"""

from django.conf import settings
from django.db import models

from .classroom import ClassSlot
from .profile import Profile


class ClassSession(models.Model):
    """
    // [Model] Daily Concrete Class Attendance Session
    // Instantiated on a specific calendar date against a ClassSlot schedule.
    // Lifecycle transitions:
    // SCHEDULED -> OPEN (scanning active) -> CLOSED (scanning concluded) / CANCELED
    """
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_CANCELED, 'Canceled'),
    ]

    slot = models.ForeignKey(
        ClassSlot,
        on_delete=models.RESTRICT,
        related_name='sessions',
        help_text="// Schedule slot template"
    )
    session_date = models.DateField(help_text="// Actual calendar date of meeting")
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    opened_at = models.DateTimeField(null=True, blank=True, help_text="// Timestamp when teacher opened session")
    closed_at = models.DateTimeField(null=True, blank=True, help_text="// Timestamp when session was terminated")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_sessions'
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='opened_sessions'
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='closed_sessions'
    )
    auto_closed = models.BooleanField(
        default=False,
        help_text="// True if session was terminated automatically at schedule end time"
    )
    cancellation_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_class_session'
        unique_together = [('slot', 'session_date')]
        ordering = ['-session_date']

    def __str__(self):
        return f'{self.slot.class_obj.class_code} - {self.session_date} ({self.status})'


class AttendanceRecord(models.Model):
    """
    // [Model] Confirmed Student Attendance Record
    // Captures the finalized status (PRESENT, LATE, ABSENT, EXCUSED) for a student in a session.
    """
    STATUS_PRESENT = 'PRESENT'
    STATUS_LATE = 'LATE'
    STATUS_ABSENT = 'ABSENT'
    STATUS_EXCUSED = 'EXCUSED'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Present'),
        (STATUS_LATE, 'Late'),
        (STATUS_ABSENT, 'Absent'),
        (STATUS_EXCUSED, 'Excused'),
    ]

    METHOD_QR = 'QR'
    METHOD_CODE = 'CODE'
    METHOD_MANUAL = 'MANUAL'
    METHOD_SYSTEM = 'SYSTEM'
    METHOD_CHOICES = [
        (METHOD_QR, 'QR Scan'),
        (METHOD_CODE, 'Code'),
        (METHOD_MANUAL, 'Manual'),
        (METHOD_SYSTEM, 'System'),
    ]

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.RESTRICT,
        related_name='attendance_records',
        help_text="// Target attendance meeting"
    )
    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.RESTRICT,
        related_name='attendance_records',
        help_text="// Student marked in session"
    )
    status = models.CharField(max_length=8, choices=STATUS_CHOICES)
    method = models.CharField(max_length=6, choices=METHOD_CHOICES, help_text="// Verification mechanism")
    stamped_at = models.DateTimeField(null=True, blank=True, help_text="// Exact timestamp of validation stamp")
    late_minutes = models.PositiveSmallIntegerField(
        default=0,
        help_text="// Minutes elapsed past scheduled start time and grace buffer"
    )
    correction_reason = models.TextField(
        null=True, blank=True,
        help_text="// Justification if marked or corrected manually by instructor"
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='marked_attendance_records',
        help_text="// Instructor or system agent who recorded attendance"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_attendance_record'
        unique_together = [('session', 'student_profile')]

    def __str__(self):
        return f'{self.student_profile} - {self.session} - {self.status}'


class StampAttempt(models.Model):
    """
    // [Model] Scan & Stamp Audit Log (Anti-Replay / Fraud Prevention)
    // Immutable log capturing every QR scan or code submission attempt regardless of outcome.
    // Crucial for anomaly detection and rate-limiting brute-force attempts.
    """
    METHOD_QR = 'QR'
    METHOD_CODE = 'CODE'
    METHOD_CHOICES = [
        (METHOD_QR, 'QR Scan'),
        (METHOD_CODE, 'Code'),
    ]

    OUTCOME_ACCEPTED = 'ACCEPTED'
    OUTCOME_INVALID = 'INVALID'
    OUTCOME_EXPIRED = 'EXPIRED'
    OUTCOME_DUPLICATE = 'DUPLICATE'
    OUTCOME_INELIGIBLE = 'INELIGIBLE'
    OUTCOME_SESSION_CLOSED = 'SESSION_CLOSED'
    OUTCOME_CHOICES = [
        (OUTCOME_ACCEPTED, 'Accepted'),
        (OUTCOME_INVALID, 'Invalid'),
        (OUTCOME_EXPIRED, 'Expired'),
        (OUTCOME_DUPLICATE, 'Duplicate'),
        (OUTCOME_INELIGIBLE, 'Ineligible'),
        (OUTCOME_SESSION_CLOSED, 'Session Closed'),
    ]

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts'
    )
    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts'
    )
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stamp_attempts',
        help_text="// Teacher terminal or camera scanning the badge"
    )
    attempted_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=4, choices=METHOD_CHOICES)
    outcome = models.CharField(max_length=14, choices=OUTCOME_CHOICES)
    token_bucket = models.BigIntegerField(
        null=True, blank=True,
        help_text="// 30-second TOTP step window interval identifier"
    )
    token_age_s = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="// Age in seconds of token relative to current wall clock"
    )

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_stamp_attempt'
        ordering = ['-attempted_at']

    def __str__(self):
        return f'{self.attempted_at} - {self.outcome}'


class OfflineBadge(models.Model):
    """
    // [Model] Server-Issued Single-Use Offline Attendance Badge (S-07)
    // A short-lived credential for students without network/data connectivity:
    // the badge renders a static QR that the teacher terminal can validate
    // without the student's live TOTP device. The raw token is never stored —
    // only its SHA-256 hash — and each badge can be consumed exactly once.
    """
    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='offline_badges',
        help_text="// Student account the badge belongs to"
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="// SHA-256 hex digest of the raw 64-hex bearer token"
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="// Hard expiry (default +48h)")
    consumed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="// Set when the badge is redeemed at a scanning terminal"
    )
    consumed_session = models.ForeignKey(
        ClassSession,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='offline_badges',
        help_text="// Session where the badge was redeemed"
    )

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_offline_badge'
        ordering = ['-issued_at']

    def __str__(self):
        return f'{self.student_profile.student_number} badge issued {self.issued_at:%Y-%m-%d %H:%M}'

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone
        return self.expires_at <= timezone.now()
