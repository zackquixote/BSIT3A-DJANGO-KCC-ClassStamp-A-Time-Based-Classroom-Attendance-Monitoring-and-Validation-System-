"""
# // ==============================================================================
# // KCC CLASSSTAMP - OUTBOUND MAIL SMOKE TEST
# // ==============================================================================
# // Usage: python manage.py send_test_email you@example.com
# // Description:
# //   Sends one message through the configured backend and reports the transport
# //   it used. Run this after filling in Gmail credentials — a wrong App Password
# //   otherwise fails silently, and the first symptom is a student who never got
# //   their reset link.
# // ==============================================================================
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Sends one test email through the configured backend'

    def add_arguments(self, parser):
        parser.add_argument('recipient', help='Address to send the test message to')

    def handle(self, *args, **options):
        recipient = options['recipient'].strip()
        if '@' not in recipient:
            raise CommandError(f'"{recipient}" does not look like an email address.')

        backend = getattr(settings, 'EMAIL_BACKEND', '')
        self.stdout.write(f'Backend : {backend}')
        self.stdout.write(f'Host    : {getattr(settings, "EMAIL_HOST", "") or "(console)"}')
        self.stdout.write(f'From    : {settings.DEFAULT_FROM_EMAIL}')

        if 'console' in backend:
            self.stdout.write(self.style.WARNING(
                'This backend prints to the console — nothing will actually be delivered.'
            ))

        try:
            sent = send_mail(
                '[KCC ClassStamp] Test message',
                'If you can read this, the ClassStamp mail transport works.',
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f'Delivery failed: {type(exc).__name__}: {exc}')

        if sent:
            self.stdout.write(self.style.SUCCESS(f'Accepted by the backend for {recipient}.'))
        else:
            self.stdout.write(self.style.WARNING('The backend accepted no messages.'))
