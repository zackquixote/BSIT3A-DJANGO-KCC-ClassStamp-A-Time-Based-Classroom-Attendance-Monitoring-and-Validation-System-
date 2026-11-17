# Generated manually for KCC ClassStamp - seed the campus rooms the registrar
# timetable actually books, and backfill ClassSlot.room_ref for every slot that
# still carries a raw workbook label.
#
# Why: half the 2026-2027 timetable meets in rooms the Room Directory never
# had ('LAB 7', 'ROOM 301 · CMAT', 'GYM', 'ROOM 112 · HS', ...). The importer
# deliberately keeps unmatched labels as text, so those slots stayed invisible
# to the room picker, slot counts, delete protection and conflict detection.
# This migration adds the real rooms and binds the labels to them, mirroring
# migration 0034 (which did the same for the Main Building set).

from django.db import migrations


# Only current Room fields are used (0035 dropped building/floor). Capacities
# are conservative registrar defaults - adjust them in the Room Directory as
# measured.
SEEDED_ROOMS = [
    # Computer Laboratory (the timetable books seven labs; 0034 seeded six)
    {"code": "LAB-7", "name": "Computer Laboratory 7", "room_type": "LABORATORY",
     "capacity": 40, "notes": "40 Desktop workstations, Gigabit LAN, Projector"},

    # CMAT building rooms share the canonical RM-### code space - the importer's
    # ROOM_MAP_ALLOWED_BUILDINGS already treats 'ROOM 301 · CMAT' as RM-301.
    {"code": "RM-301", "name": "Room 301 (CMAT)", "room_type": "LECTURE",
     "capacity": 45, "notes": "CMAT building"},
    {"code": "RM-302", "name": "Room 302 (CMAT)", "room_type": "LECTURE",
     "capacity": 45, "notes": "CMAT building"},
    {"code": "RM-303", "name": "Room 303 (CMAT)", "room_type": "LECTURE",
     "capacity": 45, "notes": "CMAT building"},
    {"code": "RM-304", "name": "Room 304 (CMAT)", "room_type": "LECTURE",
     "capacity": 45, "notes": "CMAT building"},

    # Elementary building (own code namespace; never collapsed into RM-###)
    {"code": "ELEM-21", "name": "Elementary Room 21", "room_type": "LECTURE",
     "capacity": 45, "notes": "Elementary building"},
    {"code": "ELEM-22", "name": "Elementary Room 22", "room_type": "LECTURE",
     "capacity": 45, "notes": "Elementary building"},

    # High School building (borrowed for college classes)
    {"code": "HS-107", "name": "High School Room 107", "room_type": "LECTURE",
     "capacity": 45, "notes": "High School building"},
    {"code": "HS-108", "name": "High School Room 108", "room_type": "LECTURE",
     "capacity": 45, "notes": "High School building"},
    {"code": "HS-109", "name": "High School Room 109", "room_type": "LECTURE",
     "capacity": 45, "notes": "High School building"},
    {"code": "HS-111", "name": "High School Room 111", "room_type": "LECTURE",
     "capacity": 45, "notes": "High School building"},
    {"code": "HS-112", "name": "High School Room 112", "room_type": "LECTURE",
     "capacity": 45, "notes": "High School building"},

    # College building (a different physical building from the Main Building:
    # 'ROOM 101 · COLLEGE' is NOT RM-101, see migration 0034)
    {"code": "COLLEGE-101", "name": "College Building Room 101", "room_type": "LECTURE",
     "capacity": 45, "notes": "College building"},
    {"code": "COLLEGE-203", "name": "College Building Room 203", "room_type": "LECTURE",
     "capacity": 45, "notes": "College building"},

    # Gymnasium (PATHFIT classes; gym periods are legitimately shared)
    {"code": "GYM", "name": "Gymnasium", "room_type": "OTHER",
     "capacity": 60, "notes": "Shared gymnasium; overlapping PATHFIT periods are expected"},
    {"code": "GYM-1", "name": "Gymnasium 1", "room_type": "OTHER",
     "capacity": 60, "notes": "Gymnasium court 1"},
    {"code": "GYM-2", "name": "Gymnasium 2", "room_type": "OTHER",
     "capacity": 60, "notes": "Gymnasium court 2"},
    {"code": "GYM-3", "name": "Gymnasium 3", "room_type": "OTHER",
     "capacity": 60, "notes": "Gymnasium court 3"},
    {"code": "GYM-4", "name": "Gymnasium 4", "room_type": "OTHER",
     "capacity": 60, "notes": "Gymnasium court 4"},

    # Administration
    {"code": "QA-CONF", "name": "QA Conference Room", "room_type": "OTHER",
     "capacity": 20, "notes": "QA office conference room"},
]


