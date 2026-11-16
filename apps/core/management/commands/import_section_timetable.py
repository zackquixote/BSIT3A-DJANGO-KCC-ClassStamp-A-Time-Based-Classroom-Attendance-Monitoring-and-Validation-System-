"""
Import a section timetable workbook (one sheet, sections stacked vertically).

The official BSIT workbook lists, per section (BSIT 1A … 4C), every subject with
its faculty, day, time, room, units and weekly hours:

    Code | Description | Faculty | Day | Time | Room | Units | Hrs/Wk

The system models that as one Class per (section, subject) with one ClassSlot per
meeting day, so a lecture+lab pair on two rows becomes two slots of one class.

    python manage.py import_section_timetable --dry-run
    python manage.py import_section_timetable --apply
"""

import datetime
import pathlib
import re
import unicodedata

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.core.models import (
    AcademicYear, Class, ClassSlot, Curriculum, CurriculumVersion, Department, Profile,
    Program, Subject,
)
from apps.core.management.commands.import_curriculum_docs import code_key

User = get_user_model()

DEFAULT_FILE = pathlib.Path('docs/curriculum/BSIT-Final-2026-2027.xlsx')
SECTION_RE = re.compile(r'^(?P<program>[A-Z]{2,8})\s+(?P<year>\d)(?P<section>[A-Z])$')
AY_RE = re.compile(r'A\.Y\.\s*(\d{4}-\d{4})', re.I)
SEM_RE = re.compile(r'(first|second)\s+semester', re.I)
TIME_RE = re.compile(
    r'(\d{1,2}):(\d{2})\s*([AP]M)\s*[-–]\s*(\d{1,2}):(\d{2})\s*([AP]M)', re.I,
)

DAY_INDEX = {'M': 0, 'T': 1, 'W': 2, 'TH': 3, 'F': 4, 'S': 5, 'SU': 6}


def parse_days(text):
    """'MWF' -> [0, 2, 4]; 'TTH' -> [1, 3]; 'MTH' -> [0, 3]."""
    compact = (text or '').upper().replace(' ', '').replace(',', '')
    days, i = [], 0
    while i < len(compact):
        pair = compact[i:i + 2]
        if pair == 'TH':
            days.append(DAY_INDEX['TH']); i += 2
        elif pair == 'SU':
            days.append(DAY_INDEX['SU']); i += 2
        elif compact[i] in DAY_INDEX:
            days.append(DAY_INDEX[compact[i]]); i += 1
        else:
            i += 1
    return sorted(set(days))


def room_code_candidates(label):
    """
    // Workbook room label -> plausible Room.code spellings.

    // The registrar writes 'LAB 1', 'ROOM 203', sometimes with the building
    // appended ('ROOM 302 · CMAT'). Room.code is canonical and hyphenated
    // (LAB-1, RM-203), so both spellings are tried before giving up.
    """
    base = str(label or '').split('\u00b7')[0].strip().upper()
    base = re.sub(r'\s+', ' ', base)
    if not base:
        return []
    candidates = [base, base.replace(' ', '-')]
    if base.startswith('ROOM '):
        tail = base[len('ROOM '):].strip()
        candidates.append(f'RM-{tail.replace(" ", "-")}')
        candidates.append(f'RM {tail}')
    return [value for value in dict.fromkeys(candidates) if value]


def resolve_room(label):
    """
    // Return the Room matching a workbook label, or None.

    // Code spellings first, then an exact name match. None means the label is
    // kept as free text (and reported), never invented as a new Room.
    """
    from apps.core.models import Room

    candidates = room_code_candidates(label)
    if not candidates:
        return None
    room = Room.objects.filter(code__in=candidates).first()
    if room is not None:
        return room
    name = str(label or '').split('\u00b7')[0].strip()
    if name:
        return Room.objects.filter(name__iexact=name).first()
    return None


