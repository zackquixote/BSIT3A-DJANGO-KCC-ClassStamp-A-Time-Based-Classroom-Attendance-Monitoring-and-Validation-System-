"""Tests for the registrar-style section timetable sheet."""

import datetime

from django.test import TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear, Class, ClassSlot, Department, Profile, Program, Subject,
)
from apps.core.views.timetable_views import (
    academic_year_label, build_meeting_rows, build_occupancy, build_section_sheet,
    display_code, display_section, format_clock, format_days, normalize_section,
)


class FormattingTests(TestCase):
    def test_format_days_matches_workbook_style(self):
        self.assertEqual(format_days([0, 2, 4]), 'MWF')
        self.assertEqual(format_days([1, 3]), 'TTH')
        self.assertEqual(format_days([0, 1]), 'MT')
        self.assertEqual(format_days([2]), 'W')

    def test_format_clock_is_twelve_hour(self):
        self.assertEqual(format_clock(datetime.time(8, 30)), '8:30 AM')
        self.assertEqual(format_clock(datetime.time(13, 0)), '1:00 PM')
        self.assertEqual(format_clock(datetime.time(0, 5)), '12:05 AM')
        self.assertEqual(format_clock(datetime.time(12, 0)), '12:00 PM')

    def test_display_code_adds_the_workbook_space(self):
        self.assertEqual(display_code('CC101'), 'CC 101')
        self.assertEqual(display_code('IT201'), 'IT 201')
        self.assertEqual(display_code('GE 1'), 'GE 1')
        self.assertEqual(display_code('PATHfit 1'), 'PATHfit 1')
        self.assertEqual(display_code('CAP 102'), 'CAP 102')

    def test_display_and_normalise_section(self):
        self.assertEqual(display_section('BSIT-1A'), 'BSIT 1A')
        self.assertEqual(display_section('BSIT 4C'), 'BSIT 4C')
        self.assertEqual(normalize_section('BSIT 1A'), normalize_section('bsit-1a'))

    def test_academic_year_label_drops_the_term(self):
        self.assertEqual(academic_year_label('2026-2027 1st Sem'), '2026-2027')
        self.assertEqual(academic_year_label(''), '')


class SheetTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CMAT', name='College of Management')
        self.program = Program.objects.create(
            code='BSIT', name='Bachelor of Science in Information Technology',
            department=self.department,
        )
        self.term = AcademicYear.objects.create(
            name='2026-2027 1st Sem', starts_on=datetime.date(2026, 8, 1),
            ends_on=datetime.date(2027, 5, 31), is_active=True,
        )
        self.teacher = self.make_teacher('Tabligan', 'Lezeth Rose')

    def make_teacher(self, last, first):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(
            username=f'{first}.{last}'.lower().replace(' ', ''), password='x',
            first_name=first, last_name=last,
        )
        return Profile.objects.create(user=user, role=Profile.ROLE_TEACHER)

    def make_class(self, subject, section='BSIT-1A', code=None, teacher=None):
        class_obj = Class.objects.create(
            academic_year=self.term,
            section_code=section,
            class_code=code or f'{section}-{subject.code.replace(" ", "")}',
            subject=subject,
            teacher_profile=teacher or self.teacher,
            program=self.program,
            year_level=1,
            is_active=True,
        )
        return class_obj

    def test_lecture_and_lab_render_as_two_rows(self):
        subject = Subject.objects.create(code='CC 101', name='Introduction to Computing', units=3)
        class_obj = self.make_class(subject)
        ClassSlot.objects.create(class_obj=class_obj, weekday=0, starts_at=datetime.time(13, 0),
                                 ends_at=datetime.time(14, 0), room='LAB 1')
        ClassSlot.objects.create(class_obj=class_obj, weekday=1, starts_at=datetime.time(13, 0),
                                 ends_at=datetime.time(14, 0), room='LAB 1')
        ClassSlot.objects.create(class_obj=class_obj, weekday=2, starts_at=datetime.time(13, 0),
                                 ends_at=datetime.time(16, 0), room='LAB 1')

        rows = build_meeting_rows(class_obj)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['days'], 'MT')
        self.assertEqual(rows[0]['time'], '1:00 PM - 2:00 PM')
        self.assertEqual(rows[0]['hours_label'], '2')
        self.assertEqual(rows[1]['days'], 'W')
        self.assertEqual(rows[1]['hours_label'], '3')

    def test_sheet_totals_match_the_workbook(self):
        # GE 4 MWF -> 3 hrs, ACCT 1 TTH 1.5h -> 3 hrs, PATHfit 1 MW -> 2 hrs
        cases = [
            ('GE 4', 'Mathematics in the Modern World', 3, [0, 2, 4], datetime.time(8, 30), datetime.time(9, 30), '3'),
            ('ACCT 1', 'Principles of Accounting', 3, [1, 3], datetime.time(16, 0), datetime.time(17, 30), '3'),
            ('PATHfit 1', 'Movement Competency Training', 2, [0, 2], datetime.time(10, 30), datetime.time(11, 30), '2'),
        ]
        classes = []
        for code, name, units, days, start, end, _expected in cases:
            subject = Subject.objects.create(code=code, name=name, units=units)
            class_obj = self.make_class(subject)
            for day in days:
                ClassSlot.objects.create(class_obj=class_obj, weekday=day, starts_at=start,
                                         ends_at=end, room='ROOM 203')
            classes.append(class_obj)

        sheet = build_section_sheet('BSIT-1A', classes)
        self.assertEqual(sheet['subject_count'], 3)
        self.assertEqual(sheet['total_units'], 8)
        self.assertEqual(sheet['total_hours_label'], '8')
        self.assertEqual([row['hours_label'] for row in sheet['rows']], ['3', '3', '2'])

    def test_room_label_splits_building_from_room(self):
        subject = Subject.objects.create(code='GE 1', name='Understanding the Self', units=3)
        class_obj = self.make_class(subject)
        ClassSlot.objects.create(class_obj=class_obj, weekday=0, starts_at=datetime.time(18, 0),
                                 ends_at=datetime.time(19, 0), room='ROOM 107 · HS')

        sheet = build_section_sheet('BSIT-1A', [class_obj])
        self.assertEqual(sheet['rows'][0]['room_main'], 'ROOM 107')
        self.assertEqual(sheet['rows'][0]['room_building'], 'HS')

    def test_class_without_slots_still_appears(self):
        subject = Subject.objects.create(code='NSTP 1', name='ROTC 1/ CWTS1', units=3)
        class_obj = self.make_class(subject)
        sheet = build_section_sheet('BSIT-1A', [class_obj])
        self.assertEqual(len(sheet['rows']), 1)
        self.assertEqual(sheet['rows'][0]['days'], '—')
        self.assertFalse(sheet['rows'][0]['has_schedule'])
        self.assertEqual(sheet['total_units'], 3)

    def test_view_renders_section_sheet(self):
        subject = Subject.objects.create(code='GE 1', name='Understanding the Self', units=3)
        class_obj = self.make_class(subject)
        ClassSlot.objects.create(class_obj=class_obj, weekday=0, starts_at=datetime.time(18, 0),
                                 ends_at=datetime.time(19, 0), room='ROOM 107 · HS')

        admin = self.make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse('section_timetable'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Understanding the Self')
        self.assertContains(response, 'Lezeth Rose Tabligan')
        self.assertContains(response, 'ROOM 107')
        self.assertContains(response, 'HS')
        self.assertContains(response, 'A.Y. 2026-2027')
        self.assertContains(response, 'Total — 1 subjects')

    def test_occupancy_cells_carry_both_times_for_sorting(self):
        subject = Subject.objects.create(code='GE 1', name='Understanding the Self', units=3)
        class_obj = self.make_class(subject)
        ClassSlot.objects.create(
            class_obj=class_obj, weekday=0, starts_at=datetime.time(18, 0),
            ends_at=datetime.time(19, 0), room='ROOM 107',
        )

        rows = build_occupancy(self.term, 'rooms')

        self.assertEqual(rows[0]['label'], 'ROOM 107')
        cells = [cell for day in rows[0]['days'] for cell in day['cells']]
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]['starts_at'], datetime.time(18, 0))
        self.assertEqual(cells[0]['ends_at'], datetime.time(19, 0))
        self.assertIn('room 107', rows[0]['search_text'])
        self.assertIn('ge 1', rows[0]['search_text'])

    def test_rooms_and_teachers_week_views_render(self):
        subject = Subject.objects.create(code='GE 1', name='Understanding the Self', units=3)
        class_obj = self.make_class(subject)
        ClassSlot.objects.create(
            class_obj=class_obj, weekday=0, starts_at=datetime.time(18, 0),
            ends_at=datetime.time(19, 0), room='ROOM 107',
        )
        admin = self.make_admin()
        self.client.force_login(admin)

        rooms = self.client.get(reverse('section_timetable'), {'view': 'rooms'})
        self.assertEqual(rooms.status_code, 200)
        self.assertContains(rooms, 'Rooms this week')
        self.assertContains(rooms, 'ROOM 107')
        self.assertContains(rooms, 'occ-card')
        self.assertContains(rooms, 'id="occSearch"')
        self.assertContains(rooms, 'data-search=')

        teachers = self.client.get(reverse('section_timetable'), {'view': 'teachers'})
        self.assertEqual(teachers.status_code, 200)
        self.assertContains(teachers, 'Teachers this week')
        self.assertContains(teachers, 'Lezeth Rose Tabligan')
        self.assertContains(teachers, 'occ-card')
        self.assertContains(teachers, 'id="occSearch"')

    def test_section_filter_accepts_spaced_workbook_label(self):
        subject = Subject.objects.create(code='GE 1', name='Understanding the Self', units=3)
        self.make_class(subject, section='BSIT-1A')
        other = Subject.objects.create(code='GE 2', name='Readings in Philippine History', units=3)
        self.make_class(other, section='BSIT-2B')

        admin = self.make_admin()
        self.client.force_login(admin)
        response = self.client.get(reverse('section_timetable'), {'section': 'BSIT 1A'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Understanding the Self')
        self.assertNotContains(response, 'Readings in Philippine History')

    def test_requires_admin(self):
        from django.contrib.auth import get_user_model
        student_user = get_user_model().objects.create_user(
            username='student1', password='x', first_name='Stu', last_name='Dent',
        )
        Profile.objects.create(user=student_user, role=Profile.ROLE_STUDENT)
        self.client.force_login(student_user)
        response = self.client.get(reverse('section_timetable'))
        self.assertIn(response.status_code, (302, 403))

    def make_admin(self):
        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.create_user(
            username='admin_tt', password='x', first_name='Ada', last_name='Min',
        )
        Profile.objects.create(user=admin, role=Profile.ROLE_ADMIN)
        return admin