# Normalized workbook label -> canonical Room.code. Keys are compared after
# collapsing whitespace and uppercasing, exactly the shape the importer stores.
# Untagged variants ('ROOM 22', 'ROOM 109', 'ROOM 112', 'ROOM 303') bind to the
# only campus building where that room number exists (Elementary, High School,
# High School, CMAT respectively) - the Main Building has no such numbers.
# NOTE: the two PATHFIT-3 meetings the workbook books as 'GYM' at times that
# overlap another PATHFIT class in the same gym are NOT rebound here. The
# trg_cs_slot_bu trigger (and the importer's clash rule) forbid overlapping
# same-room slots; those two stay TBA until the registrar re-rooms one of them.
LABEL_TO_CODE = {
    'LAB 7': 'LAB-7',

    'ROOM 301 \u00b7 CMAT': 'RM-301',
    'ROOM 302 \u00b7 CMAT': 'RM-302',
    'ROOM 303 \u00b7 CMAT': 'RM-303',
    'ROOM 304 \u00b7 CMAT': 'RM-304',
    'ROOM 303': 'RM-303',

    'ROOM 21 \u00b7 ELEM': 'ELEM-21',
    'ROOM 22 \u00b7 ELEM': 'ELEM-22',
    'ROOM 22': 'ELEM-22',

    'ROOM 107 \u00b7 HS': 'HS-107',
    'ROOM 108 \u00b7 HS': 'HS-108',
    'ROOM 109 \u00b7 HS': 'HS-109',
    'ROOM 109': 'HS-109',
    'ROOM 111 \u00b7 HS': 'HS-111',
    'ROOM 112 \u00b7 HS': 'HS-112',
    'ROOM 112': 'HS-112',

    'ROOM 101 \u00b7 COLLEGE': 'COLLEGE-101',
    'ROOM 203 \u00b7 COLLEGE': 'COLLEGE-203',

    'GYM': 'GYM',
    'GYM 1': 'GYM-1',
    'GYM 1 \u00b7 GYM 1': 'GYM-1',   # registrar's doubled spelling
    'GYM 2': 'GYM-2',
    'GYM 3': 'GYM-3',
    'GYM 4': 'GYM-4',

    'QA CONFERENCE ROOM': 'QA-CONF',
}


def seed_missing_rooms_and_backfill(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    ClassSlot = apps.get_model('core', 'ClassSlot')

    room_map = {}
    for r_data in SEEDED_ROOMS:
        room_obj, _ = Room.objects.get_or_create(code=r_data['code'], defaults=r_data)
        room_map[r_data['code']] = room_obj

    # Bind every text-only slot whose label maps to a real room. Updates stay
    # inside the trg_cs_slot_bu integrity rule: no overlapping same-teacher or
    # same-room-text slots exist for these labels (the two PATHFIT-3 meetings
    # the registrar double-booked into the gymnasium stay TBA - binding them
    # would violate that rule, which is why the importer omitted the room).
    for slot in ClassSlot.objects.filter(room_ref__isnull=True):
        raw = (slot.room or '').strip()
        if not raw:
            continue
        code = LABEL_TO_CODE.get(' '.join(raw.split()).upper())
        room_obj = room_map.get(code) if code else None
        if room_obj is None:
            continue
        slot.room_ref = room_obj
        slot.room = room_obj.code
        if room_obj.room_type == 'LABORATORY':
            slot.slot_type = 'LABORATORY'
        slot.save(update_fields=['room_ref', 'room', 'slot_type'])


def reverse_seed_missing_rooms(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    codes = [r['code'] for r in SEEDED_ROOMS]
    # room_ref is SET_NULL: slots keep the canonical text but lose the link,
    # mirroring migration 0034's reverse.
    Room.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_remove_room_building_remove_room_floor'),
    ]

    operations = [
        migrations.RunPython(seed_missing_rooms_and_backfill, reverse_seed_missing_rooms),
    ]
