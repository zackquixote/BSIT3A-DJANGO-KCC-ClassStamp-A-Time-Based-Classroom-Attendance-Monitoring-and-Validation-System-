"""
# // ==============================================================================
# // KCC CLASSSTAMP - FRAUD DETECTION, ANOMALY FLAGGING & AUDIT TRAIL MODELS
# // ==============================================================================
# // Subsystem: Security Intelligence & Compliance Audit
# // Description: Models supporting the fraud detection and audit trail subsystems:
# //   - AnomalyFlag:   Raised by automated pattern detectors (impossible travel,
# //                    proxy sharing, rapid duplicate token reuse, etc.).
# //   - ReviewAction:  Append-only history of administrative adjudication decisions
# //                    rendered against open AnomalyFlag alerts.
# //   - AuditEvent:    Global immutable security log for all high-privilege
# //                    operations (approvals, rejections, QR rotations, overrides).
# //                    MUST NEVER be updated or pruned in production.
# // References: docs/02_SECURITY.md § Fraud Detection | docs/04_MODELS_REFERENCE.md
# // ==============================================================================
"""

from django.conf import settings
from django.db import models

from .attendance import AttendanceRecord


class AnomalyFlag(models.Model):
    """
    // [Model] Attendance Anomaly / Fraud Flag
    // Triggered automatically by pattern detectors (e.g., impossible travel time,
    // proxy device sharing, duplicate tokens in short spans).
    """
    STATUS_OPEN = 'OPEN'
    STATUS_DISMISSED = 'DISMISSED'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_EXCUSED = 'EXCUSED'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_DISMISSED, 'Dismissed'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_EXCUSED, 'Excused'),
    ]

    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.RESTRICT,
        related_name='anomaly_flags'
    )
    rule_code = models.CharField(
        max_length=50,
        help_text="// Rule mnemonic, e.g. RULE_RAPID_SCAN_PROXY"
    )
    reason = models.TextField(help_text="// Detailed forensic rationale")
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True, blank=True,
        help_text="// Statistical confidence score (0.0000 - 1.0000)"
    )
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_anomaly_flag'
        unique_together = [('attendance_record', 'rule_code')]

    def __str__(self):
        return f'{self.rule_code} - {self.status}'


class ReviewAction(models.Model):
    """
    // [Model] Forensic Anomaly Adjudication Action
    // Append-only history of administrative decisions rendered against AnomalyFlag alerts.
    """
    DECISION_DISMISS = 'DISMISS'
    DECISION_CONFIRM_PROXY = 'CONFIRM_PROXY'
    DECISION_EXCUSE = 'EXCUSE'
    DECISION_OTHER = 'OTHER'
    DECISION_CHOICES = [
        (DECISION_DISMISS, 'Dismiss'),
        (DECISION_CONFIRM_PROXY, 'Confirm Proxy'),
        (DECISION_EXCUSE, 'Excuse'),
        (DECISION_OTHER, 'Other'),
    ]

    anomaly_flag = models.ForeignKey(
        AnomalyFlag,
        on_delete=models.RESTRICT,
        related_name='review_actions'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='review_actions',
        help_text="// Admin or authorized investigator"
    )
    decision = models.CharField(max_length=14, choices=DECISION_CHOICES)
    reason = models.TextField(help_text="// Official justification for adjudication")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_review_action'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.decision} by {self.reviewer} on flag #{self.anomaly_flag_id}'


class AuditEvent(models.Model):
    """
    // [Model] Global Append-Only Security & Operational Audit Log
    // Tracks all high-privilege activities (account validations, overrides, key rotations).
    // Immutable record: entries should never be updated or pruned in production.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_events',
        help_text="// User account responsible for action"
    )
    action = models.CharField(max_length=80, help_text="// Action keyword e.g. APPROVE_STUDENT")
    object_type = models.CharField(max_length=80, help_text="// Target entity class e.g. Profile")
    object_id = models.CharField(max_length=80, null=True, blank=True, help_text="// Primary key of affected record")
    old_value = models.TextField(null=True, blank=True, help_text="// Previous state snapshot")
    new_value = models.TextField(null=True, blank=True, help_text="// Updated state snapshot")
    reason = models.TextField(null=True, blank=True, help_text="// User-provided remark or explanation")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_audit_event'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} on {self.object_type} #{self.object_id}'
