"""
# // ==============================================================================
# // KCC CLASSSTAMP - WEEK 7 SECTION BUILDER WIZARD TESTS
# // ==============================================================================
# // Covers (A-19):
# //   - Phase 1: Class.program / Class.year_level curriculum context,
# //              assign_class integration, legacy section-code backfill
# //   - Phase 2: schedule_service conflict detection (added later)
# //   - Phase 3: wizard JSON endpoints (added later)
# // ==============================================================================
"""

import io
import json
from datetime import date, time

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import (
    AcademicYear,
    AuditEvent,
    Class,
    ClassSlot,
    Curriculum,
    Department,
    Program,
    Subject,
)
from apps.core.services import (
    assign_class,
    detect_slot_conflicts,
    eligible_teachers_for,
    suggest_section_letter,
    validate_slot_times,
)
from apps.core.tests.test_week5 import BaseWeek5FixtureMixin


# // ==============================================================================
# // A-19 PHASE 1: CLASS CURRICULUM CONTEXT (program / year_level)
# // ==============================================================================
class AssignClassCurriculumContextTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls)
        cls.teacher_user, cls.teacher_profile = cls._make_teacher(cls)
        cls.subject = Subject.objects.create(code='SUBJ-BSIT3', name='Advanced Subject')
        cls.bscs = Program.objects.create(
            department=cls.department, code='BSCS',
            name='BS Computer Science', years_total=4,
        )

    def _assign(self, **overrides):
        kwargs = dict(
            actor=self.admin,
            teacher_profile=self.teacher_profile,
            academic_year=self.academic_year,
            subject=self.subject,
            class_code='BSIT-3A',
        )
        kwargs.update(overrides)
        return assign_class(**kwargs)

    def test_assign_stores_program_and_year_level(self):
        result = self._assign(program=self.program, year_level=3)
        class_obj = Class.objects.get(pk=result['class'].pk)
        self.assertEqual(class_obj.program, self.program)
        self.assertEqual(class_obj.year_level, 3)

    def test_edit_without_program_keeps_existing_context(self):
        created = self._assign(program=self.program, year_level=3)
        result = self._assign(class_obj=created['class'], capacity=45)
        class_obj = Class.objects.get(pk=result['class'].pk)
        self.assertEqual(class_obj.program, self.program)
        self.assertEqual(class_obj.year_level, 3)

    def test_edit_with_program_updates_context(self):
        created = self._assign(program=self.program, year_level=3)
        self._assign(class_obj=created['class'], program=self.bscs, year_level=2)
        created['class'].refresh_from_db()
        self.assertEqual(created['class'].program, self.bscs)
        self.assertEqual(created['class'].year_level, 2)

    def test_assign_without_program_leaves_null(self):
        result = self._assign()
        class_obj = Class.objects.get(pk=result['class'].pk)
        self.assertIsNone(class_obj.program)
        self.assertIsNone(class_obj.year_level)


class BackfillClassProgramTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)  # code='BSIT'
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls)
        cls.teacher_user, cls.teacher_profile = cls._make_teacher(cls)
        cls.bscs = Program.objects.create(
            department=cls.department, code='BSCS',
            name='BS Computer Science', years_total=4,
        )
        cls.bsit_class = cls._make_class(cls, cls.teacher_profile, code='BSIT-3A')
        cls.bscs_class = cls._make_class(cls, cls.teacher_profile, code='BSCS-2B')
        cls.suffixed_class = cls._make_class(cls, cls.teacher_profile, code='BSIT-1A-CS101')
        cls.unparseable_class = cls._make_class(cls, cls.teacher_profile, code='GENERAL')
        cls.unknown_class = cls._make_class(cls, cls.teacher_profile, code='NOPROG-1A')
        cls.prefilled_class = cls._make_class(cls, cls.teacher_profile, code='BSIT-4B')
        cls.prefilled_class.program = cls.program
        cls.prefilled_class.year_level = 4
        cls.prefilled_class.save(update_fields=['program', 'year_level'])

    def _run(self, **kwargs):
        out = io.StringIO()
        call_command('backfill_class_program', stdout=out, **kwargs)
        return out.getvalue()

    def test_backfill_matches_legacy_codes(self):
        self._run()
        self.bsit_class.refresh_from_db()
        self.assertEqual(self.bsit_class.program, self.program)
        self.assertEqual(self.bsit_class.year_level, 3)
        self.bscs_class.refresh_from_db()
        self.assertEqual(self.bscs_class.program, self.bscs)
        self.assertEqual(self.bscs_class.year_level, 2)
        self.suffixed_class.refresh_from_db()
        self.assertEqual(self.suffixed_class.program, self.program)
        self.assertEqual(self.suffixed_class.year_level, 1)

    def test_backfill_skips_unparseable_and_unknown(self):
        self._run()
        self.unparseable_class.refresh_from_db()
        self.assertIsNone(self.unparseable_class.program)
        self.unknown_class.refresh_from_db()
        self.assertIsNone(self.unknown_class.program)

    def test_backfill_does_not_overwrite_existing(self):
        self._run()
        self.prefilled_class.refresh_from_db()
        self.assertEqual(self.prefilled_class.program, self.program)
        self.assertEqual(self.prefilled_class.year_level, 4)

    def test_backfill_dry_run_writes_nothing(self):
        self._run(dry_run=True)
        self.bsit_class.refresh_from_db()
        self.assertIsNone(self.bsit_class.program)
        self.assertIsNone(self.bsit_class.year_level)

    def test_backfill_is_idempotent(self):
        self._run()
        second = self._run()
        self.assertIn('Matched: 0', second)
        self.bsit_class.refresh_from_db()
        self.assertEqual(self.bsit_class.year_level, 3)


