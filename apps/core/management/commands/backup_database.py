from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.services.backup_service import create_database_backup


class Command(BaseCommand):
    help = 'Create a compressed database backup and prune expired backups.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', default='')
        parser.add_argument('--keep', type=int, default=30)

    def handle(self, *args, **options):
        try:
            path = create_database_backup(
                output_dir=options['directory'] or None,
                keep=int(options['keep']),
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f'Created backup at {path} at {timezone.now().isoformat()}'
        ))
