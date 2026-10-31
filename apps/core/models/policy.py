"""
# // ==============================================================================
# // KCC CLASSSTAMP - SYSTEM POLICY (SINGLETON CONFIGURATION)
# // ==============================================================================
# // Subsystem: Administrative Policy
# // Description:
# //   Institution-level thresholds that used to be Python constants. A single row
# //   holds the overrides; every field is nullable, and a NULL means "use the
# //   documented default". Absence of a row is therefore a valid, fully-defaulted
# //   configuration — which is what tests and fresh installs run on.
# // References: apps/core/services/attendance_policy.py
# // ==============================================================================
"""

from django.conf import settings
from django.db import models


class SystemPolicy(models.Model):
    """
    // [Model] Singleton policy overrides.
    // Never rely on this row existing: resolve defaults through
    // `attendance_policy.policy_value()` instead of reading fields directly.
    """

    scan_close_tolerance_minutes = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='// Minutes after the scheduled class end during which a scan is still accepted',
    )
    absence_threshold_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='// Unexcused absence rate that triggers the CHED failure risk band',
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='policy_updates',
        help_text='// Administrator who last changed the policy',
    )

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_system_policy'
        verbose_name = 'System Policy'
        verbose_name_plural = 'System Policy'

    def __str__(self):
        return 'System Policy'

    @classmethod
    def get_solo(cls):
        """Return the policy row, or None when everything is still on defaults."""
        return cls.objects.first()