# // ==============================================================================
# // A-19 PHASE 2: SCHEDULE CONFLICT DETECTION & TIMETABLE PLANNING
# // ==============================================================================
class ScheduleServiceTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls._make_admin(cls)
        cls.teacher_a_user, cls.teacher_a = cls._make_teacher(cls, username='w7_teacher_a')
        cls.teacher_b_user, cls.teacher_b = cls._make_teacher(cls, username='w7_teacher_b')
        cls.class_a = cls._make_class(cls, cls.teacher_a, code='W7-A')
        cls.class_b = cls._make_class(cls, cls.teacher_b, code='W7-B')

    def _slot(self, class_obj, weekday=0, start_h=8, end_h=9, room='IT-Lab 1', active=True):
        return ClassSlot.objects.create(
            class_obj=class_obj, weekday=weekday,
            starts_at=time(start_h, 0), ends_at=time(end_h, 0),
            room=room, is_active=active,
        )

    def _detect(self, teacher, weekday=0, start_h=8, end_h=9, room=None, exclude=()):
        return detect_slot_conflicts(
            teacher_profile_id=teacher.pk,
            weekday=weekday,
            starts_at=time(start_h, 0),
            ends_at=time(end_h, 0),
            room=room,
            exclude_slot_ids=exclude,
        )

    def test_validate_rejects_inverted_or_equal_window(self):
        with self.assertRaises(ValueError):
            validate_slot_times(time(9, 0), time(8, 0))
        with self.assertRaises(ValueError):
            validate_slot_times(time(9, 0), time(9, 0))
        with self.assertRaises(ValueError):
            validate_slot_times(None, time(9, 0))

    def test_teacher_overlap_detected(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9)
        conflicts = self._detect(self.teacher_a, start_h=8, end_h=9)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], 'teacher')
        self.assertEqual(conflicts[0]['class_code'], 'W7-A')

    def test_partial_overlap_detected(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9)
        conflicts = detect_slot_conflicts(
            teacher_profile_id=self.teacher_a.pk, weekday=0,
            starts_at=time(8, 30), ends_at=time(9, 30),
        )
        self.assertEqual(len(conflicts), 1)

    def test_boundary_touch_is_not_a_conflict(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9)
        conflicts = self._detect(self.teacher_a, start_h=9, end_h=10)
        self.assertEqual(conflicts, [])

    def test_different_teacher_same_window_no_conflict(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9, room='IT-Lab 1')
        conflicts = self._detect(self.teacher_b, start_h=8, end_h=9, room='IT-Lab 2')
        self.assertEqual(conflicts, [])

    def test_room_conflict_detected(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9, room='IT-Lab 1')
        conflicts = detect_slot_conflicts(
            teacher_profile_id=self.teacher_b.pk, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='IT-Lab 1',
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], 'room')
        self.assertEqual(conflicts[0]['class_code'], 'W7-A')

    def test_room_conflict_case_insensitive(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9, room='IT-Lab 1')
        conflicts = detect_slot_conflicts(
            teacher_profile_id=self.teacher_b.pk, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='it-lab 1',
        )
        self.assertEqual(len(conflicts), 1)

    def test_tba_rooms_never_clash(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9, room='TBA')
        conflicts = detect_slot_conflicts(
            teacher_profile_id=self.teacher_b.pk, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='TBA',
        )
        self.assertEqual(conflicts, [])

    def test_excluded_slots_are_skipped(self):
        slot = self._slot(self.class_a, weekday=0, start_h=8, end_h=9)
        conflicts = detect_slot_conflicts(
            teacher_profile_id=self.teacher_a.pk, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), exclude_slot_ids=[slot.pk],
        )
        self.assertEqual(conflicts, [])

    def test_inactive_slots_are_ignored(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9, active=False)
        conflicts = self._detect(self.teacher_a, start_h=8, end_h=9)
        self.assertEqual(conflicts, [])

    def test_suggest_first_letter(self):
        code = suggest_section_letter(
            academic_year=self.academic_year, program=self.program, year_level=3,
        )
        self.assertEqual(code, 'BSIT-3A')

    def test_suggest_skips_taken_letters(self):
        self._make_class(self.teacher_a, code='BSIT-3A')
        code = suggest_section_letter(
            academic_year=self.academic_year, program=self.program, year_level=3,
        )
        self.assertEqual(code, 'BSIT-3B')

    def test_suggest_respects_legacy_codes(self):
        self._make_class(self.teacher_a, code='BSIT-3A')
        # Legacy row with program not backfilled still reserves its code
        Class.objects.create(
            academic_year=self.academic_year, class_code='BSIT-3B',
            subject=Subject.objects.create(code='SUBJ-LG', name='Legacy Subject'),
            teacher_profile=self.teacher_a,
        )
        code = suggest_section_letter(
            academic_year=self.academic_year, program=self.program, year_level=3,
        )
        self.assertEqual(code, 'BSIT-3C')

    def test_suggest_requires_program_and_year(self):
        with self.assertRaises(ValueError):
            suggest_section_letter(academic_year=self.academic_year, program=None, year_level=3)
        with self.assertRaises(ValueError):
            suggest_section_letter(
                academic_year=self.academic_year, program=self.program, year_level=None,
            )

    def test_eligible_teachers_ranked_by_load(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9)
        self._slot(self.class_a, weekday=1, start_h=8, end_h=9)
        other_dept = Department.objects.create(code='CBA', name='College of Business')
        self.teacher_b.department = other_dept
        self.teacher_b.save(update_fields=['department'])

        eligible = eligible_teachers_for(self.program)
        self.assertEqual([e['name'] for e in eligible], ['w7_teacher_a'])

    def test_eligible_teachers_excludes_inactive_users(self):
        self.teacher_a_user.is_active = False
        self.teacher_a_user.save(update_fields=['is_active'])
        eligible = eligible_teachers_for(self.program)
        self.assertNotIn('w7_teacher_a', [e['name'] for e in eligible])

    def test_eligible_teachers_lightest_load_first(self):
        self._slot(self.class_a, weekday=0, start_h=8, end_h=9)
        self._slot(self.class_a, weekday=1, start_h=8, end_h=9)
        eligible = eligible_teachers_for(self.program)
        self.assertEqual(len(eligible), 2)
        self.assertEqual(eligible[0]['name'], 'w7_teacher_b')
        self.assertEqual(eligible[0]['active_slots'], 0)
        self.assertEqual(eligible[1]['name'], 'w7_teacher_a')
        self.assertEqual(eligible[1]['active_slots'], 2)


class SlotSaveConflictViewTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls)
        cls.teacher_a_user, cls.teacher_a = cls._make_teacher(cls, username='w7_view_ta')
        cls.teacher_b_user, cls.teacher_b = cls._make_teacher(cls, username='w7_view_tb')
        cls.class_a = cls._make_class(cls, cls.teacher_a, code='WV-A')
        cls.class_b = cls._make_class(cls, cls.teacher_b, code='WV-B')

    def setUp(self):
        self.client.force_login(self.admin)

    def _post(self, class_obj, weekday=0, starts='08:00', ends='09:00', room=''):
        return self.client.post(
            reverse('class_slot_save', args=[class_obj.pk]),
            data={'weekday': weekday, 'starts_at': starts, 'ends_at': ends, 'room': room},
        )

    def test_inverted_window_rejected(self):
        res = self._post(self.class_b, starts='09:00', ends='08:00')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_bad_time_format_rejected(self):
        res = self._post(self.class_b, starts='8am', ends='09:00')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_teacher_conflict_blocks_save(self):
        ClassSlot.objects.create(
            class_obj=self.class_a, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='IT-Lab 1',
        )
        res = self._post(self.class_a, starts='08:30', ends='09:30')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])
        self.assertIn('WV-A', res.json()['message'])
        self.assertEqual(ClassSlot.objects.filter(class_obj=self.class_a).count(), 1)

    def test_room_conflict_warns_but_saves(self):
        ClassSlot.objects.create(
            class_obj=self.class_a, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='IT-Lab 1',
        )
        res = self._post(self.class_b, starts='08:30', ends='09:30', room='IT-Lab 1')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['warnings'])
        self.assertIn('WV-A', data['warnings'][0])
        self.assertEqual(ClassSlot.objects.filter(class_obj=self.class_b).count(), 1)

    def test_clean_save_has_no_warnings(self):
        res = self._post(self.class_b, weekday=2, starts='08:00', ends='09:00', room='RM-2')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['warnings'], [])


# // ==============================================================================
# // A-19 PHASE 3: SECTION BUILDER WIZARD JSON ENDPOINTS
# // ==============================================================================
class WizardOptionsTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls, username='w7_wiz_admin')
        cls.teacher_user, cls.teacher_profile = cls._make_teacher(cls, username='w7_wiz_teacher')
        cls.subject = Subject.objects.create(code='WIZ-SUBJ', name='Wizard Subject', units=4)
        cls.wrong_year = Subject.objects.create(code='WIZ-WRONG', name='Wrong Year Subject')
        cls.inactive_subject = Subject.objects.create(
            code='WIZ-DEAD', name='Inactive Subject', is_active=False,
        )
        Curriculum.objects.create(program=cls.program, year_level=3, semester=1, subject=cls.subject)
        Curriculum.objects.create(program=cls.program, year_level=2, semester=1, subject=cls.wrong_year)
        Curriculum.objects.create(program=cls.program, year_level=3, semester=1, subject=cls.inactive_subject)

    def setUp(self):
        self.client.force_login(self.admin)

    def _get(self, **overrides):
        params = {
            'program_id': self.program.pk,
            'year_level': 3,
            'semester': 1,
        }
        params.update(overrides)
        return self.client.get(reverse('class_wizard_options'), data=params)

    def test_returns_subjects_teachers_and_suggested_code(self):
        res = self._get()
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['academic_year']['id'], self.academic_year.pk)
        codes = [s['code'] for s in data['subjects']]
        self.assertIn('WIZ-SUBJ', codes)
        self.assertNotIn('WIZ-WRONG', codes)
        self.assertNotIn('WIZ-DEAD', codes)
        self.assertEqual(data['subjects'][0]['units'], 4)
        self.assertEqual([t['name'] for t in data['teachers']], ['w7_wiz_teacher'])
        self.assertTrue(data['suggested_code'].startswith('BSIT-3'))

    def test_suggested_code_skips_existing_sections(self):
        self._make_class(self.teacher_profile, code='BSIT-3A')
        data = self._get().json()
        self.assertEqual(data['suggested_code'], 'BSIT-3B')

    def test_explicit_academic_year_override(self):
        other_ay = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31), is_active=False,
        )
        data = self._get(ay_id=other_ay.pk).json()
        self.assertEqual(data['academic_year']['id'], other_ay.pk)

    def test_missing_params_returns_400(self):
        res = self.client.get(reverse('class_wizard_options'))
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_invalid_semester_returns_400(self):
        res = self._get(semester=9)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_unknown_program_returns_404(self):
        res = self._get(program_id=999999)
        self.assertEqual(res.status_code, 404)

    def test_teacher_role_redirects(self):
        client = Client()
        client.force_login(self.teacher_user)
        res = client.get(reverse('class_wizard_options'), data={
            'program_id': self.program.pk, 'year_level': 3, 'semester': 1,
        })
        self.assertEqual(res.status_code, 302)


class WizardOptionsNoActiveAyTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.academic_year.is_active = False
        cls.academic_year.save(update_fields=['is_active'])
        cls.admin = cls._make_admin(cls, username='w7_noay_admin')

    def test_no_active_ay_returns_400(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('class_wizard_options'), data={
            'program_id': self.program.pk, 'year_level': 3, 'semester': 1,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('No active academic year', res.json()['message'])


class WizardSaveTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls, username='w7_save_admin')
        cls.teacher_a_user, cls.teacher_a = cls._make_teacher(cls, username='w7_save_ta')
        cls.teacher_b_user, cls.teacher_b = cls._make_teacher(cls, username='w7_save_tb')
        cls.subject = Subject.objects.create(code='SAVE-SUBJ', name='Save Subject')
        cls.subject_four = Subject.objects.create(code='SAVE-SUBJ4', name='Four Unit Subject', units=4)
        Curriculum.objects.create(program=cls.program, year_level=3, semester=1, subject=cls.subject)

    def setUp(self):
        self.client.force_login(self.admin)

    def _post(self, **overrides):
        data = {
            'program_id': self.program.pk,
            'year_level': 3,
            'subject_id': self.subject.pk,
            'teacher_profile_id': self.teacher_a.pk,
            'ay_id': self.academic_year.pk,
            'class_code': 'bsit-3z',
            'capacity': '40',
            'grace_minutes': '10',
            'slots': json.dumps([
                {'weekday': 0, 'starts_at': '08:00', 'ends_at': '09:00', 'room': 'RM-1'},
                {'weekday': 2, 'starts_at': '10:00', 'ends_at': '12:00', 'room': ''},
            ]),
        }
        data.update(overrides)
        return self.client.post(reverse('class_wizard_save'), data=data)

    def _slot(self, class_obj, weekday=0, start_h=8, end_h=9, room='IT-Lab 1'):
        return ClassSlot.objects.create(
            class_obj=class_obj, weekday=weekday,
            starts_at=time(start_h, 0), ends_at=time(end_h, 0), room=room,
        )

    def test_creates_class_slots_and_audits(self):
        res = self._post()
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        class_obj = Class.objects.get(pk=data['class_id'])
        self.assertEqual(class_obj.class_code, 'BSIT-3Z')
        self.assertEqual(class_obj.program, self.program)
        self.assertEqual(class_obj.year_level, 3)
        self.assertEqual(class_obj.capacity, 40)
        self.assertEqual(class_obj.grace_minutes, 10)
        self.assertEqual(data['warnings'], [])
        slots = list(class_obj.slots.order_by('weekday'))
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0].room, 'RM-1')
        self.assertEqual(slots[1].room, 'TBA')
        self.assertEqual(
            AuditEvent.objects.filter(action='ADD_CLASS_SLOT', object_type='ClassSlot').count(),
            2,
        )
        self.assertTrue(
            AuditEvent.objects.filter(object_type='Class', object_id=str(class_obj.pk)).exists()
        )

    def test_empty_schedule_rejected_for_units(self):
        res = self._post(slots='[]')
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn("don't match subject units", data['message'])
        self.assertFalse(Class.objects.filter(class_code='BSIT-3Z').exists())

    def test_hours_mismatch_rejected(self):
        res = self._post(subject_id=self.subject_four.pk)  # 4 units but only 3h submitted
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn('SAVE-SUBJ4', data['message'])
        self.assertIn('4h', data['message'])
        self.assertIn('3h', data['message'])

    def test_split_sessions_matching_units_ok(self):
        res = self._post(slots=json.dumps([
            {'weekday': 0, 'starts_at': '08:00', 'ends_at': '09:30', 'room': 'RM-1'},
            {'weekday': 2, 'starts_at': '13:00', 'ends_at': '14:30', 'room': 'RM-1'},
        ]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['slots']), 2)

    def test_duplicate_class_code_returns_400(self):
        self._make_class(self.teacher_a, code='BSIT-3Z')
        res = self._post()
        self.assertEqual(res.status_code, 400)
        self.assertIn('already exists', res.json()['message'])

    def test_teacher_conflict_blocks_atomically(self):
        existing = self._make_class(self.teacher_a, code='SAVE-EXISTING')
        self._slot(existing, weekday=0, start_h=8, end_h=9)
        res = self._post(slots=json.dumps([
            {'weekday': 0, 'starts_at': '08:30', 'ends_at': '09:30', 'room': 'RM-1'},
            {'weekday': 2, 'starts_at': '08:00', 'ends_at': '10:00', 'room': 'RM-1'},
        ]))
        self.assertEqual(res.status_code, 400)
        self.assertIn('SAVE-EXISTING', res.json()['message'])
        self.assertFalse(Class.objects.filter(class_code='BSIT-3Z').exists())
        self.assertEqual(ClassSlot.objects.filter(class_obj__class_code='BSIT-3Z').count(), 0)

    def test_overlapping_submitted_slots_400(self):
        res = self._post(slots=json.dumps([
            {'weekday': 0, 'starts_at': '08:00', 'ends_at': '10:00', 'room': 'RM-1'},
            {'weekday': 0, 'starts_at': '09:00', 'ends_at': '11:00', 'room': 'RM-1'},
        ]))
        self.assertEqual(res.status_code, 400)
        self.assertIn('overlap', res.json()['message'])

    def test_adjacent_submitted_slots_do_not_clash(self):
        res = self._post(slots=json.dumps([
            {'weekday': 0, 'starts_at': '08:00', 'ends_at': '09:00', 'room': 'RM-1'},
            {'weekday': 0, 'starts_at': '09:00', 'ends_at': '10:00', 'room': 'RM-1'},
            {'weekday': 0, 'starts_at': '10:00', 'ends_at': '11:00', 'room': 'RM-1'},
        ]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

    def test_room_conflict_warns_but_saves(self):
        existing = self._make_class(self.teacher_b, code='SAVE-ROOM')
        self._slot(existing, weekday=0, start_h=8, end_h=9, room='IT-Lab 1')
        res = self._post(slots=json.dumps([
            {'weekday': 0, 'starts_at': '08:30', 'ends_at': '09:30', 'room': 'IT-Lab 1'},
            {'weekday': 2, 'starts_at': '08:00', 'ends_at': '10:00', 'room': 'IT-Lab 1'},
        ]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['warnings'])
        self.assertIn('SAVE-ROOM', data['warnings'][0])

    def test_bad_slots_json_400(self):
        res = self._post(slots='not-json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('JSON array', res.json()['message'])

    def test_inverted_window_400(self):
        res = self._post(slots=json.dumps([
            {'weekday': 0, 'starts_at': '09:00', 'ends_at': '08:00', 'room': 'RM-1'},
        ]))
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_bad_weekday_400(self):
        res = self._post(slots=json.dumps([
            {'weekday': 7, 'starts_at': '08:00', 'ends_at': '09:00', 'room': 'RM-1'},
        ]))
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_missing_required_fields_400(self):
        res = self._post(class_code='')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_year_level_out_of_range_400(self):
        res = self._post(year_level=9)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_teacher_role_redirects(self):
        client = Client()
        client.force_login(self.teacher_b_user)
        res = client.post(reverse('class_wizard_save'), data={
            'program_id': self.program.pk,
            'year_level': 3,
            'subject_id': self.subject.pk,
            'teacher_profile_id': self.teacher_a.pk,
            'ay_id': self.academic_year.pk,
            'class_code': 'BSIT-3Z',
            'slots': '[]',
        })
        self.assertEqual(res.status_code, 302)


class SubjectUnitsTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls, username='w7_units_admin')

    def setUp(self):
        self.client.force_login(self.admin)

    def _save(self, code, name, **overrides):
        data = {'code': code, 'name': name, 'is_active': '1'}
        data.update(overrides)
        return self.client.post(reverse('subject_save'), data=data)

    def test_units_default_to_three(self):
        res = self._save('UNITS101', 'Default Units Subject')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['subject']['units'], 3)
        self.assertEqual(Subject.objects.get(code='UNITS101').units, 3)

    def test_explicit_units_saved(self):
        res = self._save('UNITS102', 'Five Unit Subject', units='5')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['subject']['units'], 5)

    def test_zero_units_rejected(self):
        res = self._save('UNITS103', 'Zero Units', units='0')
        self.assertEqual(res.status_code, 400)
        self.assertIn('at least 1', res.json()['error'])

    def test_non_numeric_units_rejected(self):
        res = self._save('UNITS104', 'Bad Units', units='abc')
        self.assertEqual(res.status_code, 400)
        self.assertIn('whole number', res.json()['error'])


# // ==============================================================================
# // A-19 PHASE 4: WIZARD PAGE & LIVE SLOT CONFLICT CHECK
# // ==============================================================================
class WizardSetupPageTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls, username='w7_page_admin')
        cls.teacher_user, cls.teacher_profile = cls._make_teacher(cls, username='w7_page_teacher')

    def test_setup_page_renders_for_admin(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('class_wizard_setup'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Section Builder Wizard')
        self.assertContains(res, 'wizard-boot')

    def test_setup_page_teacher_redirects(self):
        self.client.force_login(self.teacher_user)
        res = self.client.get(reverse('class_wizard_setup'))
        self.assertEqual(res.status_code, 302)


class WizardSlotsCheckTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls, username='w7_check_admin')
        cls.teacher_a_user, cls.teacher_a = cls._make_teacher(cls, username='w7_check_ta')
        cls.teacher_b_user, cls.teacher_b = cls._make_teacher(cls, username='w7_check_tb')

    def setUp(self):
        self.client.force_login(self.admin)

    def _post(self, slots, teacher=None):
        return self.client.post(reverse('class_wizard_slots_check'), data={
            'teacher_profile_id': (teacher or self.teacher_a).pk,
            'slots': slots if isinstance(slots, str) else json.dumps(slots),
        })

    def test_clean_slots_have_no_conflicts(self):
        res = self._post([{'weekday': 0, 'starts_at': '08:00', 'ends_at': '09:00', 'room': 'RM-1'}])
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_minutes'], 60)
        self.assertEqual(data['slots'][0]['teacher'], [])
        self.assertEqual(data['slots'][0]['room'], [])

    def test_teacher_conflict_reported_per_slot(self):
        existing = self._make_class(self.teacher_a, code='CHECK-EXIST')
        ClassSlot.objects.create(
            class_obj=existing, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='IT-Lab 1',
        )
        res = self._post([{'weekday': 0, 'starts_at': '08:30', 'ends_at': '09:30', 'room': ''}])
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('CHECK-EXIST', data['slots'][0]['teacher'][0])

    def test_room_conflict_reported_per_slot(self):
        existing = self._make_class(self.teacher_b, code='CHECK-ROOM')
        ClassSlot.objects.create(
            class_obj=existing, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='IT-Lab 1',
        )
        res = self._post([{'weekday': 0, 'starts_at': '08:30', 'ends_at': '09:30', 'room': 'IT-Lab 1'}])
        data = res.json()
        self.assertEqual(data['slots'][0]['teacher'], [])
        self.assertIn('CHECK-ROOM', data['slots'][0]['room'][0])

    def test_nothing_saved(self):
        before_classes = Class.objects.count()
        before_slots = ClassSlot.objects.count()
        self._post([{'weekday': 0, 'starts_at': '08:00', 'ends_at': '09:00', 'room': 'RM-1'}])
        self.assertEqual(Class.objects.count(), before_classes)
        self.assertEqual(ClassSlot.objects.count(), before_slots)

    def test_bad_json_400(self):
        res = self._post('not-json')
        self.assertEqual(res.status_code, 400)

    def test_inverted_window_400(self):
        res = self._post([{'weekday': 0, 'starts_at': '09:00', 'ends_at': '08:00', 'room': ''}])
        self.assertEqual(res.status_code, 400)

    def test_overlapping_submitted_slots_400(self):
        res = self._post([
            {'weekday': 0, 'starts_at': '08:00', 'ends_at': '10:00', 'room': ''},
            {'weekday': 0, 'starts_at': '09:00', 'ends_at': '11:00', 'room': ''},
        ])
        self.assertEqual(res.status_code, 400)

    def test_teacher_role_redirects(self):
        client = Client()
        client.force_login(self.teacher_b_user)
        res = client.post(reverse('class_wizard_slots_check'), data={
            'teacher_profile_id': self.teacher_a.pk, 'slots': '[]',
        })
        self.assertEqual(res.status_code, 302)
