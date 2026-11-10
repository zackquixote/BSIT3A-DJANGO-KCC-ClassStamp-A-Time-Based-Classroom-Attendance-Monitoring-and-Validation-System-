"""
# // ==============================================================================
# // KCC CLASSSTAMP - BULK EXCUSE APPROVAL TESTS (tasks 4.5 / 4.6)
# // ==============================================================================
# // The single-slip endpoint and the bulk endpoint share one service operation.
# // Bulk processes slips independently: one failure never blocks the rest.
# // Permission is re-checked per slip (never inferred from a selected ID).
# // ==============================================================================
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
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
    Department,
    Enrollment,
    ExcuseSlip,
    Notification,
    Profile,
    Program,
    Subject,
)
from apps.core.services.excuse_service import review_excuse_slip

User = get_user_model()


class BulkExcuseApprovalTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='Information Technology',
        )
        self.subject = Subject.objects.create(code='IT311', name='Web Development')
        self.year = AcademicYear.objects.create(
            name='2026-2027', starts_on=date(2026, 6, 1), ends_on=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='bulk_teacher')
        self.teacher = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.other_teacher_user = User.objects.create_user(username='bulk_other_teacher')
        self.other_teacher = Profile.objects.create(
            user=self.other_teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.admin_user = User.objects.create_user(username='bulk_admin')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3A-IT311', subject=self.subject,
            teacher_profile=self.teacher, program=self.program, year_level=3,
        )
        self.other_class = Class.objects.create(
            academic_year=self.year, class_code='BSIT-3B-IT311', subject=self.subject,
            teacher_profile=self.other_teacher, program=self.program, year_level=3,
        )
        self.slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.other_slot = ClassSlot.objects.create(
            class_obj=self.other_class, weekday=0,
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 2',
        )

        self.students = []
        for i, number in enumerate(('2026-4001', '2026-4002', '2026-4003')):
            user = User.objects.create_user(username=f'bulk_student_{i}')
            profile = Profile.objects.create(
                user=user, role=Profile.ROLE_STUDENT, student_number=number,
                program=self.program, year_level=3,
                approval_status=Profile.APPROVAL_APPROVED,
            )
            Enrollment.objects.create(
                student_profile=profile, class_obj=self.class_obj,
                status=Enrollment.STATUS_ACTIVE,
            )
            self.students.append(profile)

        self.client.force_login(self.teacher_user)

    def _session(self, class_obj, slot, days_from_today):
        return ClassSession.objects.create(
            slot=slot,
            session_date=timezone.localdate() + timedelta(days=days_from_today),
            status=ClassSession.STATUS_CLOSED,
            created_by=self.teacher_user,
        )

    def _slip(self, student, session):
        return ExcuseSlip.objects.create(
            student_profile=student, session=session, reason='Medical appointment',
            status=ExcuseSlip.STATUS_PENDING,
        )

    def test_bulk_approves_pending_owned_slips(self):
        sessions = [
            self._session(self.class_obj, self.slot, 1),
            self._session(self.class_obj, self.slot, 2),
            self._session(self.class_obj, self.slot, 3),
        ]
        slips = [
            self._slip(student, session)
            for student, session in zip(self.students, sessions)
        ]

        response = self.client.post(reverse('teacher_excuse_bulk_approve'), {
            'slip_ids': [s.pk for s in slips],
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['approved'], 3)
        self.assertEqual(data['failed'], 0)

        for slip in slips:
            slip.refresh_from_db()
            self.assertEqual(slip.status, ExcuseSlip.STATUS_APPROVED)
            self.assertEqual(slip.reviewed_by, self.teacher_user)
            record = AttendanceRecord.objects.get(
                session=slip.session, student_profile=slip.student_profile,
            )
            self.assertEqual(record.status, AttendanceRecord.STATUS_EXCUSED)
            self.assertTrue(
                Notification.objects.filter(
                    user=slip.student_profile.user, category='excuse_slip',
                ).exists()
            )
            self.assertTrue(
                AuditEvent.objects.filter(
                    action='EXCUSE_APPROVED', object_id=str(slip.pk),
                ).exists()
            )

        self.assertTrue(
            AuditEvent.objects.filter(
                action='EXCUSE_BULK_APPROVED',
                actor=self.teacher_user,
                new_value__contains='approved=3',
            ).exists()
        )

    def test_mixed_ownership_and_already_reviewed_fail_independently(self):
        own_pending = self._slip(
            self.students[0], self._session(self.class_obj, self.slot, 1),
        )
        foreign = self._slip(
            self.students[1],
            self._session(self.other_class, self.other_slot, 2),
        )
        already = self._slip(
            self.students[2], self._session(self.class_obj, self.slot, 3),
        )
        already.status = ExcuseSlip.STATUS_APPROVED
        already.reviewed_by = self.teacher_user
        already.reviewed_at = timezone.now()
        already.save()

        response = self.client.post(reverse('teacher_excuse_bulk_approve'), {
            'slip_ids': [own_pending.pk, foreign.pk, already.pk],
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['approved'], 1)
        self.assertEqual(data['failed'], 2)

        own_pending.refresh_from_db()
        self.assertEqual(own_pending.status, ExcuseSlip.STATUS_APPROVED)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, ExcuseSlip.STATUS_PENDING)
        already.refresh_from_db()
        self.assertEqual(already.status, ExcuseSlip.STATUS_APPROVED)

        by_id = {item['slip_id']: item for item in data['results']}
        self.assertEqual(by_id[foreign.pk]['error'], 'not_authorized')
        self.assertEqual(by_id[already.pk]['error'], 'already_reviewed')

    def test_missing_slip_does_not_block_the_rest(self):
        good = self._slip(self.students[0], self._session(self.class_obj, self.slot, 1))

        response = self.client.post(reverse('teacher_excuse_bulk_approve'), {
            'slip_ids': [999999, good.pk],
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['approved'], 1)
        self.assertEqual(data['failed'], 1)
        good.refresh_from_db()
        self.assertEqual(good.status, ExcuseSlip.STATUS_APPROVED)

    def test_empty_selection_is_400(self):
        response = self.client.post(reverse('teacher_excuse_bulk_approve'), {})
        self.assertEqual(response.status_code, 400)

    def test_get_is_rejected(self):
        response = self.client.get(reverse('teacher_excuse_bulk_approve'))
        self.assertEqual(response.status_code, 405)

    def test_student_cannot_bulk_approve(self):
        student_user = self.students[0].user
        self.client.force_login(student_user)
        slip = self._slip(self.students[0], self._session(self.class_obj, self.slot, 1))
        response = self.client.post(reverse('teacher_excuse_bulk_approve'), {
            'slip_ids': [slip.pk],
        })
        # The /teacher/ prefix is blocked by RBAC middleware with 403.
        self.assertEqual(response.status_code, 403)
        slip.refresh_from_db()
        self.assertEqual(slip.status, ExcuseSlip.STATUS_PENDING)

    def test_shared_service_rejects_invalid_action(self):
        slip = self._slip(self.students[0], self._session(self.class_obj, self.slot, 1))
        result = review_excuse_slip(
            actor=self.teacher_user, slip=slip, action='explode', note='',
        )
        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], 'invalid_action')

    def test_shared_service_reject_requires_note(self):
        slip = self._slip(self.students[0], self._session(self.class_obj, self.slot, 1))
        result = review_excuse_slip(
            actor=self.teacher_user, slip=slip, action='reject', note='',
        )
        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], 'note_required')
        slip.refresh_from_db()
        self.assertEqual(slip.status, ExcuseSlip.STATUS_PENDING)
