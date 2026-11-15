"""
Import the official curriculum documents in ``docs/curriculum`` into the system.

Two source layouts are supported:

* Word prospectuses (Appendix F.1): one table per year/semester, preceded by a
  heading paragraph such as "FIRST YEAR - 1ST SEMESTER".
* Excel grids: one sheet per programme, semesters side by side, year headings
  ("F I R S T   Y E A R") and the occasional SUMMER block.

The command is dry-run by default; pass ``--apply`` to write. It reuses any
subject that already exists under a normalised code (so "CC 101" and "CC101"
never become two rows), rebuilds the programme's draft prospectus from the
document, and approves it effective the document's school year — the same
workflow an administrator would follow in the UI.

    python manage.py import_curriculum_docs --dry-run
    python manage.py import_curriculum_docs --apply
"""

import datetime
import difflib
import pathlib
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    Curriculum,
    CurriculumVersion,
    Department,
    Program,
    Subject,
)
from apps.core.services.curriculum_version_service import (
    approve_curriculum_draft,
    current_draft_version,
    latest_curriculum_version,
)

DOCS_DIR = pathlib.Path('docs/curriculum')

YEAR_WORDS = {
    'FIRST': 1, '1ST': 1,
    'SECOND': 2, '2ND': 2,
    'THIRD': 3, '3RD': 3,
    'FOURTH': 4, '4TH': 4,
}

# Obvious transcription slips in the source documents. Kept explicit (instead of
# fuzzy matching) so every correction is auditable: without this, BSA's NSTP 2
# row would publish "CWTS 1/ROTC 1" and spawn a duplicate subject.
TITLE_FIXES = {
    ('BSA', 'NSTP 2'): 'CWTS 2/ROTC 2',
}

# Codes that genuinely name a *different course* in one programme than in the
# shared master list. Only these get a programme-qualified duplicate; every other
# code keeps one subject so the matrix never fills with near-twins.
DISTINCT_COURSES = {
    ('BSA', 'ACCT1'),   # Auditing and Assurance Principles, not Principles of Accounting
}

# Seeder-era titles that the official prospectus supersedes. The shared subject
# is renamed in place (one code = one course) instead of being duplicated.
TITLE_RENAMES = {
    'IT203': 'Systems Integration and Architecture 1',
}
HEADING_RE = re.compile(r'(FIRST|SECOND|THIRD|FOURTH)\s*YEAR\s*[-–]?\s*(1ST|2ND)?\s*SEMESTER', re.I)
YEAR_ONLY_RE = re.compile(r'^(FIRST|SECOND|THIRD|FOURTH)\s*YEAR$', re.I)


def normalise_code(*parts):
    """Join "CC" + "101" into "CC 101"; collapse stray whitespace/decimals."""
    pieces = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if not text:
            continue
        text = re.sub(r'\.0+$', '', text)          # 101.0 -> 101
        pieces.append(text)
    code = ' '.join(pieces)
    return re.sub(r'\s+', ' ', code).strip()


def code_key(code):
    """Comparison key that ignores case and spacing ("cc 101" == "CC101")."""
    return re.sub(r'[^A-Z0-9]', '', (code or '').upper())


