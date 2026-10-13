"""
# // ==============================================================================
# // KCC CLASSSTAMP - QR SECRET ROTATION MANAGEMENT COMMAND
# // ==============================================================================
# // Usage: python manage.py rotate_qr_seeds [--days 30] [--force]
# // Description: Implements periodic cryptographic seed rotation for student
# //   attendance QR codes as specified in docs/02_SECURITY.md. Generates fresh
# //   64-character hex seeds and records immutable AuditEvent entries.
# // ==============================================================================
"""

import datetime
import secrets

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import AuditEvent, Profile


class Command(BaseCommand):
    help = 'Rotates dynamic QR secret seeds for approved students exceeding age threshold'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Rotate seeds older than this number of days (default: 30)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Rotate seeds for all approved students regardless of age'
        )

    def handle(self, *args, **options):
        days = options['days']
        force = options['force']

        qs = Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_APPROVED
        )

        if not force:
            threshold = timezone.now() - datetime.timedelta(days=days)
            qs = qs.filter(qr_rotated_at__lte=threshold) | qs.filter(qr_rotated_at__isnull=True)

        total_to_rotate = qs.count()
        if total_to_rotate == 0:
            self.stdout.write(self.style.NOTICE(f"No student QR secrets require rotation (threshold: {days} days)."))
            return

        rotated_count = 0
        now = timezone.now()

        for profile in qs:
            old_secret_preview = f"...{profile.qr_secret[-8:]}" if profile.qr_secret else "None"
            new_secret = secrets.token_hex(32)

            profile.qr_secret = new_secret
            profile.qr_rotated_at = now
            profile.save(update_fields=['qr_secret', 'qr_rotated_at'])

            AuditEvent.objects.create(
                actor=None,  # Automated cron/management command
                action='ROTATE_QR_SECRET',
                object_type='Profile',
                object_id=str(profile.pk),
                old_value=f"Seed rotated from {old_secret_preview}",
                new_value=f"New 64-char seed provisioned at {now.isoformat()}",
                reason=f"Scheduled security seed rotation policy ({days} days)",
            )
            rotated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"[SUCCESS] Rotated QR seeds for {rotated_count} approved student profile(s)."
        ))
