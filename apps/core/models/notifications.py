from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='classstamp_notifications',
    )
    category = models.CharField(max_length=32, db_index=True)
    title = models.CharField(max_length=180)
    message = models.TextField()
    link = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        app_label = 'core'
        db_table = 'tblcs_notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read_at', '-created_at'], name='notif_user_read_idx'),
        ]

    def __str__(self):
        return f'{self.title} -> {self.user}'
