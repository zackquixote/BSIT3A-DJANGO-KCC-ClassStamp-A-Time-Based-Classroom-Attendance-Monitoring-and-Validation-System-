"""
# // ==============================================================================
# // KCC CLASSSTAMP - CAMPUS ROOM MANAGEMENT & SCHEDULING INTEGRATION TESTS
# // ==============================================================================
# // Subsystem: Facilities & Classroom Infrastructure (Room CRUD)
# // Description: Comprehensive test coverage for:
# //   - Room model constraints, canonical code formatting, capacity limits
# //   - Room CRUD service operations, soft-delete protections, AuditEvents
# //   - Room admin views, access control, and JSON APIs
# //   - ClassSlot room_ref FK and slot_type (LECTURE vs LABORATORY)
# //   - Room conflict detection (FK-based and string fallback)
# //   - Room verification scanner integration
# //   - Academic year cloning of room_ref and slot_type
# //   - Subject is_lab flag and Section Wizard integration
# // ==============================================================================
"""

from datetime import date, time
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Curriculum,
    Department,
    FacilityType,
    Profile,
    Program,
    Room,
    RoomVerification,
    Subject,
)
from apps.core.services import (
    clone_classes_academic_year,
    create_or_update_room,
    create_or_update_subject,
    delete_or_deactivate_room,
)
from apps.core.services.schedule_service import detect_slot_conflicts

User = get_user_model()


class RoomTestMixin:
    """
    // Base test setup providing institutional hierarchy, users, and rooms.
    """
    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(code='CCS_TEST', name='College of Computer Studies')
        cls.program = Program.objects.create(
            department=cls.department, code='BSIT_TEST', name='BS in Information Technology', years_total=4,
        )
        cls.ay = AcademicYear.objects.create(
            name='2026-2027 Test Term',
            starts_on=date(2026, 6, 1),
            ends_on=date(2027, 3, 31),
            is_active=True,
        )
        cls.subj_lecture = Subject.objects.create(
            code='IT101_T', name='Introduction to Computing', units=3, is_lab=False,
        )
        cls.subj_lab = Subject.objects.create(
            code='IT102_T', name='Computer Programming 1', units=3, is_lab=True,
        )

        # Users
        cls.admin_user = User.objects.create_user(username='admin_room_user', password='password123')
        cls.admin_profile = Profile.objects.create(user=cls.admin_user, role=Profile.ROLE_ADMIN)

        cls.teacher_user = User.objects.create_user(username='teacher_room_user', password='password123')
        cls.teacher_profile = Profile.objects.create(
            user=cls.teacher_user, role=Profile.ROLE_TEACHER, department=cls.department,
        )

        cls.student_user = User.objects.create_user(username='student_room_user', password='password123')
        cls.student_profile = Profile.objects.create(user=cls.student_user, role=Profile.ROLE_STUDENT)

        # Seeded Test Rooms
        cls.lab_room, _ = Room.objects.get_or_create(
            code='LAB-TEST-1',
            defaults={
                'name': 'Test Lab 1',
                'room_type': Room.ROOM_TYPE_LABORATORY,
                'capacity': 40,
                'is_active': True,
            },
        )
        cls.lecture_room, _ = Room.objects.get_or_create(
            code='RM-TEST-101',
            defaults={
                'name': 'Test Room 101',
                'room_type': Room.ROOM_TYPE_LECTURE,
                'capacity': 45,
                'is_active': True,
            },
        )


