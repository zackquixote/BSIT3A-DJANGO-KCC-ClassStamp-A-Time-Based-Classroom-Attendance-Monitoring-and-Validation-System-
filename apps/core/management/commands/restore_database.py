from pathlib import Path
import gzip

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Restore a MySQL database from a ClassStamp SQL.gz backup.'

    def add_arguments(self, parser):
        parser.add_argument('backup_file')
        parser.add_argument('--yes', action='store_true')

    def handle(self, *args, **options):
        backup = Path(options['backup_file'])
        if not backup.is_file():
            raise CommandError(f'Backup file not found: {backup}')
        if not options['yes']:
            raise CommandError('Restore is destructive. Re-run with --yes after verifying the backup.')

        try:
            from django.conf import settings
            import os
            import subprocess

            db = settings.DATABASES['default']
            mysql = os.environ.get('MYSQL_PATH', 'mysql')
            command = [
                mysql, '-h', db['HOST'], '-P', str(db['PORT']),
                '-u', db['USER'], db['NAME'],
            ]
            env = dict(os.environ, MYSQL_PWD=db.get('PASSWORD') or '')
            with gzip.open(backup, 'rb') as source:
                subprocess.run(command, stdin=source, env=env, check=True)
        except subprocess.CalledProcessError as exc:
            raise CommandError(f'Restore failed: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Restored database from {backup}.'))
