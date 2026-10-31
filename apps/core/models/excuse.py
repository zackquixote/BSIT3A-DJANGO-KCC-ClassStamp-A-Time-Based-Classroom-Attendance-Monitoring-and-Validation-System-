"""
# // ==============================================================================
# // KCC CLASSSTAMP - EXCUSE SLIP MODEL
# // ==============================================================================
# // Subsystem: Attendance Exception Workflow (S-08)
# // Description: Student-filed justification for an absence, routed to the
# //   session's instructor for approval or rejection. Approval converts the
# //   absence into an EXCUSED attendance record with a full audit trail.
# // ==============================================================================
"""

from django.conf import settings
from django.db import models

from apps.core.validators import validate_uploaded_document

from .attendance import ClassSession
from .profile import Profile


class ExcuseSlip(models.Model):
    """
    // [Model] Online Excuse Slip (Absence Justification Workflow)
    """
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    student_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='excuse_slips',
        help_text="// Student filing the excuse"
    )
    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name='excuse_slips',
        help_text="// Session the student was marked absent from"
    )
    reason = models.TextField(help_text="// Student's justification for the absence")
    attachment = models.FileField(
        upload_to='excuse_slips/',
        null=True, blank=True,
        validators=[validate_uploaded_document],
        help_text="// Optional supporting document (medical certificate, letter)"
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING,
        db_index=True,
    )
    review_note = models.TextField(
        null=True, blank=True,
        help_text="// Instructor feedback when rejecting"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_excuse_slips',
        help_text="// Instructor who approved or rejected the slip"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_excuse_slip'
        unique_together = [('student_profile', 'session')]
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'{self.student_profile.student_number} — '
            f'{self.session.slot.class_obj.class_code} ({self.session.session_date}) — {self.status}'
        )
