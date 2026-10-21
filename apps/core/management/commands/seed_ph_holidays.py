"""
# // ==============================================================================
# // KCC CLASSSTAMP - MANAGEMENT COMMAND: SEED PHILIPPINE HOLIDAYS
# // ==============================================================================
# // Subsystem: Academic Administration & Calendar Logistics
# // Description: CLI command to populate official Philippine Regular and Special
# //   Non-Working Holidays into the institutional Academic Calendar.
# // Usage:
# //   python manage.py seed_ph_holidays
# //   python manage.py seed_ph_holidays --year 2026 2027
# // ==============================================================================
"""

import datetime
from django.core.management.base import BaseCommand
from apps.core.services import seed_philippine_holidays


class Command(BaseCommand):
    help = "Populate official Philippine Regular and Special Non-Working Holidays into the Academic Calendar."

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            nargs='+',
            type=int,
            default=[datetime.date.today().year, datetime.date.today().year + 1],
            help="Year(s) to seed holidays for (defaults to current and next year).",
        )

    def handle(self, *args, **options):
        years = options['year']
        self.stdout.write(self.style.NOTICE(f"Seeding official Philippine holidays for year(s): {years}..."))

        total_created = 0
        total_existing = 0

        for yr in years:
            res = seed_philippine_holidays(yr)
            created = res['created_count']
            existing = res['existing_count']
            total_created += created
            total_existing += existing
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [Year {yr}] Provisioned {created} new holiday(s); {existing} already present."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed Philippine Holiday sync! Total new: {total_created}, Existing: {total_existing}."
            )
        )
