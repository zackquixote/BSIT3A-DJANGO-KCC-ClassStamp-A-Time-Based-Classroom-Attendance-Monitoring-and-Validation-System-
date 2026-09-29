from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Info(models.Model):
    name = models.CharField(max_length=255)
    age = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(150)])
    address = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='infos',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tblinfo'
        ordering = ['name']

    def __str__(self):
        return self.name
