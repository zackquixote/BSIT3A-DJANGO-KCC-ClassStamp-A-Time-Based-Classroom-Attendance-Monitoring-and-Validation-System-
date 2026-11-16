"""
Sync the BSTM prospectus from the registrar's workbook.

The workbook is a curriculum (code | number | title | units | pre-requisite), not a
section timetable: it carries no faculty, day, time or room, so it can only update
the Curriculum Matrix.

    python manage.py update_bstm_prospectus --dry-run
    python manage.py update_bstm_prospectus --apply

Layout handled: a year banner ("F I R S T   Y E A R"), then two semesters side by
side — columns 1-5 for the first semester, 6-10 for the second.
"""

import pathlib
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.management.commands.import_curriculum_docs import code_key
from apps.core.models import Curriculum, CurriculumVersion, Program, Subject
from apps.core.services.academic_service import CLASSIFICATION_MAJOR, classify_subject

DEFAULT_FILE = pathlib.Path('docs/curriculum/BSTM-Updated-Curriculum-AY-2025-2026.xlsx')

YEAR_WORDS = {
    'firstyear': 1,
    'secondyear': 2,
    'thirdyear': 3,
    'fourthyear': 4,
}

# These titles are shared with BSA / BSBA / BSIT / BSCRIM, so a rename lands on
# every program. The ones below are unambiguous corrections; 'Theology 2' is a
# genuine content difference between prospectuses, so it stays untouched.
RENAME_SKIP = {'THEOLOGY2'}


def clean_units(value):
    text = str(value).strip().strip('[] ') if value is not None else ''
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def parse_workbook(path):
    """Return [(year_level, semester, code, title, units)] in file order."""
    from openpyxl import load_workbook

    workbook = load_workbook(path, data_only=True)
    sheet = workbook['Final 10-31'] if 'Final 10-31' in workbook.sheetnames else workbook.worksheets[0]

    entries = []
    year_level = None
    for row in sheet.iter_rows(values_only=True):
        values = list(row) + [None] * (12 - len(row))

        joined = re.sub(r'[^A-Za-z]', '', str(values[0] or '')).lower()
        if joined in YEAR_WORDS:
            year_level = YEAR_WORDS[joined]
            continue

        if year_level is None:
            continue

        for offset, semester in ((0, 1), (5, 2)):
            prefix = str(values[offset] or '').strip()
            number = str(values[offset + 1] or '').strip()
            title = str(values[offset + 2] or '').strip()
            units = clean_units(values[offset + 3])

            if not prefix or not title or units is None:
                continue
            if prefix.upper() in ('CODE', 'COURSE TITLE') or 'total' in prefix.lower():
                continue
            if not re.match(r'^[A-Za-z]', prefix):
                continue

            code = f'{prefix} {number}'.strip()
            entries.append((year_level, semester, code, title, units))

    workbook.close()
    return entries


