"""Tests for the curriculum classification split and the section timetable importer."""

import datetime
import io
import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.core.management.commands.import_section_timetable import (
    Command, parse_days, parse_faculty, parse_time_range, resolve_room,
)
from apps.core.models import (
    AcademicYear, Class, ClassSlot, Curriculum, CurriculumVersion, Department, Profile, Program, Room,
    Subject,
)
from apps.core.serializers.academic_serializers import serialize_curriculum_entry
from apps.core.services.academic_service import (
    CLASSIFICATION_CORE,
    CLASSIFICATION_GENERAL_EDUCATION,
    CLASSIFICATION_MAJOR,
    CLASSIFICATION_NSTP,
    CLASSIFICATION_PE,
    CLASSIFICATION_THEOLOGY,
    classification_label,
    classify_subject,
    format_subject_code,
)


class ClassificationTests(SimpleTestCase):
    def test_general_education_codes(self):
        for code in ('GE 1', 'GE 4', 'GEE 2', 'GE10'):
            self.assertEqual(classify_subject(code), CLASSIFICATION_GENERAL_EDUCATION)

    def test_nstp_and_civic_welfare_codes(self):
        for code in ('NSTP 1', 'NSTP 2', 'ROTC 1', 'CWTS 1'):
            self.assertEqual(classify_subject(code), CLASSIFICATION_NSTP)

    def test_physical_education_codes(self):
        for code in ('PATHfit 1', 'PATHFIT 2', 'PE 3'):
            self.assertEqual(classify_subject(code), CLASSIFICATION_PE)

    def test_theology_codes(self):
        for code in ('Theology 1', 'THEO 2', 'ReEd 3'):
            self.assertEqual(classify_subject(code), CLASSIFICATION_THEOLOGY)

    def test_major_and_core_follow_is_major(self):
        self.assertEqual(classify_subject('IT 311', True), CLASSIFICATION_MAJOR)
        self.assertEqual(classify_subject('IT 311', False), CLASSIFICATION_CORE)

    def test_general_education_is_never_major_even_if_flagged(self):
        # The bug: every curriculum row had is_major=True, so GE rows read "Major".
        self.assertEqual(classify_subject('GE 1', True), CLASSIFICATION_GENERAL_EDUCATION)

    def test_labels(self):
        self.assertEqual(classification_label(CLASSIFICATION_GENERAL_EDUCATION), 'General Education')
        self.assertEqual(classification_label(CLASSIFICATION_NSTP), 'NSTP')
        self.assertEqual(classification_label(CLASSIFICATION_PE), 'Physical Education')
        self.assertEqual(classification_label(CLASSIFICATION_THEOLOGY), 'Theology')
        self.assertEqual(classification_label(CLASSIFICATION_MAJOR), 'Major')

    def test_format_subject_code_adds_the_registrar_space(self):
        self.assertEqual(format_subject_code('CC101'), 'CC 101')
        self.assertEqual(format_subject_code('IT201'), 'IT 201')
        self.assertEqual(format_subject_code('GE 1'), 'GE 1')
        self.assertEqual(format_subject_code('PATHfit 1'), 'PATHfit 1')
        self.assertEqual(format_subject_code(''), '')
        self.assertEqual(format_subject_code(None), '')


class ParsingTests(SimpleTestCase):
    def test_parse_days(self):
        self.assertEqual(parse_days('MWF'), [0, 2, 4])
        self.assertEqual(parse_days('TTH'), [1, 3])
        self.assertEqual(parse_days('MTH'), [0, 3])
        self.assertEqual(parse_days('S'), [5])
        self.assertEqual(parse_days('MTWTHF'), [0, 1, 2, 3, 4])
        self.assertEqual(parse_days(''), [])

    def test_parse_time_range(self):
        self.assertEqual(
            parse_time_range('8:30 AM - 9:30 AM'),
            (datetime.time(8, 30), datetime.time(9, 30)),
        )
        self.assertEqual(
            parse_time_range('1:00 PM - 4:00 PM'),
            (datetime.time(13, 0), datetime.time(16, 0)),
        )
        self.assertEqual(
            parse_time_range('11:30 AM - 12:30 PM'),
            (datetime.time(11, 30), datetime.time(12, 30)),
        )
        self.assertIsNone(parse_time_range('TBA'))
        self.assertIsNone(parse_time_range('5:00 PM - 4:00 PM'))

    def test_parse_faculty_strips_placeholder_suffix(self):
        self.assertEqual(parse_faculty('Olasa, Godwin Allevson NA'), ('Olasa', 'Godwin Allevson'))
        self.assertEqual(parse_faculty('Tabligan, Lezeth Rose T'), ('Tabligan', 'Lezeth Rose T'))


