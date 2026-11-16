# Generated manually for KCC ClassStamp - Room seeding and backfill

import re
from django.db import migrations

SEEDED_ROOMS = [
    # Computer Laboratories (Ground Floor)
    {"code": "LAB-1", "name": "Computer Laboratory 1", "building": "Main Building", "floor": "Ground Floor", "room_type": "LABORATORY", "capacity": 40, "notes": "40 Desktop workstations, Gigabit LAN, Projector"},
    {"code": "LAB-2", "name": "Computer Laboratory 2", "building": "Main Building", "floor": "Ground Floor", "room_type": "LABORATORY", "capacity": 40, "notes": "40 Desktop workstations, Gigabit LAN, Projector"},
    {"code": "LAB-3", "name": "Computer Laboratory 3", "building": "Main Building", "floor": "Ground Floor", "room_type": "LABORATORY", "capacity": 40, "notes": "40 Desktop workstations, Gigabit LAN, Projector"},
    {"code": "LAB-4", "name": "Computer Laboratory 4", "building": "Main Building", "floor": "Ground Floor", "room_type": "LABORATORY", "capacity": 40, "notes": "40 Desktop workstations, Gigabit LAN, Projector"},
    {"code": "LAB-5", "name": "Computer Laboratory 5", "building": "Main Building", "floor": "Ground Floor", "room_type": "LABORATORY", "capacity": 40, "notes": "40 Desktop workstations, Cisco Networking Racks"},
    {"code": "LAB-6", "name": "Computer Laboratory 6", "building": "Main Building", "floor": "Ground Floor", "room_type": "LABORATORY", "capacity": 40, "notes": "40 Desktop workstations, Multimedia production setup"},

    # 1st Floor Lecture Rooms
    {"code": "RM-101", "name": "Room 101", "building": "Main Building", "floor": "1st Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with smart TV"},
    {"code": "RM-102", "name": "Room 102", "building": "Main Building", "floor": "1st Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with smart TV"},
    {"code": "RM-103", "name": "Room 103", "building": "Main Building", "floor": "1st Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with projector"},
    {"code": "RM-104", "name": "Room 104", "building": "Main Building", "floor": "1st Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with whiteboard"},

    # 2nd Floor Lecture Rooms
    {"code": "RM-201", "name": "Room 201", "building": "Main Building", "floor": "2nd Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with smart TV"},
    {"code": "RM-202", "name": "Room 202", "building": "Main Building", "floor": "2nd Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with smart TV"},
    {"code": "RM-203", "name": "Room 203", "building": "Main Building", "floor": "2nd Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with whiteboard"},
    {"code": "RM-204", "name": "Room 204", "building": "Main Building", "floor": "2nd Floor", "room_type": "LECTURE", "capacity": 45, "notes": "Standard lecture hall with whiteboard"},
]


def seed_rooms_and_backfill(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    Subject = apps.get_model('core', 'Subject')
    ClassSlot = apps.get_model('core', 'ClassSlot')

    # 1. Seed or get 14 campus rooms
    room_map = {}
    for r_data in SEEDED_ROOMS:
        room_obj, _ = Room.objects.get_or_create(
            code=r_data['code'],
            defaults=r_data,
        )
        room_map[r_data['code']] = room_obj

    # 2. Auto-tag is_lab on Subject
    lab_keywords = ['programming', 'lab', 'laboratory', 'web', 'database', 'network', 'system', 'software', 'mobile']
    for subj in Subject.objects.all():
        name_lower = (subj.name or '').lower()
        code_upper = (subj.code or '').upper()
        if any(kw in name_lower for kw in lab_keywords) or 'LAB' in code_upper:
            subj.is_lab = True
            subj.save(update_fields=['is_lab'])

    # 3. Backfill ClassSlot room_ref
    for slot in ClassSlot.objects.all():
        raw_room = (slot.room or '').strip().upper()
        if not raw_room:
            continue

        matched_room = None
        # Exact code match
        if raw_room in room_map:
            matched_room = room_map[raw_room]
        else:
            # Pattern matching for legacy strings
            # Labs: LAB 1, LAB-1, IT-LAB 1, IT LAB 1, LAB1
            lab_match = re.search(r'LAB\s*[-]?\s*([1-6])', raw_room)
            if lab_match:
                lab_code = f"LAB-{lab_match.group(1)}"
                matched_room = room_map.get(lab_code)
            else:
                # Rooms: RM 101, RM-101, ROOM 101, 101, 102, 201, etc.
                rm_match = re.search(r'(?:RM|ROOM)?\s*[-]?\s*(10[1-4]|20[1-4])', raw_room)
                if rm_match:
                    rm_code = f"RM-{rm_match.group(1)}"
                    matched_room = room_map.get(rm_code)

        if matched_room:
            slot.room_ref = matched_room
            slot.room = matched_room.code
            if matched_room.room_type == 'LABORATORY':
                slot.slot_type = 'LABORATORY'
            slot.save(update_fields=['room_ref', 'room', 'slot_type'])


def reverse_seed_rooms(apps, schema_editor):
    Room = apps.get_model('core', 'Room')
    codes = [r['code'] for r in SEEDED_ROOMS]
    Room.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_room_classslot_slot_type_subject_is_lab_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_rooms_and_backfill, reverse_seed_rooms),
    ]
