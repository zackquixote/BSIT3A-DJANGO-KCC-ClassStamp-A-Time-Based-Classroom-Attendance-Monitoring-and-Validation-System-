"""
// ==============================================================================
// KCC CLASSSTAMP - CLASS PROGRAM/YEAR BACKFILL MANAGEMENT COMMAND
// ==============================================================================
// Usage: python manage.py backfill_class_program [--dry-run]
// Description: Derives Class.program and Class.year_level from legacy section
//   codes (e.g. "BSIT-3A" -> BSIT, Year 3). Only fills rows whose program is
//   still null so it never overwrites admin-entered data; idempotent.
//   Unparseable codes or codes with no matching Program are left null and
//   reported.
// ==============================================================================
"""

import re

from django.core.management.base import BaseCommand

from apps.core.models import Class, Program

# "BSIT-3A" / "BSCS-2B" / "BSIT-1A-CS101" -> program code + year level
CODE_PATTERN = re.compile(r'^([A-Za-z]{2,})-([1-8])[A-Za-z]?(?:-.+)?$')


class Command(BaseCommand):
    help = 'Derives Class program/year_level from legacy section codes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report would-be backfills without writing anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        program_codes = {
            p.code.upper(): p
            for p in Program.objects.only('id', 'code').iterator()
        }

        matched = 0
        skipped_unparseable = 0
        skipped_unknown_program = 0
        pending = []

        for class_obj in (
            Class.objects.filter(program__isnull=True)
            .only('id', 'class_code', 'program_id', 'year_level')
            .iterator()
        ):
            code = (class_obj.class_code or '').strip()
            match = CODE_PATTERN.match(code)
            if not match:
                skipped_unparseable += 1
                continue

            program = program_codes.get(match.group(1).upper())
            if program is None:
                skipped_unknown_program += 1
                continue

            matched += 1
            if not dry_run:
                class_obj.program = program
                class_obj.year_level = int(match.group(2))
                pending.append(class_obj)

        if pending:
            Class.objects.bulk_update(pending, ['program', 'year_level'])

        self.stdout.write('[BACKFILL] Legacy section codes -> program/year_level:')
        self.stdout.write(f'  Matched: {matched}')
        self.stdout.write(f'  Skipped (unparseable code): {skipped_unparseable}')
        self.stdout.write(f'  Skipped (no matching program): {skipped_unknown_program}')
        verb = 'would backfill' if dry_run else 'backfilled'
        self.stdout.write(self.style.SUCCESS(f'[BACKFILL] {matched} class(es) {verb}.'))