class RoomModelTest(RoomTestMixin, TestCase):
    """
    // Unit tests for Room model constraints and methods.
    """
    def test_canonical_code_uppercased(self):
        room = Room(code='  lab-99  ', name='Special Lab', room_type=Room.ROOM_TYPE_LABORATORY, capacity=30)
        room.save()
        self.assertEqual(room.code, 'LAB-99')

    def test_room_properties(self):
        self.assertTrue(self.lab_room.is_lab)
        self.assertFalse(self.lab_room.is_lecture)
        self.assertTrue(self.lecture_room.is_lecture)
        self.assertFalse(self.lecture_room.is_lab)

    def test_seeded_campus_rooms_exist(self):
        # Campus rooms seeded by migrations 0034 and 0036
        for lab_num in range(1, 8):
            self.assertTrue(Room.objects.filter(code=f'LAB-{lab_num}').exists())
        for rm_num in [101, 102, 103, 104, 201, 202, 203, 204, 301, 302, 303, 304]:
            self.assertTrue(Room.objects.filter(code=f'RM-{rm_num}').exists())
        for code in ['ELEM-21', 'ELEM-22', 'HS-107', 'HS-108', 'HS-109', 'HS-111',
                     'HS-112', 'COLLEGE-101', 'COLLEGE-203', 'GYM', 'GYM-1',
                     'GYM-2', 'GYM-3', 'GYM-4', 'QA-CONF']:
            self.assertTrue(Room.objects.filter(code=code).exists())


class RoomServiceTest(RoomTestMixin, TestCase):
    """
    // Tests for Room business logic and services.
    """
    def test_create_room_service(self):
        result = create_or_update_room(
            actor=self.admin_user,
            code='HS-1',
            name='HS Room 1',
            room_type='HS',
            capacity=100,
        )
        room = result['instance']
        self.assertEqual(room.code, 'HS-1')
        self.assertEqual(room.capacity, 100)
        self.assertTrue(AuditEvent.objects.filter(actor=self.admin_user, action='CREATE_ROOM', object_id=str(room.pk)).exists())

    def test_duplicate_code_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            create_or_update_room(
                actor=self.admin_user,
                code='LAB-TEST-1',
                name='Duplicate Lab',
            )
        self.assertIn('already in use', str(ctx.exception))

    def test_invalid_capacity_rejected(self):
        with self.assertRaises(ValueError):
            create_or_update_room(
                actor=self.admin_user,
                code='RM-999',
                name='Bad Capacity Room',
                capacity=0,
            )

    def test_invalid_code_format_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            create_or_update_room(
                actor=self.admin_user,
                code='LAB 1',
                name='Spaced Code',
            )
        self.assertIn('uppercase letters', str(ctx.exception))

        with self.assertRaises(ValueError):
            create_or_update_room(actor=self.admin_user, code='lab!!', name='Punctuated')

        # Lowercase input is canonicalised first, so this is accepted.
        result = create_or_update_room(
            actor=self.admin_user, code='lab-77', name='Canonicalised',
        )
        self.assertEqual(result['instance'].code, 'LAB-77')

    def test_protected_deactivation_when_slots_exist(self):
        # Create a class with a slot attached to the room
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-3A-IT102',
            subject=self.subj_lab,
            teacher_profile=self.teacher_profile,
        )
        slot = ClassSlot.objects.create(
            class_obj=c,
            weekday=0,
            starts_at=time(8, 0),
            ends_at=time(10, 0),
            room_ref=self.lab_room,
            room=self.lab_room.code,
            slot_type=ClassSlot.SLOT_TYPE_LABORATORY,
        )

        result = delete_or_deactivate_room(actor=self.admin_user, pk=self.lab_room.pk)
        self.assertEqual(result['type'], 'deactivated')
        self.lab_room.refresh_from_db()
        self.assertFalse(self.lab_room.is_active)
        self.assertTrue(Room.objects.filter(pk=self.lab_room.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action='DEACTIVATE_ROOM', object_id=str(self.lab_room.pk)).exists())

    def test_hard_delete_when_no_slots_exist(self):
        temp_room = Room.objects.create(
            code='TEMP-99',
            name='Temporary Room',
            room_type=Room.ROOM_TYPE_LECTURE,
            capacity=20,
        )
        pk = temp_room.pk
        result = delete_or_deactivate_room(actor=self.admin_user, pk=pk)
        self.assertEqual(result['type'], 'deleted')
        self.assertFalse(Room.objects.filter(pk=pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action='DELETE_ROOM', object_id=str(pk)).exists())