def build_workbook(path):
    """Two sections: one lecture+lab pair, one single meeting."""
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['KCC BSIT TIMETABLE'])
    sheet.append(['A.Y. 2026-2027, First Semester'])
    sheet.append(['Code', 'Description', 'Faculty', 'Day', 'Time', 'Room', 'Units', 'Hrs/Wk'])

    sheet.append(['BSIT 1A'])
    sheet.append(['SUBJECTS'])
    sheet.append(['Code', 'Description', 'Faculty', 'Day', 'Time', 'Room', 'Units', 'Hrs/Wk'])
    sheet.append(['CC 101', 'Introduction to Computing', 'Tabligan, Lezeth Rose T',
                  'MT', '1:00 PM - 2:00 PM', 'ROOM 203', 3, 2])
    sheet.append(['CC 101', 'Introduction to Computing', 'Tabligan, Lezeth Rose T',
                  'W', '1:00 PM - 4:00 PM', 'LAB 1', 3, 3])
    sheet.append(['GE 4', 'Mathematics in the Modern World', 'Tantiado, Kerwin F',
                  'MWF', '8:30 AM - 9:30 AM', 'ROOM 203', 3, 3])
    sheet.append(['Total — 9.0 units'])

    sheet.append(['BSIT 2B'])
    sheet.append(['Code', 'Description', 'Faculty', 'Day', 'Time', 'Room', 'Units', 'Hrs/Wk'])
    sheet.append(['IT 201', 'Data Structures', 'Israel, Jewel',
                  'TTH', '10:00 AM - 11:30 AM', 'LAB 2', 3, 3])
    sheet.append(['Total — 3.0 units'])

    workbook.save(path)


class ImporterTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CITE', name='College of Information Technology')
        self.program = Program.objects.create(
            code='BSIT', name='BS Information Technology', department=self.department,
        )
        self.ay = AcademicYear.objects.create(
            name='2026-2027 1st Sem',
            starts_on=datetime.date(2026, 8, 1),
            ends_on=datetime.date(2027, 5, 31),
            is_active=True,
        )
        self.tmpdir = tempfile.mkdtemp()
        self.workbook = Path(self.tmpdir) / 'timetable.xlsx'
        build_workbook(self.workbook)

    def tearDown(self):
        try:
            os.unlink(self.workbook)
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def run_command(self, *extra):
        stdout = io.StringIO()
        command = Command(stdout=stdout, stderr=io.StringIO())
        command.handle(
            file=str(self.workbook), program='BSIT', apply='--apply' in extra,
            dry_run='--apply' not in extra, no_teachers=False,
            activate='--activate' in extra,
        )
        return stdout.getvalue()

    def test_dry_run_writes_nothing(self):
        output = self.run_command()
        self.assertIn('DRY RUN', output)
        self.assertEqual(Class.objects.count(), 0)
        self.assertEqual(ClassSlot.objects.count(), 0)
        self.assertEqual(Profile.objects.filter(role=Profile.ROLE_TEACHER).count(), 0)

    def test_apply_creates_classes_and_slots(self):
        self.run_command('--apply')
        self.assertEqual(Class.objects.count(), 3)
        # CC 101 lecture (M, T) + lab (W) -> 3 slots, GE 4 MWF -> 3, IT 201 TTH -> 2
        self.assertEqual(ClassSlot.objects.count(), 8)

    def test_lecture_and_lab_rows_merge_into_one_class(self):
        self.run_command('--apply')
        cc101 = Class.objects.get(class_code='BSIT-1A-CC-101')
        self.assertEqual(cc101.slots.count(), 3)
        self.assertEqual(
            sorted(cc101.slots.values_list('weekday', flat=True)), [0, 1, 2]
        )

    def test_section_and_class_codes(self):
        self.run_command('--apply')
        self.assertTrue(Class.objects.filter(class_code='BSIT-1A-GE-4').exists())
        self.assertTrue(Class.objects.filter(class_code='BSIT-2B-IT-201').exists())
        self.assertEqual(Class.objects.get(class_code='BSIT-2B-IT-201').section_code, 'BSIT-2B')

    def test_second_semester_label_in_file_is_ignored_when_active_year_matches(self):
        self.run_command('--apply')
        self.assertTrue(all(c.academic_year_id == self.ay.id for c in Class.objects.all()))

    def test_placeholder_teacher_created_inactive(self):
        self.run_command('--apply')
        profile = Profile.objects.get(role=Profile.ROLE_TEACHER, user__last_name='Tabligan')
        self.assertFalse(profile.user.is_active)
        self.assertTrue(profile.employee_number.startswith('FAC-TMP-'))

    def test_repeated_run_is_idempotent(self):
        self.run_command('--apply')
        classes, slots, teachers = (
            Class.objects.count(), ClassSlot.objects.count(),
            Profile.objects.filter(role=Profile.ROLE_TEACHER).count(),
        )
        self.run_command('--apply')
        self.assertEqual(Class.objects.count(), classes)
        self.assertEqual(ClassSlot.objects.count(), slots)
        self.assertEqual(Profile.objects.filter(role=Profile.ROLE_TEACHER).count(), teachers)

    def test_room_conflict_keeps_slot_without_room(self):
        # Force both classes into the same room at the same time.
        self.run_command('--apply')
        clash = ClassSlot.objects.filter(class_obj__class_code='BSIT-2B-IT-201').first()
        clash.room = ''
        clash.save(update_fields=['room'])
        ClassSlot.objects.filter(class_obj__class_code='BSIT-1A-GE-4').update(room='LAB 2')

    def test_subject_resolves_to_approved_curriculum_row(self):
        # Catalogue holds both 'CC101' and 'CC 101'; the approved version uses the unspaced one.
        spaced = Subject.objects.create(code='CC 101', name='Introduction to Computing', units=3)
        approved_subject = Subject.objects.create(code='CC101', name='Introduction to Computing', units=3)
        unspaced_only = Subject.objects.create(code='GE 4', name='Mathematics in the Modern World', units=3)
        other_subject = Subject.objects.create(code='IT 201', name='Data Structures', units=3)

        version = CurriculumVersion.objects.create(
            program=self.program, version_number=5, status='APPROVED',
        )
        Curriculum.objects.create(
            program=self.program, subject=approved_subject, year_level=1, semester=1,
            is_major=True, version=version,
        )
        Curriculum.objects.create(
            program=self.program, subject=unspaced_only, year_level=1, semester=1,
            is_major=True, version=version,
        )
        Curriculum.objects.create(
            program=self.program, subject=other_subject, year_level=2, semester=1,
            is_major=True, version=version,
        )

        self.run_command('--apply')
        cc101 = Class.objects.get(class_code='BSIT-1A-CC-101')
        self.assertEqual(cc101.subject_id, approved_subject.id)
        self.assertNotEqual(cc101.subject_id, spaced.id)


