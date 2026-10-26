"""
# // ==============================================================================
# // KCC CLASSSTAMP - WEEK 4+ EXPERIENCE & RESILIENCE TESTS
# // ==============================================================================
# // Covers:
# //   - A-07: Curriculum matrix builder (semester dimension, assign/remove/list)
# //   - A-08: Academic term rollover wizard (atomic deactivate + promotion)
# //   - S-07: Server-issued single-use offline QR badge (issue + redeem)
# //   - S-08: Online excuse slip workflow (submit, approve, reject, authz)
# // T-07 (kiosk mode) and T-12 (IndexedDB buffer) are frontend-only and are
# //   exercised manually in the browser; their controllers are syntax-checked.
# // ==============================================================================
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Curriculum,
    Department,
    Enrollment,
    ExcuseSlip,
    OfflineBadge,
    Profile,
    Program,
    Subject,
)
from apps.core.services import rollover_academic_year

User = get_user_model()


class BaseWeek4FixtureMixin:
    def _make_department(self):
        return Department.objects.create(code='CCS', name='College of Computer Studies')

    def _make_program(self):
        return Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )

    def _make_academic_year(self, name='2025-2026', is_active=True):
        return AcademicYear.objects.create(
            name=name, starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31), is_active=is_active,
        )

    def _make_teacher(self, username):
        user = User.objects.create_user(username=username, password='Teacher!Pass123')
        profile = Profile.objects.create(
            user=user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        return user, profile

    def _make_admin(self, username):
        user = User.objects.create_user(username=username, password='Admin!Pass123')
        profile = Profile.objects.create(user=user, role=Profile.ROLE_ADMIN)
        return user, profile

    def _make_student(self, username, student_number, year_level=1, approval_status=None):
        user = User.objects.create_user(
            username=username, password='Student!Pass123', first_name='Ana', last_name='Cruz',
        )
        profile = Profile.objects.create(
            user=user, role=Profile.ROLE_STUDENT, student_number=student_number,
            program=self.program, year_level=year_level,
            approval_status=approval_status or Profile.APPROVAL_APPROVED,
            qr_secret='a' * 64,
        )
        return user, profile

    def _make_class(self, teacher_profile, subject, code='BSIT-1A'):
        return Class.objects.create(
            academic_year=self.academic_year, class_code=code,
            subject=subject, teacher_profile=teacher_profile, grace_minutes=10,
        )

    def _make_slot(self, class_obj, weekday, starts_at, ends_at, room='Room 1'):
        return ClassSlot.objects.create(
            class_obj=class_obj, weekday=weekday,
            starts_at=starts_at, ends_at=ends_at, room=room, is_active=True,
        )

    def _make_session(self, slot, session_date, status=ClassSession.STATUS_CLOSED):
        return ClassSession.objects.create(
            slot=slot, session_date=session_date, status=status,
        )


# // ==============================================================================
# // A-07: CURRICULUM MATRIX BUILDER
# // ==============================================================================
class CurriculumMatrixTests(TestCase, BaseWeek4FixtureMixin):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()
        self.academic_year = self._make_academic_year()
        self.admin_user, self.admin_profile = self._make_admin('curr_admin')
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.client.force_login(self.admin_user)

    def _assign(self, subject_id, year_level, semester):
        return self.client.post(reverse('subject_curriculum_assign'), {
            'subject_id': subject_id,
            'program_id': self.program.id,
            'year_level': year_level,
            'semester': semester,
        })

    def test_assign_creates_entry_with_semester(self):
        res = self._assign(self.subject.id, 1, 2)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        entry = Curriculum.objects.get(pk=data['entry']['id'])
        self.assertEqual(entry.year_level, 1)
        self.assertEqual(entry.semester, 2)
        self.assertEqual(entry.subject, self.subject)

    def test_same_subject_same_semester_is_duplicate(self):
        self._assign(self.subject.id, 1, 1)
        res = self._assign(self.subject.id, 1, 1)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])

    def test_same_subject_different_semester_is_allowed(self):
        self._assign(self.subject.id, 1, 1)
        res = self._assign(self.subject.id, 1, 2)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['ok'])

    def test_invalid_semester_rejected(self):
        res = self._assign(self.subject.id, 1, 9)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])

    def test_program_curriculum_list_json(self):
        self._assign(self.subject.id, 1, 1)
        self._assign(self.subject.id, 2, 2)
        res = self.client.get(reverse('program_curriculum_list', args=[self.program.id]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['years_total'], 4)
        self.assertEqual(len(data['semesters']), 3)
        self.assertEqual(len(data['entries']), 2)
        semesters = {e['semester'] for e in data['entries']}
        self.assertEqual(semesters, {1, 2})

    def test_remove_curriculum_entry(self):
        self._assign(self.subject.id, 1, 1)
        entry = Curriculum.objects.get(program=self.program)
        res = self.client.post(reverse('subject_curriculum_remove', args=[entry.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['ok'])
        self.assertFalse(Curriculum.objects.filter(pk=entry.id).exists())


# // ==============================================================================
# // A-08: ACADEMIC TERM ROLLOVER WIZARD
# // ==============================================================================
class TermRolloverTests(TestCase, BaseWeek4FixtureMixin):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()
        self.old_term = self._make_academic_year('2025-2026', is_active=True)
        self.admin_user, self.admin_profile = self._make_admin('rollover_admin')
        self.client.force_login(self.admin_user)

    def test_rollover_creates_new_active_and_deactivates_old(self):
        result = rollover_academic_year(
            actor=self.admin_user,
            name='2026-2027',
            starts_on='2026-06-01',
            ends_on='2027-03-31',
            promote=False,
        )
        self.old_term.refresh_from_db()
        self.assertFalse(self.old_term.is_active)
        self.assertTrue(result['instance'].is_active)
        self.assertEqual(result['instance'].name, '2026-2027')
        self.assertIn('2025-2026', result['previous_actives'])

    def test_rollover_audits_term_events(self):
        rollover_academic_year(
            actor=self.admin_user,
            name='2026-2027',
            starts_on='2026-06-01',
            ends_on='2027-03-31',
            promote=False,
        )
        self.assertTrue(AuditEvent.objects.filter(action='TERM_ROLLOVER').exists())
        self.assertTrue(AuditEvent.objects.filter(action='CREATE_ACADEMIC_YEAR').exists())

    def test_rollover_promotes_students_capped_at_program_duration(self):
        _, senior = self._make_student('rollover_senior', '2026-9001', year_level=4)
        _, junior = self._make_student('rollover_junior', '2026-9002', year_level=1)
        result = rollover_academic_year(
            actor=self.admin_user,
            name='2026-2027',
            starts_on='2026-06-01',
            ends_on='2027-03-31',
            promote=True,
        )
        senior.refresh_from_db()
        junior.refresh_from_db()
        self.assertEqual(senior.year_level, 4)   # capped at years_total
        self.assertEqual(junior.year_level, 2)   # promoted
        self.assertEqual(result['promoted_count'], 1)
        self.assertTrue(AuditEvent.objects.filter(action='PROMOTE_STUDENTS').exists())

    def test_rollover_skips_unapproved_students(self):
        self._make_student('rollover_pending', '2026-9003', approval_status=Profile.APPROVAL_PENDING)
        result = rollover_academic_year(
            actor=self.admin_user,
            name='2026-2027',
            starts_on='2026-06-01',
            ends_on='2027-03-31',
            promote=True,
        )
        self.assertEqual(result['promoted_count'], 0)

    def test_rollover_duplicate_name_rejected(self):
        with self.assertRaises(ValueError):
            rollover_academic_year(
                actor=self.admin_user,
                name='2025-2026',
                starts_on='2026-06-01',
                ends_on='2027-03-31',
                promote=False,
            )

    def test_rollover_endpoint(self):
        res = self.client.post(reverse('academic_year_rollover'), {
            'name': '2026-2027',
            'starts_on': '2026-06-01',
            'ends_on': '2027-03-31',
            'promote': '0',
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['academic_year']['name'], '2026-2027')
        self.old_term.refresh_from_db()
        self.assertFalse(self.old_term.is_active)

    def test_rollover_endpoint_bad_dates(self):
        res = self.client.post(reverse('academic_year_rollover'), {
            'name': '2026-2027',
            'starts_on': '2027-03-31',
            'ends_on': '2026-06-01',
            'promote': '0',
        })
        self.assertEqual(res.status_code, 400)


# // ==============================================================================
# // S-07: OFFLINE QR BADGE (SERVER-ISSUED SINGLE-USE)
# // ==============================================================================
class OfflineBadgeTests(TestCase, BaseWeek4FixtureMixin):
    def setUp(self):
        cache.clear()
        self.department = self._make_department()
        self.program = self._make_program()
        self.academic_year = self._make_academic_year()
        self.teacher_user, self.teacher_profile = self._make_teacher('badge_teacher')
        self.student_user, self.student_profile = self._make_student('badge_student', '2026-7101')

        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.class_obj = self._make_class(self.teacher_profile, self.subject)
        today = timezone.localdate()
        self.slot = self._make_slot(self.class_obj, today.weekday(), time(8, 0), time(9, 0))
        self.session = ClassSession.objects.create(
            slot=self.slot, session_date=today, status=ClassSession.STATUS_OPEN,
            opened_at=timezone.now(), opened_by=self.teacher_user, created_by=self.teacher_user,
        )
        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )

    def _issue(self):
        self.client.force_login(self.student_user)
        return self.client.post(reverse('student_offline_badge_issue'))

    def _scan(self, payload):
        self.client.force_login(self.teacher_user)
        return self.client.post(reverse('attendance_scan_api'), {
            'session_id': self.session.id,
            'qr_payload': payload,
        })

    def test_student_can_issue_offline_badge(self):
        res = self._issue()
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['payload'].startswith('classstamp:offline:2026-7101:'))
        token = data['payload'].rsplit(':', 1)[1]
        self.assertEqual(len(token), 64)
        badge = OfflineBadge.objects.get(student_profile=self.student_profile)
        self.assertIsNone(badge.consumed_at)
        self.assertNotEqual(badge.token_hash, token)  # raw token is never stored

    def test_issue_replaces_previous_unconsumed_badge(self):
        self._issue()
        self._issue()
        self.assertEqual(
            OfflineBadge.objects.filter(student_profile=self.student_profile).count(), 1
        )

    def test_offline_badge_redeems_and_stamps_attendance(self):
        payload = self._issue().json()['payload']
        res = self._scan(payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn(data['record_status'], [AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE])

        record = AttendanceRecord.objects.get(
            session=self.session, student_profile=self.student_profile
        )
        self.assertEqual(record.method, AttendanceRecord.METHOD_QR)
        badge = OfflineBadge.objects.get(student_profile=self.student_profile)
        self.assertIsNotNone(badge.consumed_at)
        self.assertEqual(badge.consumed_session, self.session)
        self.assertTrue(AuditEvent.objects.filter(action='REDEEM_OFFLINE_BADGE').exists())

    def test_offline_badge_is_single_use(self):
        payload = self._issue().json()['payload']
        self.assertEqual(self._scan(payload).status_code, 200)
        second = self._scan(payload)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()['outcome'], 'DUPLICATE')
        badge = OfflineBadge.objects.get(student_profile=self.student_profile)
        self.assertIsNotNone(badge.consumed_at)  # redeemed exactly once
        self.assertEqual(
            AttendanceRecord.objects.filter(session=self.session).count(), 1
        )

    def test_garbage_offline_token_rejected(self):
        payload = 'classstamp:offline:2026-7101:' + ('f' * 64)
        res = self._scan(payload)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(
            AttendanceRecord.objects.filter(session=self.session).exists()
        )

    def test_unknown_student_offline_rejected(self):
        payload = 'classstamp:offline:9999-9999:' + ('a' * 64)
        res = self._scan(payload)
        self.assertEqual(res.status_code, 404)

    def test_unenrolled_student_offline_rejected(self):
        other_student_user, other_student = self._make_student('badge_other', '2026-7102')
        self.client.force_login(other_student_user)
        payload = self.client.post(reverse('student_offline_badge_issue')).json()['payload']
        res = self._scan(payload)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['outcome'], 'INELIGIBLE')

    def test_issue_endpoint_requires_student_role(self):
        self.client.force_login(self.teacher_user)
        res = self.client.post(reverse('student_offline_badge_issue'))
        self.assertEqual(res.status_code, 302)


# // ==============================================================================
# // S-08: ONLINE EXCUSE SLIP WORKFLOW
# // ==============================================================================
class ExcuseSlipTests(TestCase, BaseWeek4FixtureMixin):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()
        self.academic_year = self._make_academic_year()
        self.teacher_user, self.teacher_profile = self._make_teacher('excuse_teacher')
        self.student_user, self.student_profile = self._make_student('excuse_student', '2026-7201')

        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.class_obj = self._make_class(self.teacher_profile, self.subject)
        self.slot = self._make_slot(self.class_obj, weekday=0, starts_at=time(8, 0), ends_at=time(9, 0))
        self.session = self._make_session(self.slot, timezone.localdate() - timedelta(days=1))
        Enrollment.objects.create(
            student_profile=self.student_profile,
            class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        self.record = AttendanceRecord.objects.create(
            session=self.session, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_ABSENT, method=AttendanceRecord.METHOD_SYSTEM,
            stamped_at=timezone.now(),
        )

    def _submit(self, session_id=None, reason='Medical appointment'):
        self.client.force_login(self.student_user)
        return self.client.post(reverse('student_excuse_slips'), {
            'session_id': session_id or self.session.id,
            'reason': reason,
        })

    def _review(self, slip, action, note=''):
        self.client.force_login(self.teacher_user)
        return self.client.post(reverse('excuse_slip_review_ajax', args=[slip.id]), {
            'action': action, 'note': note,
        })

    def test_student_can_file_excuse_slip(self):
        res = self._submit()
        self.assertEqual(res.status_code, 302)
        slip = ExcuseSlip.objects.get(session=self.session, student_profile=self.student_profile)
        self.assertEqual(slip.status, ExcuseSlip.STATUS_PENDING)
        self.assertEqual(slip.reason, 'Medical appointment')
        self.assertTrue(AuditEvent.objects.filter(action='EXCUSE_SUBMITTED').exists())

    def test_duplicate_slip_for_same_session_blocked(self):
        self._submit()
        self._submit()
        self.assertEqual(
            ExcuseSlip.objects.filter(
                session=self.session, student_profile=self.student_profile
            ).count(), 1
        )

    def test_cannot_file_for_non_absent_session(self):
        present_session = self._make_session(
            self.slot, timezone.localdate() - timedelta(days=2),
        )
        AttendanceRecord.objects.create(
            session=present_session, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_PRESENT, method=AttendanceRecord.METHOD_SYSTEM,
            stamped_at=timezone.now(),
        )
        res = self._submit(session_id=present_session.id)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(
            ExcuseSlip.objects.filter(session=present_session).exists()
        )

    def test_reason_required(self):
        res = self._submit(reason='')
        self.assertEqual(res.status_code, 302)
        self.assertFalse(ExcuseSlip.objects.exists())

    def test_teacher_approve_converts_absence_to_excused(self):
        self._submit()
        slip = ExcuseSlip.objects.get(session=self.session)
        res = self._review(slip, 'approve')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['ok'])

        slip.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(slip.status, ExcuseSlip.STATUS_APPROVED)
        self.assertEqual(slip.reviewed_by, self.teacher_user)
        self.assertIsNotNone(slip.reviewed_at)
        self.assertEqual(self.record.status, AttendanceRecord.STATUS_EXCUSED)
        self.assertEqual(self.record.method, AttendanceRecord.METHOD_MANUAL)
        self.assertTrue(self.record.correction_reason.startswith('Excuse slip approved'))
        self.assertTrue(AuditEvent.objects.filter(action='EXCUSE_APPROVED').exists())

    def test_reject_requires_note(self):
        self._submit()
        slip = ExcuseSlip.objects.get(session=self.session)
        res = self._review(slip, 'reject', note='')
        self.assertEqual(res.status_code, 400)
        slip.refresh_from_db()
        self.assertEqual(slip.status, ExcuseSlip.STATUS_PENDING)

    def test_reject_closes_slip_with_note(self):
        self._submit()
        slip = ExcuseSlip.objects.get(session=self.session)
        res = self._review(slip, 'reject', note='Certificate not valid')
        self.assertEqual(res.status_code, 200)
        slip.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(slip.status, ExcuseSlip.STATUS_REJECTED)
        self.assertEqual(slip.review_note, 'Certificate not valid')
        self.assertEqual(self.record.status, AttendanceRecord.STATUS_ABSENT)
        self.assertTrue(AuditEvent.objects.filter(action='EXCUSE_REJECTED').exists())

    def test_already_reviewed_slip_cannot_be_reviewed_again(self):
        self._submit()
        slip = ExcuseSlip.objects.get(session=self.session)
        self._review(slip, 'approve')
        res = self._review(slip, 'reject', note='nope')
        self.assertEqual(res.status_code, 400)

    def test_other_teacher_cannot_review(self):
        self._submit()
        slip = ExcuseSlip.objects.get(session=self.session)
        intruder_user, intruder = self._make_teacher('excuse_intruder')
        self.client.force_login(intruder_user)
        res = self.client.post(reverse('excuse_slip_review_ajax', args=[slip.id]), {
            'action': 'approve', 'note': '',
        })
        self.assertEqual(res.status_code, 403)
        slip.refresh_from_db()
        self.assertEqual(slip.status, ExcuseSlip.STATUS_PENDING)

    def test_review_page_lists_pending_for_teacher(self):
        self._submit()
        self.client.force_login(self.teacher_user)
        res = self.client.get(reverse('teacher_excuse_slips'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '2026-7201')
        self.assertEqual(len(res.context['pending_slips']), 1)