class Command(BaseCommand):
    help = 'Update the BSTM curriculum from the registrar prospectus workbook.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE))
        parser.add_argument('--program', default='BSTM')
        parser.add_argument('--apply', action='store_true', help='Write (default: dry run).')
        parser.add_argument('--dry-run', action='store_true', help='Explicit dry run (default).')

    def handle(self, *args, **options):
        path = pathlib.Path(options['file'])
        if not path.exists():
            raise CommandError(f'Workbook not found: {path}')

        program = Program.objects.filter(code__iexact=options['program']).first()
        if program is None:
            raise CommandError(f'Program {options["program"]} does not exist.')

        version = (
            CurriculumVersion.objects.filter(program=program, status=CurriculumVersion.STATUS_APPROVED).first()
            or CurriculumVersion.objects.filter(program=program).order_by('-version_number').first()
        )
        if version is None:
            raise CommandError(f'{program.code} has no curriculum version to update.')

        parsed = parse_workbook(path)
        if not parsed:
            raise CommandError('No subjects were found in the workbook.')

        mode = 'APPLY' if options['apply'] else 'DRY RUN'
        self.stdout.write(self.style.MIGRATE_HEADING(f'=== BSTM prospectus sync ({mode}) ==='))
        self.stdout.write(f'source   : {path.name}')
        self.stdout.write(f'program  : {program.code} | version v{version.version_number} ({version.status})')
        self.stdout.write(f'subjects : {len(parsed)} rows from the workbook')

        existing_subjects = {}
        for subject in Subject.objects.all():
            existing_subjects.setdefault(code_key(subject.code), subject)

        linked = {
            entry.subject_id: entry
            for entry in Curriculum.objects.filter(program=program, version=version)
        }

        new_subjects, new_entries, renames, unit_fixes, moved = [], [], [], [], []

        for year_level, semester, code, title, units in parsed:
            key = code_key(code)
            subject = existing_subjects.get(key)
            if subject is None:
                new_subjects.append((code, title, units))
                continue

            if subject.name.strip().lower() != title.strip().lower() and key not in RENAME_SKIP:
                renames.append((code, subject.name, title))
            if subject.units != units:
                unit_fixes.append((code, subject.units, units))

            current = linked.get(subject.id)
            if current is None:
                new_entries.append((year_level, semester, code, title, units))
            elif (current.year_level, current.semester) != (year_level, semester):
                moved.append((code, (current.year_level, current.semester), (year_level, semester)))

        self.stdout.write('')
        self.stdout.write(f'new subjects      : {len(new_subjects)}')
        for code, title, units in new_subjects:
            self.stdout.write(f'   + {code:14s} {title[:48]} ({units}u)')
        self.stdout.write(f'new matrix rows   : {len(new_entries)}')
        for year_level, semester, code, _title, units in new_entries:
            self.stdout.write(f'   + Y{year_level}S{semester} {code:14s} {units}u')
        self.stdout.write(f'title corrections : {len(renames)}')
        for code, old, new in renames:
            self.stdout.write(f'   ~ {code:14s} "{old[:38]}" -> "{new[:38]}"')
        self.stdout.write(f'unit corrections  : {len(unit_fixes)}')
        for code, old, new in unit_fixes:
            self.stdout.write(f'   ~ {code:14s} {old}u -> {new}u')
        self.stdout.write(f'placement moves   : {len(moved)}')
        for code, old, new in moved:
            self.stdout.write(f'   > {code:14s} Y{old[0]}S{old[1]} -> Y{new[0]}S{new[1]}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('\nDry run only. Re-run with --apply to write.'))
            return

        with transaction.atomic():
            for code, title, units in new_subjects:
                subject = Subject.objects.create(code=code[:40], name=title[:150], units=units)
                existing_subjects[code_key(code)] = subject

            for code, old, new in renames:
                subject = existing_subjects.get(code_key(code))
                if subject is not None:
                    subject.name = new[:150]
                    subject.save(update_fields=['name'])

            for code, _old, new in unit_fixes:
                subject = existing_subjects.get(code_key(code))
                if subject is not None:
                    subject.units = new
                    subject.save(update_fields=['units'])

            for year_level, semester, code, title, units in parsed:
                subject = existing_subjects.get(code_key(code))
                if subject is None:
                    continue
                entry = linked.get(subject.id)
                if entry is None:
                    Curriculum.objects.create(
                        program=program,
                        version=version,
                        subject=subject,
                        year_level=year_level,
                        semester=semester,
                        is_major=classify_subject(subject.code, True) == CLASSIFICATION_MAJOR,
                    )
                elif (entry.year_level, entry.semester) != (year_level, semester):
                    entry.year_level = year_level
                    entry.semester = semester
                    entry.save(update_fields=['year_level', 'semester'])

        total = Curriculum.objects.filter(program=program, version=version).count()
        self.stdout.write(self.style.SUCCESS(f'\nDone. {program.code} now has {total} matrix rows.'))