def parse_time_range(text):
    match = TIME_RE.search(text or '')
    if not match:
        return None
    start_h, start_m, start_ap, end_h, end_m, end_ap = match.groups()

    def to_24(hour, minute, meridiem):
        hour = int(hour) % 12
        if meridiem.upper() == 'PM':
            hour += 12
        return datetime.time(hour, int(minute))

    start = to_24(start_h, start_m, start_ap)
    end = to_24(end_h, end_m, end_ap)
    if end <= start:
        return None
    return start, end


def parse_faculty(name):
    """'Olasa, Godwin Allevson NA' -> ('Olasa', 'Godwin Allevson')."""
    text = (name or '').strip()
    if not text:
        return '', ''
    last, _, rest = text.partition(',')
    rest = re.sub(r'\s+NA\.?$', '', rest.strip(), flags=re.I).strip()
    return last.strip().title(), rest.title()


def name_key(text):
    normalised = unicodedata.normalize('NFKD', text or '')
    ascii_text = normalised.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z]', '', ascii_text.lower())


class Command(BaseCommand):
    help = 'Import a section timetable workbook into Class + ClassSlot records.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE))
        parser.add_argument('--program', default='BSIT')
        parser.add_argument('--apply', action='store_true', help='Write (default: dry run).')
        parser.add_argument('--dry-run', action='store_true', help='Explicit dry run (default).')
        parser.add_argument('--activate', action='store_true',
                            help="Make the workbook's academic year the active term and point "
                                 "the approved curriculum version at it (the matrix reads the "
                                 "active term).")
        parser.add_argument('--no-teachers', action='store_true',
                            help='Skip sections whose faculty cannot be matched (default: create placeholders).')

    # ------------------------------------------------------------------ parsing
    def parse_workbook(self, path):
        from openpyxl import load_workbook

        workbook = load_workbook(path, data_only=True)
        sheet = workbook.worksheets[0]
        sections, current = {}, None
        term_label = None

        for row in range(1, (sheet.max_row or 0) + 1):
            values = [sheet.cell(row=row, column=c).value for c in range(1, 9)]
            first = str(values[0]).strip() if values[0] is not None else ''

            match = SECTION_RE.match(first)
            if match:
                current = f'{match.group("program")} {match.group("year")}{match.group("section")}'
                sections[current] = {'year': int(match.group('year')),
                                     'letter': match.group('section'),
                                     'rows': []}
                continue

            if current is None:
                ay = AY_RE.search(first)
                if ay and term_label is None:
                    semester = SEM_RE.search(first)
                    term_label = (ay.group(1), 2 if semester and semester.group(1).lower() == 'second' else 1)
                continue

            if first.lower().startswith('total'):
                current = None
                continue

            ay = AY_RE.search(first)
            if ay and term_label is None:
                semester = SEM_RE.search(first)
                term_label = (ay.group(1), 2 if semester and semester.group(1).lower() == 'second' else 1)
                continue

            if not first or first.lower() == 'code' or first.upper() == 'SUBJECTS':
                continue

            code = first
            description = str(values[1]).strip() if values[1] else ''
            faculty = str(values[2]).strip() if values[2] else ''
            day = str(values[3]).strip() if values[3] else ''
            time_text = str(values[4]).strip() if values[4] else ''
            room = str(values[5]).strip() if values[5] else ''
            units = values[6]
            hours = values[7]
            if not description or not day:
                continue

            sections[current]['rows'].append({
                'code': code, 'description': description, 'faculty': faculty,
                'day': day, 'time': time_text, 'room': room,
                'units': int(units) if isinstance(units, (int, float)) else 3,
                'hours': hours,
            })

        workbook.close()
        return sections, term_label

    # ------------------------------------------------------------------- handle
    def handle(self, *args, **options):
        path = pathlib.Path(options['file'])
        if not path.exists():
            raise CommandError(f'Workbook not found: {path}')

        program_code = options['program'].upper()
        apply_changes = options['apply']
        sections, term_label = self.parse_workbook(path)
        if not sections:
            raise CommandError('No sections were found in the workbook.')

        # group rows into one class per (section, code) — lecture + lab rows share it
        planned = []
        for section_name, payload in sections.items():
            grouped = {}
            for row in payload['rows']:
                key = code_key(row['code'])
                grouped.setdefault(key, []).append(row)
            for key, rows in grouped.items():
                first = rows[0]
                planned.append({
                    'section': section_name,
                    'year': payload['year'],
                    'letter': payload['letter'],
                    'code': first['code'],
                    'key': key,
                    'description': first['description'],
                    'units': first['units'],
                    'faculty': first['faculty'],
                    'meetings': [r for r in rows if parse_time_range(r['time']) and parse_days(r['day'])],
                })

        meetings = sum(len(p['meetings']) for p in planned)
        slot_count = sum(
            len(parse_days(m['day'])) for p in planned for m in p['meetings']
        )
        faculty_names = sorted({p['faculty'] for p in planned if p['faculty']})
        mode = 'APPLY' if apply_changes else 'DRY RUN'
        self.stdout.write(self.style.MIGRATE_HEADING(f'=== Section timetable import ({mode}) ==='))
        self.stdout.write(f'source      : {path.name}')
        self.stdout.write(f'programme   : {program_code}')
        self.stdout.write(f'term in file: {term_label[0]} semester {term_label[1]}' if term_label else 'term in file: (not stated)')
        self.stdout.write(f'sections    : {len(sections)}')
        self.stdout.write(f'classes     : {len(planned)} (from {sum(len(v["rows"]) for v in sections.values())} subject rows)')
        self.stdout.write(f'meetings    : {meetings} rows -> {slot_count} weekly slots')
        self.stdout.write(f'faculty     : {len(faculty_names)} unique')

        if not apply_changes:
            known = self._known_teacher_names()
            matched = [n for n in faculty_names if self._looks_like_known(n, known)]
            missing = [n for n in faculty_names if n not in matched]
            self.stdout.write(f'faculty ok  : {len(matched)} matched to existing accounts')
            if missing:
                self.stdout.write(f'faculty new : {len(missing)} would be created inactive:')
                for name in missing[:10]:
                    self.stdout.write(f'    + {name}')
                if len(missing) > 10:
                    self.stdout.write(f'    … and {len(missing) - 10} more')

        if not apply_changes:
            self.stdout.write('\nFirst 8 planned classes:')
            for item in planned[:8]:
                self.stdout.write(
                    f'  {item["section"]:9s} {item["code"]:16s} {item["faculty"][:28]:28s} '
                    f'{len(item["meetings"])} slot(s)'
                )
            self.stdout.write(self.style.WARNING('\nDry run only. Re-run with --apply to write.'))
            return

        self._apply(program_code, planned, term_label, options['no_teachers'],
                    options['activate'])

    # ----------------------------------------------------------------- subject
    @staticmethod
    def _subject_index(program):
        """
        Normalised code -> Subject, preferring the version the matrix displays.

        The catalogue holds both 'CC101' and 'CC 101' (and nine more such pairs). The
        approved curriculum references the unspaced row, so resolving by raw code made
        every class point at the twin subject and the matrix still showed no faculty.
        """
        index = {}
        rows = (
            Curriculum.objects
            .filter(program=program)
            .exclude(version__isnull=True)
            .select_related('subject', 'version')
        )
        ranked = sorted(
            rows,
            key=lambda row: (
                0 if getattr(row.version, 'status', None) == 'APPROVED' else 1,
                -(getattr(row.version, 'version_number', None) or 0),
                -(row.version_id or 0),
            ),
        )
        for row in ranked:
            if row.subject is not None:
                index.setdefault(code_key(row.subject.code), row.subject)
        return index

    # -------------------------------------------------------------------- apply
    def _apply(self, program_code, planned, term_label, no_teachers, activate=False):
        program = Program.objects.filter(code=program_code).first()
        if program is None:
            raise CommandError(f'Program {program_code} does not exist.')

        if term_label:
            term_name = f'{term_label[0]} {term_label[1]}st Sem' if term_label[1] == 1 else f'{term_label[0]} 2nd Sem'
            start_year = int(term_label[0].split('-')[0])
            term, term_created = AcademicYear.objects.get_or_create(
                name=term_name,
                defaults={
                    'starts_on': datetime.date(start_year, 8, 1),
                    'ends_on': datetime.date(start_year + 1, 5, 31),
                    'is_active': False,
                },
            )
        else:
            term = AcademicYear.objects.filter(is_active=True).first()
            if term is None:
                raise CommandError('No active academic year and none stated in the workbook.')
            term_created = False

        self.stdout.write(f'\nterm        : {term.name}' + (' (created)' if term_created else ''))

        if activate:
            # The Curriculum Matrix only reads the active term, so a timetable filed
            # under a dormant year is invisible until this flips.
            AcademicYear.objects.exclude(pk=term.pk).update(is_active=False)
            AcademicYear.objects.filter(pk=term.pk).update(is_active=True)
            repointed = 0
            for version in CurriculumVersion.objects.filter(
                program=program, status=CurriculumVersion.STATUS_APPROVED,
            ).exclude(effective_from=term):
                version.effective_from = term
                version.save(update_fields=['effective_from'])
                repointed += 1
            self.stdout.write(f'activated   : {term.name} is now the active term'
                              + (f'; {repointed} approved curriculum version(s) repointed'
                                 if repointed else ''))

        teacher_cache, created_teachers, matched_teachers = {}, [], []
        for name in sorted({p['faculty'] for p in planned if p['faculty']}):
            profile = self._resolve_teacher(name, created_teachers, matched_teachers, teacher_cache)
            if profile is None and no_teachers:
                raise CommandError(f'Faculty not found and --no-teachers was given: {name}')

        subject_index = self._subject_index(program)
        subject_cache, created_subjects, repaired_classes = {}, [], []
        created_classes, skipped_classes, created_slots = 0, 0, 0
        skipped_slots, room_conflicts, refreshed_slots = [], [], []
        unmatched_rooms = set()
        occupied = list(
            ClassSlot.objects
            .filter(class_obj__academic_year=term, is_active=True)
            .values('class_obj_id', 'weekday', 'starts_at', 'ends_at',
                    'class_obj__teacher_profile_id', 'room')
        )
        occupied = [
            {'class_id': row['class_obj_id'], 'weekday': row['weekday'], 'start': row['starts_at'],
             'end': row['ends_at'], 'teacher_id': row['class_obj__teacher_profile_id'],
             'room': row['room']}
            for row in occupied
        ]

        with transaction.atomic():
            for item in planned:
                subject = subject_cache.get(item['key'])
                if subject is None:
                    subject = subject_index.get(item['key'])
                if subject is None:
                    subject = Subject.objects.filter(code__iexact=item['code']).first()
                    if subject is None:
                        subject = Subject.objects.create(
                            code=item['code'][:40],
                            name=item['description'][:150],
                            units=item['units'],
                            is_active=True,
                        )
                        created_subjects.append(item['code'])
                    subject_cache[item['key']] = subject

                profile = teacher_cache.get(name_key(item['faculty']))
                if profile is None:
                    profile = self._resolve_teacher(item['faculty'], created_teachers, matched_teachers, teacher_cache)
                if profile is None:
                    self.stdout.write(self.style.WARNING(f'  ! {item["section"]} {item["code"]}: no faculty, skipped'))
                    continue

                class_code = f'{program_code}-{item["year"]}{item["letter"]}-{slugify(item["code"]).upper()}'[:40]
                class_obj, created = Class.objects.get_or_create(
                    academic_year=term,
                    class_code=class_code,
                    defaults={
                        'section_code': f'{program_code}-{item["year"]}{item["letter"]}',
                        'subject': subject,
                        'teacher_profile': profile,
                        'program': program,
                        'year_level': item['year'],
                        'grace_minutes': 10,
                        'is_active': True,
                    },
                )
                if created:
                    created_classes += 1
                else:
                    skipped_classes += 1
                    if subject and class_obj.subject_id != subject.id:
                        class_obj.subject = subject
                        class_obj.save(update_fields=['subject'])
                        repaired_classes.append(class_code)

                for meeting in item['meetings']:
                    span = parse_time_range(meeting['time'])
                    days = parse_days(meeting['day'])
                    if span is None:
                        continue
                    starts_at, ends_at = span
                    room_label = ' '.join((meeting['room'] or '').split())[:100]
                    room_obj = resolve_room(room_label)
                    if room_label and room_obj is None:
                        unmatched_rooms.add(room_label)
                    # Store the canonical code when the label resolves, so the
                    # sheet, the room directory and the conflict check agree.
                    room = room_obj.code if room_obj is not None else room_label
                    slot_type = (
                        ClassSlot.SLOT_TYPE_LABORATORY
                        if (
                            (subject is not None and subject.is_lab)
                            or (room_obj is not None and room_obj.is_lab)
                        )
                        else ClassSlot.SLOT_TYPE_LECTURE
                    )
                    for weekday in days:
                        existing = ClassSlot.objects.filter(
                            class_obj=class_obj, weekday=weekday, starts_at=starts_at,
                        ).first()
                        if existing is not None:
                            # Already imported: refresh the room label only when
                            # the workbook spells it differently and the room is
                            # free. The FK and slot type always follow the file.
                            changed = []
                            relabel = False
                            # One clash check governs both the label and the FK:
                            # binding a room that another class already holds
                            # would let save() overwrite the text back to it.
                            room_allowed = True
                            if room:
                                room_allowed = self._clash(
                                    occupied, weekday, starts_at, ends_at,
                                    profile.pk, room, class_obj.pk,
                                ) != 'room'
                            if room_allowed and room and existing.room != room:
                                existing.room = room
                                relabel = True
                                changed.append('room')
                            if (
                                room_allowed
                                and room_obj is not None
                                and existing.room_ref_id != room_obj.pk
                            ):
                                existing.room_ref = room_obj
                                changed.append('room_ref')
                            if existing.slot_type != slot_type:
                                existing.slot_type = slot_type
                                changed.append('slot_type')
                            if existing.ends_at != ends_at:
                                existing.ends_at = ends_at
                                changed.append('ends_at')
                            if changed:
                                existing.save(update_fields=changed + ['updated_at'])
                            if relabel:
                                refreshed_slots.append(f'{item["section"]} {item["code"]} '
                                                       f'day {weekday} -> {room}')
                                for row in occupied:
                                    if (row['class_id'] == class_obj.pk
                                            and row['weekday'] == weekday
                                            and row['start'] == starts_at):
                                        row['room'] = room
                            continue
                        if self._clash(occupied, weekday, starts_at, ends_at, profile.pk, '',
                                       class_obj.pk) == 'teacher':
                            skipped_slots.append(
                                f'{item["section"]} {item["code"]} — teacher already booked '
                                f'(day {weekday}, {starts_at}-{ends_at})'
                            )
                            continue
                        slot_room = room
                        if slot_room and self._clash(occupied, weekday, starts_at, ends_at,
                                                     profile.pk, slot_room, class_obj.pk) == 'room':
                            room_conflicts.append(
                                f'{item["section"]} {item["code"]} — {slot_room} already taken '
                                f'(day {weekday}, {starts_at}-{ends_at}); room omitted'
                            )
                            slot_room = ''
                        _, slot_created = ClassSlot.objects.get_or_create(
                            class_obj=class_obj,
                            weekday=weekday,
                            starts_at=starts_at,
                            defaults={
                                'ends_at': ends_at,
                                'room': slot_room,
                                # Blanking the room on a conflict must blank the
                                # FK too, or save() would put the code back.
                                'room_ref': room_obj if slot_room else None,
                                'slot_type': slot_type,
                                'is_active': True,
                            },
                        )
                        if slot_created:
                            created_slots += 1
                        occupied.append({'class_id': class_obj.pk, 'weekday': weekday,
                                         'start': starts_at, 'end': ends_at,
                                         'teacher_id': profile.pk, 'room': slot_room})

        self.stdout.write(self.style.SUCCESS(
            f'\nclasses  : {created_classes} created, {skipped_classes} already existed'
        ))
        self.stdout.write(f'slots    : {created_slots} created'
                          + (f', {len(refreshed_slots)} room label(s) refreshed'
                             if refreshed_slots else ''))
        if repaired_classes:
            self.stdout.write(f'repaired : {len(repaired_classes)} class(es) relinked to the '
                              f'approved-curriculum subject row')
        self.stdout.write(f'subjects : {len(created_subjects)} created ({", ".join(created_subjects[:8])}'
                          f'{"…" if len(created_subjects) > 8 else ""})')
        self.stdout.write(f'teachers : {len(matched_teachers)} matched, {len(created_teachers)} placeholder(s) created')
        for name in created_teachers:
            self.stdout.write(self.style.WARNING(f'  + {name} (inactive placeholder — add Faculty ID and email)'))
        if unmatched_rooms:
            self.stdout.write(self.style.WARNING(
                f'\nunmatched rooms: {len(unmatched_rooms)} label(s) have no Room record '
                f'(kept as text — add them in Room Directory)'
            ))
            for label in sorted(unmatched_rooms):
                self.stdout.write(f'  ? {label}')
        if room_conflicts:
            self.stdout.write(self.style.WARNING(
                f'\nroom conflicts: {len(room_conflicts)} (slot kept, room left blank)'
            ))
            for line in room_conflicts:
                self.stdout.write(f'  ! {line}')
        if skipped_slots:
            self.stdout.write(self.style.WARNING(f'\nskipped slots: {len(skipped_slots)}'))
            for line in skipped_slots[:10]:
                self.stdout.write(f'  - {line}')

    # ------------------------------------------------------------------- clash
    @staticmethod
    def _clash(occupied, weekday, starts_at, ends_at, teacher_id, room, class_id=None):
        """Mirror the tblcs_class_slot trigger so the import never trips it."""
        overlaps = [
            slot for slot in occupied
            if slot['weekday'] == weekday
            and slot['start'] < ends_at and slot['end'] > starts_at
            and (class_id is None or slot['class_id'] != class_id)
        ]
        if any(slot['teacher_id'] == teacher_id for slot in overlaps):
            return 'teacher'
        if room and any(slot['room'] == room for slot in overlaps):
            return 'room'
        return None

    # ------------------------------------------------------------------ teacher
    @staticmethod
    def _known_teacher_names():
        return [
            (name_key(p.user.last_name), name_key(p.user.first_name))
            for p in Profile.objects.filter(role=Profile.ROLE_TEACHER).select_related('user')
        ]

    @staticmethod
    def _looks_like_known(raw_name, known):
        last, first = parse_faculty(raw_name)
        last_key, first_key = name_key(last), name_key(first)
        return any(
            known_last == last_key and known_first.startswith(first_key[:4])
            for known_last, known_first in known
            if last_key and known_last
        )

    def _resolve_teacher(self, raw_name, created, matched, cache):
        key = name_key(raw_name)
        if not key:
            return None
        if key in cache:
            return cache[key]

        last, first = parse_faculty(raw_name)
        last_key, first_key = name_key(last), name_key(first)

        for profile in Profile.objects.filter(role=Profile.ROLE_TEACHER).select_related('user'):
            user = profile.user
            if name_key(user.last_name) == last_key and name_key(user.first_name).startswith(first_key[:4]):
                cache[key] = profile
                matched.append(raw_name)
                return profile

        counter = Profile.objects.filter(employee_number__startswith='FAC-TMP-').count() + 1
        while True:
            username = slugify(f'{first}.{last}')[:24] or f'faculty{counter}'
            if not User.objects.filter(username=username).exists():
                break
            username = f'{username}{counter}'
            counter += 1

        user = User.objects.create_user(username=username, password=None)
        user.first_name = first[:150]
        user.last_name = last[:150]
        user.is_active = False
        user.save(update_fields=['first_name', 'last_name', 'is_active'])

        profile = Profile.objects.create(
            user=user,
            role=Profile.ROLE_TEACHER,
            employee_number=f'FAC-TMP-{counter:03d}',
        )
        cache[key] = profile
        created.append(f'{first} {last}')
        return profile