class RoomViewsTest(RoomTestMixin, TestCase):
    """
    // Tests for Room admin views and API endpoints.
    """
    def test_room_list_access_control(self):
        url = reverse('room_list')

        # Anonymous redirected
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)

        # Teacher redirected to dashboard fallback
        self.client.force_login(self.teacher_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('dashboard'))

        # Admin allowed
        self.client.force_login(self.admin_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'LAB-TEST-1')

        # Search query finds page-2 rooms
        res_search = self.client.get(url, {'q': 'RM-TEST-101'})
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, 'RM-TEST-101')

    def test_room_save_ajax(self):
        self.client.force_login(self.admin_user)
        url = reverse('room_save')
        data = {
            'code': 'LAB-NEW',
            'name': 'New Robotics Lab',
            'room_type': 'LABORATORY',
            'capacity': 35,
            'is_active': 'true',
        }
        res = self.client.post(url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        json_data = res.json()
        self.assertEqual(json_data['status'], 'success')
        self.assertTrue(Room.objects.filter(code='LAB-NEW').exists())

    def test_room_options_json(self):
        self.client.force_login(self.admin_user)
        url = reverse('room_options_json')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        codes = [r['code'] for r in data['rooms']]
        self.assertIn('LAB-TEST-1', codes)
        self.assertIn('RM-TEST-101', codes)

    def test_room_options_json_admin_only(self):
        url = reverse('room_options_json')

        # Anonymous → login
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)

        # Students must not enumerate campus facilities
        self.client.force_login(self.student_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)

        # Teachers do not schedule rooms; wizard/options stay admin-only
        self.client.force_login(self.teacher_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('dashboard'))

        # Admin allowed
        self.client.force_login(self.admin_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_room_detail_json(self):
        self.client.force_login(self.admin_user)
        url = reverse('room_detail_json', args=[self.lab_room.pk])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['room']['code'], 'LAB-TEST-1')
        self.assertTrue(data['room']['is_lab'])
        self.assertEqual(data['attached_slot_count'], 0)

    def test_room_detail_json_reports_attached_slots(self):
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-2B-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
        )
        ClassSlot.objects.create(
            class_obj=c,
            weekday=1,
            starts_at=time(9, 0),
            ends_at=time(10, 30),
            room_ref=self.lab_room,
            room=self.lab_room.code,
        )
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse('room_detail_json', args=[self.lab_room.pk]))
        self.assertEqual(res.json()['attached_slot_count'], 1)

    def test_room_list_slot_count_includes_legacy_string_slots(self):
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-2C-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
        )
        ClassSlot.objects.create(
            class_obj=c,
            weekday=2,
            starts_at=time(8, 0),
            ends_at=time(9, 30),
            room_ref=self.lab_room,
            room=self.lab_room.code,
        )
        # Legacy slot: code string matches but room_ref was never linked
        # (e.g. the Room row was created after the slot). QuerySet.update
        # bypasses save() so the sync does not repair the FK.
        legacy = ClassSlot.objects.create(
            class_obj=c,
            weekday=3,
            starts_at=time(8, 0),
            ends_at=time(9, 30),
            room=self.lecture_room.code,
        )
        ClassSlot.objects.filter(pk=legacy.pk).update(room_ref=None)

        self.client.force_login(self.admin_user)
        # Search for the two test rooms: the directory now holds more rooms
        # than one page (migration 0036), and RM-TEST-101 sorts onto page 2.
        res = self.client.get(reverse('room_list'), {'q': 'TEST'})
        counts = {r.code: r.slot_count for r in res.context['rooms']}
        self.assertEqual(counts['LAB-TEST-1'], 1)
        self.assertEqual(counts['RM-TEST-101'], 1)

    def test_class_list_includes_room_picker(self):
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse('class_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'name="room_id"')
        self.assertContains(res, 'LAB-TEST-1')


class ClassSlotRoomIntegrationTest(RoomTestMixin, TestCase):
    """
    // Tests for ClassSlot room_ref FK and conflict detection.
    """
    def test_class_slot_room_sync(self):
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-1A-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
        )
        slot = ClassSlot.objects.create(
            class_obj=c,
            weekday=1,
            starts_at=time(9, 0),
            ends_at=time(10, 30),
            room_ref=self.lecture_room,
            slot_type=ClassSlot.SLOT_TYPE_LECTURE,
        )
        # room CharField is automatically synced to room_ref.code
        self.assertEqual(slot.room, self.lecture_room.code)
        self.assertEqual(slot.slot_type, ClassSlot.SLOT_TYPE_LECTURE)

    def test_detect_slot_conflicts_by_room_id(self):
        c1 = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-1A-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
        )
        ClassSlot.objects.create(
            class_obj=c1,
            weekday=2,
            starts_at=time(10, 0),
            ends_at=time(12, 0),
            room_ref=self.lab_room,
            room=self.lab_room.code,
        )

        other_teacher = User.objects.create_user(username='other_teacher_user')
        other_profile = Profile.objects.create(user=other_teacher, role=Profile.ROLE_TEACHER)

        # Conflict detected when proposed slot has the same room_id
        conflicts = detect_slot_conflicts(
            teacher_profile_id=other_profile.id,
            weekday=2,
            starts_at=time(11, 0),
            ends_at=time(13, 0),
            room_id=self.lab_room.id,
            academic_year=self.ay,
        )
        room_conflicts = [c for c in conflicts if c['type'] == 'room']
        self.assertEqual(len(room_conflicts), 1)
        self.assertEqual(room_conflicts[0]['class_code'], 'BSIT-1A-IT101')

    def test_detect_slot_conflicts_by_room_string_matches_canonical(self):
        c1 = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-2A-IT102',
            subject=self.subj_lab,
            teacher_profile=self.teacher_profile,
        )
        ClassSlot.objects.create(
            class_obj=c1,
            weekday=3,
            starts_at=time(13, 0),
            ends_at=time(15, 0),
            room_ref=self.lab_room,
            room=self.lab_room.code,
        )

        # Proposing with room string 'lab-test-1' matches case-insensitively
        conflicts = detect_slot_conflicts(
            teacher_profile_id=99999,
            weekday=3,
            starts_at=time(14, 0),
            ends_at=time(16, 0),
            room='lab-test-1',
            academic_year=self.ay,
        )
        room_conflicts = [c for c in conflicts if c['type'] == 'room']
        self.assertEqual(len(room_conflicts), 1)

    def test_detect_slot_conflicts_room_id_against_legacy_string_slot(self):
        """P1-2: Manage Slots sends room_id only; legacy TBA/string rows must still clash."""
        c1 = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-3A-IT103',
            subject=self.subj_lab,
            teacher_profile=self.teacher_profile,
        )
        # Live MySQL shape from the audit: room code copied, FK still NULL.
        ClassSlot.objects.create(
            class_obj=c1,
            weekday=4,
            starts_at=time(8, 0),
            ends_at=time(10, 0),
            room=self.lab_room.code,
            room_ref=None,
        )

        other_teacher = User.objects.create_user(username='legacy_clash_teacher')
        other_profile = Profile.objects.create(user=other_teacher, role=Profile.ROLE_TEACHER)

        conflicts = detect_slot_conflicts(
            teacher_profile_id=other_profile.id,
            weekday=4,
            starts_at=time(9, 0),
            ends_at=time(11, 0),
            room_id=self.lab_room.id,
            academic_year=self.ay,
        )
        room_conflicts = [c for c in conflicts if c['type'] == 'room']
        self.assertEqual(len(room_conflicts), 1)
        self.assertEqual(room_conflicts[0]['class_code'], 'BSIT-3A-IT103')

    def test_class_slot_save_binds_room_ref_from_room_id(self):
        """
        // The Manage Slots form submits room_id (Room Directory picker).
        // The slot must bind the FK and copy the canonical code into room.
        """
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-1C-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
        )
        self.client.force_login(self.admin_user)
        res = self.client.post(
            reverse('class_slot_save', args=[c.pk]),
            {
                'weekday': '1',
                'starts_at': '08:00',
                'ends_at': '09:30',
                'room_id': str(self.lab_room.pk),
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        slot = ClassSlot.objects.get(class_obj=c)
        self.assertEqual(slot.room_ref, self.lab_room)
        self.assertEqual(slot.room, self.lab_room.code)

    def test_class_slot_save_accepts_slot_type(self):
        """P2-2: Manage Slots must be able to file a slot as LABORATORY."""
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-1E-IT101',
            subject=self.subj_lab,
            teacher_profile=self.teacher_profile,
        )
        self.client.force_login(self.admin_user)
        res = self.client.post(
            reverse('class_slot_save', args=[c.pk]),
            {
                'weekday': '3',
                'starts_at': '13:00',
                'ends_at': '15:00',
                'room_id': str(self.lab_room.pk),
                'slot_type': 'LABORATORY',
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        slot = ClassSlot.objects.get(class_obj=c)
        self.assertEqual(slot.slot_type, 'LABORATORY')
        self.assertEqual(slot.room_ref, self.lab_room)

    def test_class_slot_save_refuses_inactive_class_and_closed_term(self):
        """P3-7: no new slots on a retired section or a closed term."""
        inactive = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-1F-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
            is_active=False,
        )
        self.client.force_login(self.admin_user)
        res = self.client.post(
            reverse('class_slot_save', args=[inactive.pk]),
            {'weekday': '1', 'starts_at': '08:00', 'ends_at': '09:00', 'room_id': ''},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('inactive', res.json()['message'])

        closed_ay = AcademicYear.objects.create(
            name='2025-2026 Closed',
            starts_on=date(2025, 6, 1),
            ends_on=date(2026, 3, 31),
            is_active=False,
        )
        closed = Class.objects.create(
            academic_year=closed_ay,
            class_code='BSIT-1G-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
            is_active=True,
        )
        res = self.client.post(
            reverse('class_slot_save', args=[closed.pk]),
            {'weekday': '1', 'starts_at': '08:00', 'ends_at': '09:00', 'room_id': ''},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('active academic term', res.json()['message'])

    def test_class_slot_save_tba_when_no_room(self):
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-1D-IT101',
            subject=self.subj_lecture,
            teacher_profile=self.teacher_profile,
        )
        self.client.force_login(self.admin_user)
        res = self.client.post(
            reverse('class_slot_save', args=[c.pk]),
            {
                'weekday': '2',
                'starts_at': '08:00',
                'ends_at': '09:30',
                'room_id': '',
            },
        )
        self.assertEqual(res.status_code, 200)
        slot = ClassSlot.objects.get(class_obj=c)
        self.assertIsNone(slot.room_ref)
        self.assertEqual(slot.room, 'TBA')

    def test_verify_classroom_allows_canonical_code_and_name(self):
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-3A-IT102',
            subject=self.subj_lab,
            teacher_profile=self.teacher_profile,
        )
        slot = ClassSlot.objects.create(
            class_obj=c,
            weekday=0,
            starts_at=time(8, 0),
            ends_at=time(10, 0),
            room_ref=self.lab_room,
            room=self.lab_room.code,
        )
        session = ClassSession.objects.create(
            slot=slot,
            session_date=date(2026, 6, 1),
            status=ClassSession.STATUS_OPEN,
        )

        self.client.force_login(self.teacher_user)
        url = reverse('verify_classroom', args=[session.pk])

        # Verification with canonical code
        res = self.client.post(url, {'room': 'lab-test-1'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['room'], 'LAB-TEST-1')

        # Verification with room name
        res = self.client.post(url, {'room': 'Test Lab 1'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['room'], 'LAB-TEST-1')

        # Wrong room rejected
        res = self.client.post(url, {'room': 'RM-999'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('Room mismatch', res.json()['error'])

    def test_clone_classes_preserves_room_ref_and_slot_type(self):
        target_ay = AcademicYear.objects.create(
            name='2027-2028 Future Term',
            starts_on=date(2027, 6, 1),
            ends_on=date(2028, 3, 31),
            is_active=False,
        )
        c = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-4A-IT102',
            subject=self.subj_lab,
            teacher_profile=self.teacher_profile,
        )
        ClassSlot.objects.create(
            class_obj=c,
            weekday=4,
            starts_at=time(13, 0),
            ends_at=time(16, 0),
            room_ref=self.lab_room,
            room=self.lab_room.code,
            slot_type=ClassSlot.SLOT_TYPE_LABORATORY,
        )

        result = clone_classes_academic_year(
            actor=self.admin_user,
            source_year=self.ay,
            target_year=target_ay,
        )
        self.assertEqual(result['copied_class_count'], 1)
        self.assertEqual(result['copied_slot_count'], 1)

        cloned_slot = ClassSlot.objects.get(class_obj__academic_year=target_ay, class_obj__class_code='BSIT-4A-IT102')
        self.assertEqual(cloned_slot.room_ref, self.lab_room)
        self.assertEqual(cloned_slot.slot_type, ClassSlot.SLOT_TYPE_LABORATORY)
        self.assertEqual(cloned_slot.room, self.lab_room.code)


class SubjectLabFlagTest(RoomTestMixin, TestCase):
    """
    // Tests for Subject is_lab attribute and wizard options.
    """
    def test_create_or_update_subject_is_lab(self):
        result = create_or_update_subject(
            actor=self.admin_user,
            code='IT499_TEST',
            name='Capstone Project Lab',
            description='Project laboratory course',
            units=3,
            is_active=True,
            is_lab=True,
        )
        subj = result['instance']
        self.assertTrue(subj.is_lab)

        # Update flag
        update_res = create_or_update_subject(
            actor=self.admin_user,
            code='IT499_TEST',
            name='Capstone Project Lab',
            description='Project lecture course',
            units=3,
            is_active=True,
            is_lab=False,
            subject_id=subj.pk,
        )
        subj.refresh_from_db()
        self.assertFalse(subj.is_lab)

    def test_class_wizard_options_includes_is_lab(self):
        # Curriculum mapping
        Curriculum.objects.create(
            program=self.program,
            subject=self.subj_lab,
            year_level=1,
            semester=1,
        )
        self.client.force_login(self.admin_user)
        url = reverse('class_wizard_options')
        res = self.client.get(url, {
            'program_id': self.program.id,
            'year_level': 1,
            'semester': 1,
            'ay_id': self.ay.id,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        subjs = data['subjects']
        lab_subj = next((s for s in subjs if s['code'] == 'IT102_T'), None)
        self.assertIsNotNone(lab_subj)
        self.assertTrue(lab_subj['is_lab'])


class RoomRenamePropagationTests(RoomTestMixin, TestCase):
    """
    // Renaming a Room code must keep every slot's room text and room_ref FK
    // in sync (the latent drift gap found in the room scheduling audit).
    """

    def test_rename_propagates_to_fk_and_adopts_text_only_slots(self):
        room = Room.objects.create(
            code='LAB-9', name='Computer Laboratory 9',
            room_type=Room.ROOM_TYPE_LABORATORY, capacity=40,
        )
        class_obj = Class.objects.create(
            academic_year=self.ay,
            class_code='BSIT-3A-IT309T',
            subject=self.subj_lab,
            teacher_profile=self.teacher_profile,
        )
        bound = ClassSlot.objects.create(
            class_obj=class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(10, 0), room_ref=room,
        )
        legacy = ClassSlot.objects.create(
            class_obj=class_obj, weekday=2,
            starts_at=time(8, 0), ends_at=time(10, 0), room='LAB-9',
        )
        # Simulate a legacy row written without the FK link.
        ClassSlot.objects.filter(pk=legacy.pk).update(room_ref=None)

        result = create_or_update_room(
            actor=self.admin_user, code='LAB-10', name='Computer Laboratory 10',
            room_type=Room.ROOM_TYPE_LABORATORY, capacity=40, room_id=room.pk,
        )

        room.refresh_from_db()
        bound.refresh_from_db()
        legacy.refresh_from_db()
        self.assertEqual(room.code, 'LAB-10')
        # FK-bound slot follows the rename in its text.
        self.assertEqual(bound.room, 'LAB-10')
        self.assertEqual(bound.room_ref_id, room.pk)
        # Text-only slot spelled with the old code is adopted by the FK.
        self.assertEqual(legacy.room, 'LAB-10')
        self.assertEqual(legacy.room_ref_id, room.pk)
        # No slot keeps a stale label.
        self.assertFalse(
            ClassSlot.objects.filter(room_ref=room).exclude(room='LAB-10').exists()
        )
        self.assertIn('schedule slot(s) follow the rename', result['message'])
        self.assertTrue(
            AuditEvent.objects.filter(
                action='UPDATE_ROOM', object_id=str(room.pk),
                reason__icontains='LAB-9 -> LAB-10',
            ).exists()
        )

    def test_rename_without_slots_reports_plain_update(self):
        room = Room.objects.create(
            code='RM-301T', name='Room 301 Test',
            room_type=Room.ROOM_TYPE_LECTURE, capacity=45,
        )
        result = create_or_update_room(
            actor=self.admin_user, code='RM-302T', name='Room 302 Test',
            room_type=Room.ROOM_TYPE_LECTURE, capacity=45, room_id=room.pk,
        )
        room.refresh_from_db()
        self.assertEqual(room.code, 'RM-302T')
        self.assertNotIn('follow the rename', result['message'])


class FacilityTypeCrudTests(RoomTestMixin, TestCase):
    """
    // Facility Types are a registrar-managed lookup (not a frozen choices list):
    // create/rename/delete, wiring into the Room form, and the guards that keep
    // built-in or in-use types from being removed.
    """

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_seeded_types_use_the_new_set(self):
        codes = set(FacilityType.objects.values_list('code', flat=True))

        self.assertIn('LECTURE', codes)
        self.assertIn('LABORATORY', codes)
        self.assertIn('HS', codes)
        self.assertIn('ELEM', codes)
        self.assertNotIn('AVR', codes)

    def test_create_type_and_assign_to_room(self):
        response = self.client.post(reverse('facility_type_save'), {
            'code': 'hsb', 'name': 'HS Building Room',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200, response.content)
        facility = FacilityType.objects.get(code='HSB')
        self.assertEqual(facility.name, 'HS Building Room')

        room_response = self.client.post(reverse('room_save'), {
            'code': 'HSB-101', 'name': 'HS Building Room 101',
            'room_type': 'HSB', 'capacity': '45', 'is_active': 'true', 'notes': '',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(room_response.status_code, 200, room_response.content)
        room = Room.objects.get(code='HSB-101')
        self.assertEqual(room.room_type, 'HSB')
        self.assertEqual(room.get_room_type_display(), 'HS Building Room')

    def test_rename_type_keeps_its_code(self):
        facility = FacilityType.objects.get(code='HS')

        response = self.client.post(reverse('facility_type_save'), {
            'id': facility.pk, 'code': 'HS', 'name': 'High School Room',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200, response.content)
        facility.refresh_from_db()
        self.assertEqual(facility.name, 'High School Room')
        self.assertEqual(facility.code, 'HS')

    def test_in_use_type_cannot_be_deleted(self):
        facility = FacilityType.objects.create(code='HSB', name='HS Building Room', sort_order=50)
        Room.objects.create(code='HSB-102', name='HS Building Room 102',
                            room_type='HSB', capacity=40)

        response = self.client.post(
            reverse('facility_type_delete', args=[facility.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('still use', response.json()['error'])
        self.assertTrue(FacilityType.objects.filter(pk=facility.pk).exists())

    def test_builtin_type_cannot_be_deleted(self):
        lecture = FacilityType.objects.get(code='LECTURE')

        response = self.client.post(
            reverse('facility_type_delete', args=[lecture.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('built-in', response.json()['error'])

    def test_unknown_room_type_is_rejected(self):
        with self.assertRaises(ValueError):
            create_or_update_room(
                actor=self.admin_user, code='RM-900',
                name='Room 900', room_type='NOPE',
            )
