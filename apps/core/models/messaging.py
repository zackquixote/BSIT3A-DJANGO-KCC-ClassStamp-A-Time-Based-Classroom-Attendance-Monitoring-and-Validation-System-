"""
# // ==============================================================================
# // KCC CLASSSTAMP - INTERNAL MESSAGING MODEL
# // ==============================================================================
# // Subsystem: Internal Communication
# // Description: Message model for student-teacher-admin communication within
# //   the ClassStamp system. Enables in-app messaging with validation rules
# //   enforced by MessageService.
# //
# // Validation Rules (enforced in MessageService):
# //   - Student → Teacher: recipient must teach at least one of sender's classes
# //   - Teacher → Student: sender must teach at least one of recipient's classes
# //   - Teacher → Admin: no restriction
# //   - Admin → Any: no restriction
# //
# // References: specs/system-integration-enhancement-suite/requirements.md § 8
# // ==============================================================================
"""

from django.conf import settings
from django.db import models


class Message(models.Model):
    """
    // [Model] Internal Message for ClassStamp Communication
    // Enables secure in-app messaging between students, teachers, and admins.
    """

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        help_text="// User who sent the message"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages',
        help_text="// User who receives the message"
    )
    subject = models.CharField(
        max_length=200,
        help_text="// Message subject line"
    )
    body = models.TextField(
        help_text="// Message content"
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="// Whether the recipient has read this message"
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="// Timestamp when message was read by recipient"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="// Message send timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="// Last modification timestamp"
    )

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_message'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', '-created_at'], name='msg_sender_date_idx'),
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='msg_recipient_read_idx'),
        ]

    def __str__(self):
        return f'{self.subject} from {self.sender} to {self.recipient}'
