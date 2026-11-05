"""Rebuild the CSS/JS bundles by hand.

Rarely needed: the bundles rebuild themselves at app start whenever a source
file is newer than the bundle. Use this to rebuild without restarting, to check
freshness, or to see the resulting sizes.
"""

from django.core.management.base import BaseCommand

from apps.core.services import asset_bundles


class Command(BaseCommand):
    help = 'Rebuild the static CSS and JS bundles now instead of at the next app start.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Report which bundles are out of date without writing anything.',
        )

    def handle(self, *args, **options):
        if options['check']:
            stale = asset_bundles.stale_outputs()
            if stale:
                self.stdout.write(self.style.WARNING('out of date: ' + ', '.join(stale)))
            else:
                self.stdout.write(self.style.SUCCESS('bundles are up to date'))
            return

        base = asset_bundles.static_dir()
        for path, size in asset_bundles.build_all().items():
            self.stdout.write(self.style.SUCCESS(
                f'{path.relative_to(base)}: {size / 1024:.0f} KB'
            ))
