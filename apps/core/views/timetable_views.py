"""
Section timetable sheet — mirrors the registrar's official workbook layout.

Each section renders as one sheet:

    Bachelor of Science in Information Technology | First Semester, A.Y. 2026-2027 | 25 units, 9 subjects
    SUBJECTS
    Code | Description | Faculty | Day | Time | Room | Units | Hrs/Wk
    ...
    Total — 9 subjects | 25 units | 29

A class with a lecture meeting and a separate laboratory meeting therefore shows
two rows, exactly like the spreadsheet (e.g. CC 101 on MT and again on W).

The same context also feeds the .xlsx export, so the screen, the printout and the
downloaded workbook can never disagree.
"""

import datetime
import re

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from apps.core.decorators import role_required
from apps.core.models import AcademicYear, Class, ClassSlot, Department, Profile, Program
from apps.core.services.academic_service import format_subject_code

WEEKDAY_TOKENS = ('M', 'T', 'W', 'TH', 'F', 'S', 'SU')
DAY_WORDS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')


def normalize_section(text):
    """'BSIT 1A', 'BSIT-1A' and 'bsit1a' all compare equal."""
    return re.sub(r'[^A-Za-z0-9]', '', str(text or '')).lower()


# Shared with the Curriculum Matrix so both views spell codes identically.
display_code = format_subject_code


def display_section(code):
    """Stored 'BSIT-1A' is printed the way the workbook writes it: 'BSIT 1A'."""
    text = str(code or '')
    if '-' in text:
        prefix, _, rest = text.partition('-')
        if prefix.isalpha():
            return f'{prefix} {rest}'
    return text


def academic_year_label(name):
    """'2026-2027 1st Sem' -> '2026-2027' (the sheet prints the school year only)."""
    parts = str(name or '').split()
    return parts[0] if parts else ''


def semester_label_for(term):
    """Readable semester name for the sheet caption."""
    if term is None:
        return ''
    if '2nd' in term.name:
        return 'Second Semester'
    if 'Summer' in term.name:
        return 'Summer'
    return 'First Semester'


def format_days(weekdays):
    """[0, 2, 4] -> 'MWF'; [1, 3] -> 'TTH'; [6] -> 'SU'."""
    return ''.join(WEEKDAY_TOKENS[day] for day in sorted(weekdays) if 0 <= day < 7)


def format_clock(value):
    """datetime.time(13, 0) -> '1:00 PM'."""
    hour = value.hour % 12 or 12
    meridiem = 'AM' if value.hour < 12 else 'PM'
    return f'{hour}:{value.minute:02d} {meridiem}'


def format_hours(hours):
    """3.0 -> '3'; 1.5 -> '1.5'."""
    return str(int(hours)) if float(hours).is_integer() else f'{hours:g}'


def build_meeting_rows(class_obj):
    """
    One row per distinct meeting (day-set + time + room), in schedule order.

    Slots that share a time and room are the same class meeting on several days,
    so they collapse into a single row such as 'MWF | 8:30 AM - 9:30 AM'.
    """
    grouped = {}
    for slot in class_obj.slots.all():
        if not slot.is_active:
            continue
        key = (slot.starts_at, slot.ends_at, slot.room or '')
        grouped.setdefault(key, []).append(slot.weekday)

    rows = []
    for (starts_at, ends_at, room), weekdays in grouped.items():
        span = (
            datetime.datetime.combine(datetime.date.today(), ends_at)
            - datetime.datetime.combine(datetime.date.today(), starts_at)
        )
        duration = span.total_seconds() / 3600
        # 'ROOM 302 · CMAT' is stored as one label; split it so the building sits
        # on its own small line instead of wrapping mid-token.
        room_main, _, room_building = room.partition('·')
        rows.append({
            'days': format_days(weekdays),
            'days_long': ', '.join(DAY_WORDS[d] for d in sorted(weekdays) if d < 7),
            'time': f'{format_clock(starts_at)} - {format_clock(ends_at)}',
            'room': room or '—',
            'room_main': room_main.strip() or '—',
            'room_building': room_building.strip(),
            'hours_per_week': duration * len(weekdays),
            'sort_key': (min(weekdays), starts_at),
        })

    rows.sort(key=lambda row: row['sort_key'])
    for row in rows:
        row['hours_label'] = format_hours(row['hours_per_week'])
    return rows