class ImportedRoomBindingTests(ImporterTests):
    """The importer must produce the same slot shape the Room Directory expects."""

    def _seed_rooms(self):
        # Migration 0034 seeds the campus rooms, so the labels in the fixture
        # workbook ('ROOM 203', 'LAB 1', 'LAB 2') resolve out of the box.
        return (
            Room.objects.get(code='RM-203'),
            Room.objects.get(code='LAB-1'),
            Room.objects.get(code='LAB-2'),
        )

    def test_imported_slots_bind_room_ref_and_slot_type(self):
        rm203, lab1, _lab2 = self._seed_rooms()

        self.run_command('--apply')

        cc101 = Class.objects.get(class_code='BSIT-1A-CC-101')
        lecture = cc101.slots.get(weekday=0)      # Monday, 'ROOM 203'
        laboratory = cc101.slots.get(weekday=2)   # Wednesday, 'LAB 1'

        self.assertEqual(lecture.room_ref_id, rm203.pk)
        self.assertEqual(lecture.room, 'RM-203')
        self.assertEqual(lecture.slot_type, ClassSlot.SLOT_TYPE_LECTURE)

        self.assertEqual(laboratory.room_ref_id, lab1.pk)
        self.assertEqual(laboratory.room, 'LAB-1')
        self.assertEqual(laboratory.slot_type, ClassSlot.SLOT_TYPE_LABORATORY)

    def test_lab_room_types_the_slot_even_for_a_lecture_subject(self):
        self._seed_rooms()

        self.run_command('--apply')

        it201 = Class.objects.get(class_code='BSIT-2B-IT-201')
        self.assertTrue(
            all(slot.slot_type == ClassSlot.SLOT_TYPE_LABORATORY for slot in it201.slots.all())
        )

    def test_rerun_repairs_a_legacy_string_only_slot(self):
        _rm203, lab1, _lab2 = self._seed_rooms()
        self.run_command('--apply')

        # Simulate a row written the old way: canonical text, no FK, LECTURE.
        ClassSlot.objects.filter(
            class_obj__class_code='BSIT-1A-CC-101', weekday=0,
        ).update(room='RM-203', room_ref=None, slot_type=ClassSlot.SLOT_TYPE_LECTURE)
        ClassSlot.objects.filter(
            class_obj__class_code='BSIT-1A-CC-101', weekday=2,
        ).update(room='LAB-1', room_ref=None, slot_type=ClassSlot.SLOT_TYPE_LECTURE)

        self.run_command('--apply')

        laboratory = ClassSlot.objects.get(
            class_obj__class_code='BSIT-1A-CC-101', weekday=2,
        )
        self.assertEqual(laboratory.room_ref_id, lab1.pk)
        self.assertEqual(laboratory.slot_type, ClassSlot.SLOT_TYPE_LABORATORY)

    def test_unmatched_room_labels_are_reported_and_kept_as_text(self):
        Room.objects.filter(code__in=['RM-203', 'LAB-1', 'LAB-2']).delete()

        output = self.run_command('--apply')

        self.assertIn('unmatched rooms', output)
        self.assertIn('LAB 1', output)
        slot = ClassSlot.objects.get(class_obj__class_code='BSIT-1A-CC-101', weekday=2)
        self.assertIsNone(slot.room_ref_id)
        self.assertEqual(slot.room, 'LAB 1')

    def test_other_building_labels_do_not_collapse_into_main_building_rooms(self):
        # Matches migration 0034: the same number in another building is another room.
        self.assertTrue(Room.objects.filter(code='RM-101').exists())
        self.assertIsNone(resolve_room('ROOM 101 \u00b7 COLLEGE'))
        self.assertIsNotNone(resolve_room('ROOM 101 \u00b7 CMAT'))

    def test_resolve_room_handles_building_suffix_and_room_alias(self):
        rm302, _ = Room.objects.get_or_create(
            code='RM-302',
            defaults={
                'name': 'Room 302',
                'room_type': Room.ROOM_TYPE_LECTURE,
                'capacity': 45,
            },
        )
        self.assertEqual(resolve_room('ROOM 302 \u00b7 CMAT'), rm302)
        self.assertEqual(resolve_room('room 302'), rm302)
        self.assertIsNone(resolve_room('ROOM 999'))
        self.assertIsNone(resolve_room(''))


class SerializerTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CITE', name='College of Information Technology')
        self.program = Program.objects.create(
            code='BSIT', name='BS Information Technology', department=self.department,
        )
        self.subject = Subject.objects.create(code='GE 1', name='Understanding the Self', units=3)
        self.entry = Curriculum.objects.create(
            program=self.program, subject=self.subject, year_level=1, semester=1, is_major=True,
        )

    def test_serializer_exposes_classification(self):
        payload = serialize_curriculum_entry(self.entry, teachers=['Bregabriel, Clair De Mae'])
        self.assertEqual(payload['classification'], CLASSIFICATION_GENERAL_EDUCATION)
        self.assertEqual(payload['classification_label'], 'General Education')
        self.assertTrue(payload['is_major'])
        self.assertEqual(payload['teachers'], ['Bregabriel, Clair De Mae'])

    def test_major_subject_serializes_as_major(self):
        major_subject = Subject.objects.create(code='IT 311', name='Systems Analysis', units=3)
        entry = Curriculum.objects.create(
            program=self.program, subject=major_subject, year_level=3, semester=1, is_major=True,
        )
        payload = serialize_curriculum_entry(entry)
        self.assertEqual(payload['subject_code'], 'IT 311')
        self.assertEqual(payload['subject_code_display'], 'IT 311')
        self.assertEqual(payload['classification'], CLASSIFICATION_MAJOR)
        self.assertEqual(payload['classification_label'], 'Major')
