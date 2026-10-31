"""
# // ==============================================================================
# // KCC CLASSSTAMP - SCHEDULE & TIMETABLE SERVICE
# // ==============================================================================
# // Subsystem: Timetable Conflict Detection & Section Planning (A-19 Phase 2)
# // Description: Pure scheduling logic used by both the legacy slot modal and
# //   the Section Builder wizard:
# //   - validate_slot_times      — rejects empty/inverted time windows
# //   - detect_slot_conflicts    — interval-overlap scan for teacher/room clashes
# //   - suggest_section_letter   — probes the next free section letter (A/B/C…)
# //   - eligible_teachers_for    — department-scoped teacher list ranked by load
# // Overlap rule: two windows clash iff s1.start < s2.end AND s2.start < s1.end
# //   (boundary-touching windows do NOT clash).
# // ==============================================================================
"""

from django.db.models import Count, Q

from apps.core.models import Class, ClassSlot, Profile

SECTION_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def validate_slot_times(starts_at, ends_at):
    """
    // Raises ValueError when the window is empty or inverted.
    """
    if starts_at is None or ends_at is None:
        raise ValueError('Both start and end times are required.')
    if starts_at >= ends_at:
        raise ValueError('End time must be after the start time.')


def detect_slot_conflicts(
    *, teacher_profile_id, weekday, starts_at, ends_at,
    room=None, exclude_slot_ids=(), academic_year=None,
):
    """
    // [Service] Returns a list of conflict dicts for a proposed weekly slot.
    //
    // Each dict: {type: 'teacher'|'room', class_code, weekday, starts_at,
    //             ends_at, room, teacher_name}
    // Teacher clashes are detected unconditionally; room clashes only when a
    // real room is proposed (empty or 'TBA' rooms never clash). Inactive slots,
    // inactive classes, and slots in exclude_slot_ids are ignored. When an
    // academic year is supplied, only that year's timetable is considered so a
    // prior or future term cannot produce a false conflict.
    """
    validate_slot_times(starts_at, ends_at)

    overlapping = (
        ClassSlot.objects
        .filter(
            weekday=weekday,
            is_active=True,
            class_obj__is_active=True,
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
        )
        .exclude(id__in=list(exclude_slot_ids))
        .select_related('class_obj__teacher_profile__user')
    )
    if academic_year is not None:
        overlapping = overlapping.filter(class_obj__academic_year=academic_year)

    proposed_room = (room or '').strip().lower()
    check_room = bool(proposed_room) and proposed_room != 'tba'

    conflicts = []
    for slot in overlapping:
        if slot.class_obj.teacher_profile_id == teacher_profile_id:
            conflicts.append(_conflict_dict(slot, 'teacher'))
        elif check_room and (slot.room or '').strip().lower() == proposed_room:
            conflicts.append(_conflict_dict(slot, 'room'))
    return conflicts


def _conflict_dict(slot, kind):
    teacher = slot.class_obj.teacher_profile
    teacher_name = ''
    if teacher is not None:
        teacher_name = teacher.user.get_full_name() or teacher.user.username
    return {
        'type': kind,
        'class_code': slot.class_obj.class_code,
        'weekday': slot.weekday,
        'starts_at': slot.starts_at.strftime('%H:%M'),
        'ends_at': slot.ends_at.strftime('%H:%M'),
        'room': slot.room,
        'teacher_name': teacher_name,
    }


def suggest_section_letter(*, academic_year, program, year_level):
    """
    // [Service] Probes for the next free section letter, e.g. BSIT-3A, BSIT-3B…
    // Collision check is by exact class_code within the academic year, so both
    // wizard-created and legacy (unbackfilled) codes are respected.
    """
    if program is None:
        raise ValueError('A program is required to suggest a section code.')
    if year_level is None:
        raise ValueError('A year level is required to suggest a section code.')

    prefix = f'{program.code.upper()}-{year_level}'
    for letter in SECTION_LETTERS:
        candidate = f'{prefix}{letter}'
        if not Class.objects.filter(
            academic_year=academic_year, class_code=candidate,
        ).exists():
            return candidate
    raise ValueError(
        f'No free section letters remain for {prefix} in {academic_year.name}.'
    )


def eligible_teachers_for(program):
    """
    // [Service] Active teachers in the program's department, ranked by current
    // weekly teaching load (lightest first). Returns a list of dicts:
    //   {profile_id, name, department_code, active_classes, active_slots}
    """
    if program is None:
        raise ValueError('A program is required to list eligible teachers.')

    teachers = (
        Profile.objects
        .filter(
            role=Profile.ROLE_TEACHER,
            user__is_active=True,
            department_id=program.department_id,
        )
        .select_related('user', 'department')
        .annotate(
            active_classes=Count(
                'taught_classes',
                filter=Q(taught_classes__is_active=True),
                distinct=True,
            ),
            active_slots=Count(
                'taught_classes__slots',
                filter=Q(
                    taught_classes__is_active=True,
                    taught_classes__slots__is_active=True,
                ),
                distinct=True,
            ),
        )
        .order_by('active_slots', 'user__last_name', 'user__first_name')
    )

    return [
        {
            'profile_id': teacher.pk,
            'name': teacher.user.get_full_name() or teacher.user.username,
            'department_code': teacher.department.code if teacher.department else None,
            'active_classes': teacher.active_classes,
            'active_slots': teacher.active_slots,
        }
        for teacher in teachers
    ]