def build_section_sheet(section_code, classes):
    """Assemble one section block: header, subject rows and totals."""
    classes = sorted(classes, key=lambda c: (c.subject.code if c.subject else ''))
    subject_rows = []
    seen_subjects = {}

    for class_obj in classes:
        subject = class_obj.subject
        if subject is None:
            continue
        teacher = class_obj.teacher_profile
        faculty = ''
        if teacher is not None:
            faculty = teacher.user.get_full_name().strip() or teacher.user.username

        meetings = build_meeting_rows(class_obj)
        if not meetings:
            subject_rows.append({
                'code': display_code(subject.code),
                'description': subject.name,
                'faculty': faculty or '— unassigned',
                'days': '—',
                'time': '—',
                'room': '—',
                'room_main': '—',
                'room_building': '',
                'units': subject.units,
                'hours_label': '0',
                'hours_per_week': 0,
                'has_schedule': False,
            })
            seen_subjects.setdefault(subject.id, subject.units)
            continue

        for meeting in meetings:
            subject_rows.append({
                'code': display_code(subject.code),
                'description': subject.name,
                'faculty': faculty or '— unassigned',
                'days': meeting['days'],
                'days_long': meeting['days_long'],
                'time': meeting['time'],
                'room': meeting['room'],
                'room_main': meeting['room_main'],
                'room_building': meeting['room_building'],
                'units': subject.units,
                'hours_label': meeting['hours_label'],
                'hours_per_week': meeting['hours_per_week'],
                'has_schedule': True,
            })
        seen_subjects.setdefault(subject.id, subject.units)

    total_hours = sum(row['hours_per_week'] for row in subject_rows)
    return {
        'section': display_section(section_code),
        'section_code': section_code,
        'rows': subject_rows,
        'subject_count': len(seen_subjects),
        'total_units': sum(seen_subjects.values()),
        'total_hours': total_hours,
        'total_hours_label': format_hours(total_hours),
        'caption': (
            f'{len(seen_subjects)} subjects' if not seen_subjects
            else f'{sum(seen_subjects.values())} units, {len(seen_subjects)} subjects'
        ),
    }


def section_sort_key(name):
    """'BSIT 1A' sorts before 'BSIT 2A'."""
    digits = ''.join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 0, name)


def _classes_in_scope(term, program):
    classes_qs = (
        Class.objects
        .filter(is_active=True)
        .select_related('subject', 'teacher_profile__user', 'program')
        .prefetch_related('slots')
        .order_by('section_code', 'subject__code')
    )
    if term is not None:
        classes_qs = classes_qs.filter(academic_year=term)
    if program is not None:
        classes_qs = classes_qs.filter(program=program)
    return classes_qs


def build_occupancy(term, mode):
    """
    Weekly occupancy rows for the Room and Teacher views.

    mode='rooms' groups active slots by canonical room (room_ref code, falling
    back to the legacy string). mode='teachers' groups by the assigned
    instructor. Each row is one room or teacher with seven day columns of
    meeting pills, so a registrar can see where a new section can physically
    go without opening every section sheet.
    """
    if mode not in ('rooms', 'teachers'):
        return []

    slots = (
        ClassSlot.objects
        .filter(is_active=True, class_obj__is_active=True)
        .select_related(
            'class_obj__subject',
            'class_obj__teacher_profile__user',
            'room_ref',
        )
    )
    if term is not None:
        slots = slots.filter(class_obj__academic_year=term)

    groups = {}
    for slot in slots:
        teacher = slot.class_obj.teacher_profile
        teacher_name = ''
        if teacher is not None:
            teacher_name = teacher.user.get_full_name() or teacher.user.username
        subject_code = slot.class_obj.subject.code if slot.class_obj.subject_id else ''
        class_code = slot.class_obj.class_code
        room_label = slot.room_ref.code if slot.room_ref else (slot.room or 'TBA')

        if mode == 'rooms':
            key = (slot.room_ref.code if slot.room_ref else (slot.room or '')).strip().upper() or 'TBA'
            label = key
            sublabel = slot.room_ref.name if slot.room_ref else ''
        else:
            if teacher is None:
                key, label, sublabel = '0', 'Unassigned', ''
            else:
                key = str(teacher.pk)
                label = teacher_name
                sublabel = teacher.department.code if teacher.department_id else ''

        groups.setdefault(key, {'label': label, 'sublabel': sublabel, 'cells': []})
        groups[key]['cells'].append({
            'weekday': slot.weekday,
            'time': f'{format_clock(slot.starts_at)} – {format_clock(slot.ends_at)}',
            'starts_at': slot.starts_at,
            'class_code': class_code,
            'subject': subject_code,
            'room': room_label,
            'teacher': teacher_name,
        })

    rows = []
    for key in sorted(groups, key=lambda k: groups[k]['label'].lower()):
        group = groups[key]
        days = [[] for _ in range(7)]
        for cell in group['cells']:
            days[cell['weekday']].append(cell)
        for day_cells in days:
            day_cells.sort(key=lambda c: (c['starts_at'], c['ends_at']))
        rows.append({
            'label': group['label'],
            'sublabel': group['sublabel'],
            'slot_count': len(group['cells']),
            'days': [
                {'name': name, 'cells': days[i]}
                for i, name in enumerate(('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'))
            ],
        })
    return rows


