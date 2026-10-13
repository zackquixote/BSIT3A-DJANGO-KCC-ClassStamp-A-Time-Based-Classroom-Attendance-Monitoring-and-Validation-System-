"""
// ==============================================================================
// KCC CLASSSTAMP - INFO APP DATA MODEL
// ==============================================================================
// Description: Auxiliary institutional information / contact registry entity.
// Supports user-scoped CRUD operations with ownership constraints.
// References: docs/04_MODELS_REFERENCE.md | apps/scoping.py
// ==============================================================================
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# // ==============================================================================
# // MODEL: Info (tblinfo)
# // ==============================================================================
class Info(models.Model):
    """
    // [Model] Auxiliary Contact / Demographic Record
    // Scoped per user account to support multi-tenant data isolation.
    """
    name = models.CharField(
        max_length=255,
        help_text="// Full entity or contact name"
    )
    age = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(150)],
        help_text="// Age in years (Validated between 1 and 150)"
    )
    address = models.CharField(
        max_length=255,
        help_text="// Physical residential or departmental address"
    )
    email = models.EmailField(
        max_length=255,
        blank=True,
        help_text="// Contact electronic mail address"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='infos',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="// Owning user account for privacy scoping"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblinfo'
        ordering = ['name']

    def __str__(self):
        return self.name
