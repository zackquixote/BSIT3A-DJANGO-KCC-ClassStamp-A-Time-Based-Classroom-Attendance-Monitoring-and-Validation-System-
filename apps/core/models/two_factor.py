"""
# // ==============================================================================
# // KCC CLASSSTAMP - TWO-FACTOR RECOVERY CODES
# // ==============================================================================
# // Subsystem: Account Security
# // Description:
# //   A TOTP factor is unforgiving: lose the phone and the account is unreachable.
# //   Each administrator therefore gets a fixed set of single-use recovery codes
# //   at enrolment. Only SHA-256 hashes are stored, so a database read cannot be
# //   replayed as a credential, and a used code is marked rather than deleted so
# //   the audit trail can still show which one was spent.
# // References: apps/core/services/two_factor_service.py
# // ==============================================================================
"""

import hashlib

from django.db import models


def hash_recovery_code(raw_code: str) -> str:
    """SHA-256 of a normalised recovery code (dashes and case removed)."""
    normalised = str(raw_code or '').replace('-', '').replace(' ', '').upper()
    return hashlib.sha256(normalised.encode('utf-8')).hexdigest()


class RecoveryCode(models.Model):
    """One single-use backup code for an administrator's second factor."""

    profile = models.ForeignKey(
        'core.Profile',
        on_delete=models.CASCADE,
        related_name='recovery_codes',
        help_text='// Account the code belongs to',
    )
    code_hash = models.CharField(
        max_length=64, unique=True,
        help_text='// SHA-256 of the normalised code; the plaintext is never stored',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(
        null=True, blank=True,
        help_text='// Set when the code was spent at the login challenge',
    )

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_recovery_code'
        ordering = ['created_at']
        verbose_name = 'Recovery Code'
        verbose_name_plural = 'Recovery Codes'

    def __str__(self):
        state = 'used' if self.used_at else 'unused'
        return f'Recovery code for {self.profile_id} ({state})'

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