def parse_units(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    text = text.replace('[', '').replace(']', '')
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if value <= 0 or value > 12:
        return None
    return int(value) if value == int(value) else round(value, 2)


# --------------------------------------------------------------------------- docx
def parse_docx(path):
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:  # pragma: no cover - depends on the deployment
        raise CommandError(
            'Reading the BSIT prospectus needs python-docx. Install it with:\n'
            '    pip install python-docx==1.2.0'
        ) from exc

    document = Document(path)
    entries = []
    year, semester = None, None
    body = document.element.body
    for child in body.iterchildren():
        if child.tag.endswith('}p'):
            text = re.sub(r'\s+', ' ', Paragraph(child, document).text or '').strip()
            if not text:
                continue
            match = HEADING_RE.search(text.upper())
            if match:
                year = YEAR_WORDS.get(match.group(1).upper())
                semester = 3 if 'SUMMER' in text.upper() else (2 if match.group(2) == '2ND' else 1)
            elif 'SUMMER' in text.upper() and year:
                semester = 3
        elif child.tag.endswith('}tbl'):
            table = Table(child, document)
            if not year or not semester:
                continue
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if len(cells) < 6:
                    continue
                joined = ' '.join(cells).upper()
                if 'COURSE CODE' in joined or 'TOTAL' in joined:
                    continue
                code = normalise_code(cells[0], cells[1])
                title = re.sub(r'\s+', ' ', cells[2]).strip()
                units = parse_units(cells[5])
                if not code or not title or units is None:
                    continue
                entries.append({
                    'year': year, 'semester': semester,
                    'code': code, 'title': title, 'units': units,
                })
    return entries


# ---------------------------------------------------------------------------- xlsx
def parse_markdown_table(path):
    """Read a prospectus transcribed as Markdown: one table per year, semesters
    side by side (code, number, description, units twice)."""
    text = pathlib.Path(path).read_text(encoding='utf-8')
    entries = []
    year = None

    for line in text.splitlines():
        if line.startswith('## '):
            match = YEAR_ONLY_RE.match(re.sub(r'\s+', '', line[3:]).upper())
            year = YEAR_WORDS.get(match.group(1).upper()) if match else None
            continue
        if not line.startswith('|') or year is None:
            continue

        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if len(cells) < 8:
            continue
        if cells[0].upper() == '1ST SEMESTER' or (cells[0] and set(cells[0]) <= {'-'}):
            continue
        if cells[2].upper() == 'TOTAL':
            continue

        for semester, offset in ((1, 0), (2, 4)):
            code = normalise_code(cells[offset], cells[offset + 1])
            title = re.sub(r'\s+', ' ', cells[offset + 2]).strip()
            units = parse_units(cells[offset + 3])
            if not code or not title or units is None:
                continue
            entries.append({
                'year': year, 'semester': semester,
                'code': code, 'title': title, 'units': units,
            })
    return entries


def parse_grid_sheet(workbook, sheet_name):
    sheet = workbook[sheet_name]
    entries = []
    year, semester_override = None, None
    groups = []
    max_row = sheet.max_row or 0
    max_col = min(sheet.max_column or 0, 14)

    for r in range(1, max_row + 1):
        row = [sheet.cell(row=r, column=c).value for c in range(1, max_col + 1)]
        texts = [('' if v is None else str(v).strip()) for v in row]
        flat = re.sub(r'\s+', '', ' '.join(texts)).upper()

        if not any(texts):
            continue

        if 'SUMMER' in flat and len([t for t in texts if t]) <= 3:
            semester_override = 3
            groups = []
            continue

        year_match = None
        for text in texts:
            compact = re.sub(r'\s+', '', text).upper()
            m = YEAR_ONLY_RE.match(compact)
            if m:
                year_match = YEAR_WORDS.get(m.group(1).upper())
                break
            m2 = HEADING_RE.search(text.upper())
            if m2:
                year_match = YEAR_WORDS.get(m2.group(1).upper())
                semester_override = 3 if 'SUMMER' in text.upper() else (2 if m2.group(2) == '2ND' else 1)
                break
        if year_match:
            year = year_match
            if 'SUMMER' not in flat:
                semester_override = None
            groups = []
            continue

        # header row: locate every "CODE" column and remember its field offsets
        code_cols = [i for i, t in enumerate(texts) if re.sub(r'\s+', '', t).upper() == 'CODE']
        if code_cols:
            groups = code_cols
            continue

        # Some prospectuses have no "CODE" header at all: the semester label
        # itself sits above the code column (BSBA: "1st SEMESTER … 2nd SEMESTER").
        sem_cols = [
            i for i, t in enumerate(texts)
            if re.sub(r'\s+', '', t).upper() in (
                '1STSEMESTER', 'FIRSTSEMESTER', '2NDSEMESTER', 'SECONDSEMESTER',
            )
        ]
        if sem_cols:
            groups = sem_cols
            continue

        if not year or not groups:
            continue

        for index, col in enumerate(groups):
            def cell(offset):
                pos = col + offset
                return texts[pos] if pos < len(texts) else ''

            code = normalise_code(cell(0), cell(1))
            title = re.sub(r'\s+', ' ', cell(2)).strip()
            units = parse_units(cell(3))
            if not code or not title or units is None:
                continue
            if 'TOTAL' in code.upper() or 'TOTAL' in title.upper():
                continue
            semester = semester_override if semester_override == 3 else (index + 1 if index < 2 else 1)
            entries.append({
                'year': year, 'semester': semester,
                'code': code, 'title': title, 'units': units,
            })
    return entries


# Programmes the source documents may introduce. Everything else must exist
# already; auto-creating an unknown code would hide a typo in the document name.
AUTO_PROGRAMS = {
    'BSTM': ('Bachelor of Science in Tourism Management', 'CMAT'),
    'BSCRIM': ('Bachelor of Science in Criminology', 'COC'),
}


class Command(BaseCommand):
    help = 'Import the official curriculum documents from docs/curriculum into the database.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the changes (default is a dry run).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Explicit dry run (the default).')
        parser.add_argument('--docs-dir', default=str(DOCS_DIR),
                            help='Folder holding the curriculum documents.')

    # ------------------------------------------------------------------ helpers
    def _source_plan(self, docs_dir):
        """Return [(program_code, label, parser, payload, effective_term)]."""
        docs = pathlib.Path(docs_dir)
        plan = []

        docx_path = docs / 'Appendix-F.1-BSIT-Curriculum-2023-2024.docx'
        if docx_path.exists():
            plan.append({
                'program': 'BSIT', 'file': docx_path.name, 'kind': 'docx',
                'path': docx_path, 'sheet': None, 'term': '2023-2024',
            })

        xlsx_specs = [
            ('BSA-Revised-Curriculum-AY2023-2024-1.xlsx', 'BSA Curriculum', 'BSA', '2023-2024'),
            ('BSBA-Revised-Curriculum-AY-2023-2024-1.xlsx', 'BSBA - FM', 'BSBA', '2023-2024'),
            ('BSTM-Updated-Curriculum-AY-2025-2026-1.xlsx', 'Sheet1', 'BSTM', '2025-2026'),
        ]
        for filename, sheet, program, term in xlsx_specs:
            path = docs / filename
            if path.exists():
                plan.append({
                    'program': program, 'file': filename, 'kind': 'xlsx',
                    'path': path, 'sheet': sheet, 'term': term,
                })

        md_path = docs / 'KCC-BSCRIM-Curriculum-2023-2024.md'
        if md_path.exists():
            plan.append({
                'program': 'BSCRIM', 'file': md_path.name, 'kind': 'md',
                'path': md_path, 'sheet': None, 'term': '2023-2024',
            })
        return plan

    def _load_entries(self, spec):
        if spec['kind'] == 'docx':
            return parse_docx(spec['path'])
        if spec['kind'] == 'md':
            return parse_markdown_table(spec['path'])
        from openpyxl import load_workbook
        workbook = load_workbook(spec['path'], data_only=True)
        try:
            return parse_grid_sheet(workbook, spec['sheet'])
        finally:
            workbook.close()

    def _ensure_term(self, label):
        """Return (or create) the academic year 'YYYY-YYYY 1st Sem' for a school year."""
        name = f'{label} 1st Sem'
        term = AcademicYear.objects.filter(name=name).first()
        if term:
            return term, False
        start_year = int(label.split('-')[0])
        term = AcademicYear.objects.create(
            name=name,
            starts_on=datetime.date(start_year, 8, 1),
            ends_on=datetime.date(start_year + 1, 5, 31),
            is_active=False,
        )
        return term, True

    def _ensure_program(self, code):
        program = Program.objects.filter(code=code).first()
        if program:
            return program, False
        if code not in AUTO_PROGRAMS:
            raise CommandError(f'Program {code} does not exist and is not auto-created.')
        name, dept_code = AUTO_PROGRAMS[code]
        department = Department.objects.filter(code=dept_code).first()
        if department is None:
            raise CommandError(f'{dept_code} department is required to create {code}.')
        program = Program.objects.create(
            code=code,
            name=name,
            department=department,
            years_total=4,
            is_active=True,
        )
        return program, True

    def _resolve_subject(self, entry, program_code, cache, created, reused, conflicts):
        """Reuse the subject behind this code, or create one.

        The Subject table is shared by every programme, so a code can only hold
        one course. When an existing subject under the same code names a really
        different course ("ACCT 1" is Principles of Accounting in BSIT and
        Auditing in BSA), the imported row gets a programme-qualified code
        instead of silently inheriting the wrong title.
        """
        key = code_key(entry['code'])
        if key in cache:
            return cache[key]
        existing = self._subject_index.get(key)
        if existing is not None and (program_code, key) in DISTINCT_COURSES:
            qualified = f"{existing.code} ({program_code})"
            qualified_key = code_key(qualified)
            twin = self._subject_index.get(qualified_key)
            if twin is not None:
                cache[key] = twin
                return twin
            conflicts.append((existing.code, existing.name, entry['title'], program_code))
            existing = None
            entry = dict(entry, code=qualified)
            key = qualified_key
        if existing is None:
            if len(entry['code']) > 40:
                raise CommandError(f'Subject code too long: {entry["code"]!r}')
            existing = Subject.objects.create(
                code=entry['code'],
                name=entry['title'][:150],
                units=entry['units'],
                is_active=True,
            )
            created.append(entry['code'])
            self._subject_index[key] = existing
        else:
            reused.add(existing.code)
            official = TITLE_RENAMES.get(key)
            if official and existing.name.strip() != official:
                self._title_notes.append((existing.code, existing.name, official))
                existing.name = official
                existing.save(update_fields=['name'])
            elif self._title_similarity(existing.name, entry['title']) < 0.90:
                self._title_notes.append((existing.code, existing.name, entry['title']))
        cache[key] = existing
        return existing

    @staticmethod
    def _title_similarity(left, right):
        def norm(text):
            return re.sub(r'[^a-z0-9 ]', ' ', (text or '').lower())
        return difflib.SequenceMatcher(None, norm(left), norm(right)).ratio()

    def _already_imported(self, program, spec):
        """True when the approved version already holds exactly these rows."""
        approved = latest_curriculum_version(
            program, statuses=(CurriculumVersion.STATUS_APPROVED,),
        )
        if approved is None or approved.notes != f'Imported from {spec["file"]}':
            return False
        current = {
            (entry.year_level, entry.semester, code_key(entry.subject.code.split(' (')[0]))
            for entry in approved.entries.select_related('subject')
        }
        desired = {
            (entry['year'], entry['semester'], code_key(entry['code']))
            for entry in spec['entries']
        }
        return current == desired

    # ------------------------------------------------------------------- handle
    def handle(self, *args, **options):
        apply_changes = options['apply']
        plan = self._source_plan(options['docs_dir'])
        if not plan:
            raise CommandError('No curriculum documents found.')

        mode = 'APPLY' if apply_changes else 'DRY RUN'
        self.stdout.write(self.style.MIGRATE_HEADING(f'=== Curriculum import ({mode}) ==='))

        summary = []
        for spec in plan:
            entries = self._load_entries(spec)
            for entry in entries:
                fixed = TITLE_FIXES.get((spec['program'], entry['code']))
                if fixed:
                    entry['title'] = fixed
            # de-duplicate inside one document
            seen, unique = set(), []
            for entry in entries:
                key = (entry['year'], entry['semester'], code_key(entry['code']))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(entry)
            spec['entries'] = unique
            by_term = {}
            for entry in unique:
                by_term.setdefault((entry['year'], entry['semester']), 0)
                by_term[(entry['year'], entry['semester'])] += 1
            summary.append((spec, len(unique), by_term))

        for spec, count, by_term in summary:
            grid = ', '.join(f'Y{y}S{s}:{n}' for (y, s), n in sorted(by_term.items()))
            self.stdout.write(f'\n[{spec["program"]}] {spec["file"]} -> {count} subjects  ({grid})')
            if count == 0:
                self.stdout.write(self.style.WARNING('  ! nothing parsed — check the sheet name/layout'))
                continue
            program = Program.objects.filter(code=spec['program']).first()
            if program is not None and self._already_imported(program, spec):
                spec['skip'] = True
                self.stdout.write('  = already imported (identical rows) — nothing to do')

        if not apply_changes:
            self.stdout.write(self.style.WARNING('\nDry run only. Re-run with --apply to write.'))
            return

        for spec, count, _ in summary:
            if count == 0 or spec.get('skip'):
                continue
            self._import_one(spec)

        self.stdout.write(self.style.SUCCESS('\nImport finished.'))

    @transaction.atomic
    def _import_one(self, spec):
        program, program_created = self._ensure_program(spec['program'])
        if program_created:
            self.stdout.write(self.style.SUCCESS(f'  + program {program.code} created'))

        # One index for every subject in the system: "CC 101" and "CC101" are
        # the same course and must not become two rows.
        self._subject_index = {code_key(s.code): s for s in Subject.objects.all()}

        term, term_created = self._ensure_term(spec['term'])
        if term_created:
            self.stdout.write(f'  + academic term {term.name} created')

        cache, created_subjects, reused_subjects = {}, [], set()
        conflicts, self._title_notes = [], []
        self._subject_index = {code_key(s.code): s for s in Subject.objects.all()}
        draft = current_draft_version(program)
        if draft is None:
            next_number = (
                CurriculumVersion.objects.filter(program=program)
                .order_by('-version_number')
                .values_list('version_number', flat=True)
                .first() or 0
            ) + 1
            draft = CurriculumVersion.objects.create(
                program=program,
                version_number=next_number,
                status=CurriculumVersion.STATUS_DRAFT,
                notes=f'Imported from {spec["file"]}',
            )
            action = 'created'
        else:
            action = 'rebuilt'

        cleared = draft.entries.count()
        draft.entries.all().delete()

        rows = []
        for entry in spec['entries']:
            subject = self._resolve_subject(
                entry, program.code, cache, created_subjects, reused_subjects, conflicts,
            )
            rows.append(Curriculum(
                program=program,
                version=draft,
                year_level=entry['year'],
                semester=entry['semester'],
                subject=subject,
                is_major=True,
            ))
        Curriculum.objects.bulk_create(rows)

        result = approve_curriculum_draft(
            None, draft, effective_from=term,
            notes=f'Imported from {spec["file"]}',
        )

        self.stdout.write(self.style.SUCCESS(
            f'  = {program.code}: draft {action} (cleared {cleared}), '
            f'{len(rows)} entries written, {len(created_subjects)} new subjects, '
            f'{len(reused_subjects)} reused -> {result["message"]}'
        ))
        for code, kept_title, doc_title, program_code in conflicts:
            self.stdout.write(self.style.WARNING(
                f'    ! {code} means "{kept_title}" elsewhere; imported here as '
                f'"{code} ({program_code})" — "{doc_title}"'
            ))
        for code, kept_title, doc_title in self._title_notes[:8]:
            self.stdout.write(
                f'    ~ {code}: kept existing title "{kept_title}" (document: "{doc_title}")'
            )