def build_timetable_context(request):
    """
    Resolve filters and build every sheet.

    Every program in the catalogue is selectable: one with no imported timetable
    simply returns an empty sheet list plus `no_data_reason`, so the page, the
    printout and the workbook all stay consistent instead of 404-ing.
    """
    ay_param = request.GET.get('ay', '').strip()
    program_param = request.GET.get('program', '').strip()
    department_param = request.GET.get('department', '').strip()
    section_param = request.GET.get('section', '').strip()

    all_terms = list(AcademicYear.objects.order_by('-starts_on'))
    active_ay = next((t for t in all_terms if t.is_active), None)

    terms_with_classes = set(
        Class.objects.filter(is_active=True).values_list('academic_year_id', flat=True)
    )
    terms = [t for t in all_terms if t.pk in terms_with_classes or t.is_active]
    if not terms:
        terms = all_terms

    if ay_param.isdigit():
        term = next((t for t in terms if t.pk == int(ay_param)), None) or active_ay
    else:
        term = active_ay or (terms[0] if terms else None)

    programmes = list(Program.objects.select_related('department').order_by('code'))
    departments = list(Department.objects.order_by('code'))

    # Department -> Program -> Section. A program outside the chosen department is
    # ignored, so switching department always resets the program instead of mixing
    # CEAS and CMAT courses in one list.
    department = None
    if department_param:
        department = next(
            (d for d in departments if d.code.lower() == department_param.lower()), None
        )

    program = None
    if program_param:
        program = next((p for p in programmes if p.code.lower() == program_param.lower()), None)
        if program is not None and department is not None and program.department_id != department.id:
            program = None  # stale program from another department

    terms_with_data = set(
        _classes_in_scope(term, None).exclude(program__isnull=True)
        .values_list('program_id', flat=True)
    )

    if program is None:
        # Keep the department honest: only consider its own programs.
        candidates = [p for p in programmes if department is None or p.department_id == department.id]
        with_data = [p for p in candidates if p.id in terms_with_data]
        pool = with_data or candidates
        if pool:
            program = pool[0]
    if program is not None and department is None:
        department = program.department

    # The program list only offers what belongs to the chosen department.
    if department is not None:
        programs = [p for p in programmes if p.department_id == department.id]
    else:
        programs = programmes

    classes_qs = _classes_in_scope(term, program)
    if program is None and department is not None:
        # No program resolved (the department has none yet): still never show
        # another department's timetable under this filter.
        classes_qs = classes_qs.filter(program__department=department)
    grouped = {}
    for class_obj in classes_qs:
        grouped.setdefault(class_obj.section_code or 'UNASSIGNED', []).append(class_obj)

    section_options = [
        {'value': name, 'label': display_section(name)}
        for name in sorted(grouped.keys(), key=section_sort_key)
    ]

    if section_param:
        wanted = normalize_section(section_param)
        grouped = {k: v for k, v in grouped.items() if normalize_section(k) == wanted}

    sheets = [
        build_section_sheet(name, grouped[name])
        for name in sorted(grouped.keys(), key=section_sort_key)
    ]

    grand = {
        'sections': len(sheets),
        'subjects': sum(sheet['subject_count'] for sheet in sheets),
        'units': sum(sheet['total_units'] for sheet in sheets),
        'hours': sum(sheet['total_hours'] for sheet in sheets),
    }

    no_data_reason = ''
    if not sheets:
        if program is None:
            no_data_reason = 'No timetable is on file for any program in this term.'
        elif section_param:
            no_data_reason = (
                f'Section "{section_param}" is not on file for {program.code}. '
                f'Choose "All sections" to see everything.'
            )
        else:
            # The template already lists the programs that do have one, so the
            # reason stays short instead of repeating the same sentence.
            no_data_reason = (
                f'No timetable is on file for {program.code} in '
                f'{term.name if term else "—"}.'
            )

    view_param = request.GET.get('view', 'sections').strip().lower()
    if view_param not in ('sections', 'rooms', 'teachers'):
        view_param = 'sections'

    base_qs = request.GET.copy()
    if 'view' in base_qs:
        del base_qs['view']
    base_query = base_qs.urlencode()

    occupancy = []
    if view_param in ('rooms', 'teachers'):
        occupancy = build_occupancy(term, view_param)

    return {
        'sheets': sheets if view_param == 'sections' else [],
        'view_mode': view_param,
        'occupancy': occupancy,
        'base_query': base_query,
        'term': term,
        'semester_label': semester_label_for(term),
        'academic_year_label': academic_year_label(term.name) if term else '',
        'department': department,
        'departments': departments,
        'department_filter': department_param,
        'program': program,
        'programs': programs,
        'terms': terms,
        'sections': section_options,
        'section_filter': section_param,
        'grand': grand,
        'no_data_reason': no_data_reason,
        'query_string': request.GET.urlencode() if hasattr(request.GET, 'urlencode') else '',
    }


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def section_timetable(request):
    """Read-only timetable sheet per section, laid out like the registrar's workbook."""
    return render(request, 'core/admin/section_timetable.html', build_timetable_context(request))


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def section_timetable_export(request):
    """Download the same sheets as an .xlsx workbook, matching the registrar's file."""
    from apps.core.services.timetable_export import build_timetable_workbook

    context = build_timetable_context(request)
    workbook = build_timetable_workbook(context)

    program_code = context['program'].code if context['program'] else 'TIMETABLE'
    year_label = context['academic_year_label'] or 'Term'
    filename = f'{program_code}-Section-Timetable-{year_label}.xlsx'.replace(' ', '-')

    response = HttpResponse(
        workbook,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
