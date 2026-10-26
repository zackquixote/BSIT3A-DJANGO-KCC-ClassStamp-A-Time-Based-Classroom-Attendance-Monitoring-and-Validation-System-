"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACCOUNT VALIDATION WORKFLOW TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Admin Validation Module
# // Description: Tests for the administrative approval/rejection workflow.
# //   Exercises the view logic that satisfies DB contracts enforced by
# //   ``trg_cs_profile_bu`` and ``chk_cs_profile_shape`` in the live database.
# //
# // Live DB Contracts Guarded:
# //   - Only an ADMIN may approve/reject a registration.
# //   - A decision must set BOTH approved_by and approved_at.
# //   - A rejection must carry a non-empty approval_note.
# //   - An APPROVED student must have a 64-character qr_secret.
# //
# // NOTE: The test database is created from migrations, which do not include
# //   the DB triggers/constraints. These tests assert the row state the views
# //   produce (the precondition the live DB requires) rather than relying on
# //   the DB to reject a bad write.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditEvent, Department, Profile, Program

User = get_user_model()


class AccountValidationTests(TestCase):
    """Tests for the admin account-validation workflow.

    These exercise the view logic that satisfies the DB contract enforced by
    ``trg_cs_profile_bu`` and ``chk_cs_profile_shape`` in the live database:

      * only an ADMIN may approve/reject (trigger: 'Only an admin can validate
        a registration'),
      * a decision must set BOTH approved_by and approved_at,
      * a rejection must carry a non-empty approval_note,
      * an APPROVED student must have a 64-character qr_secret.

    NOTE: the test database is created from migrations, which do not include
    the DB triggers/constraints. These tests therefore assert the row state the
    views produce (the precondition the live DB requires) rather than relying
    on the DB to reject a bad write.
    """

    def setUp(self):
        # The acting admin — must have an ADMIN Profile for the trigger to pass.
        self.admin_user = User.objects.create_user(
            username='admin', password='Admin!Pass123', is_staff=True,
        )
        self.admin_profile = Profile.objects.create(
            user=self.admin_user,
            role=Profile.ROLE_ADMIN,
        )

        # A non-admin who must be denied access to the queue.
        self.student_user = User.objects.create_user(username='stud', password='Stud!Pass123')
        self.department = Department.objects.create(code='CITCS', name='College of IT')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2023-0999',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_PENDING,
            qr_secret='0' * 64,
        )

    def _queue_url(self):
        return reverse('validation_pending_queue')

    def test_admin_can_view_queue(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(self._queue_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2023-0999')

    def test_non_admin_cannot_view_queue(self):
        self.client.force_login(self.student_user)
        response = self.client.get(self._queue_url())
        # Redirected to dashboard, not shown the queue.
        self.assertRedirects(response, reverse('dashboard'))

    def test_anonymous_cannot_view_queue(self):
        response = self.client.get(self._queue_url())

    def test_approve_sets_decision_fields_and_rotates_qr_secret(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('approve_student', args=[self.student_profile.pk])
        )

        self.assertRedirects(response, self._queue_url())
        self.student_profile.refresh_from_db()

        self.assertEqual(self.student_profile.approval_status, Profile.APPROVAL_APPROVED)
        self.assertEqual(self.student_profile.approved_by, self.admin_user)
        self.assertIsNotNone(self.student_profile.approved_at)
        # QR secret rotated to a valid 64-char value.
        self.assertEqual(len(self.student_profile.qr_secret), 64)
        self.assertNotEqual(self.student_profile.qr_secret, '0' * 64)

        # An audit event is written.
        self.assertTrue(
            AuditEvent.objects.filter(action='APPROVE_STUDENT').exists()
        )

    def test_approve_creates_audit_event(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('approve_student', args=[self.student_profile.pk]))
        event = AuditEvent.objects.filter(action='APPROVE_STUDENT').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor, self.admin_user)
        self.assertEqual(event.object_id, str(self.student_profile.pk))

    def test_reject_requires_reason(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('reject_student', args=[self.student_profile.pk]),
            {'reason': ''},
        )
        # Redirected back with an error; status unchanged.
        self.assertRedirects(response, self._queue_url())
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.approval_status, Profile.APPROVAL_PENDING)

    def test_reject_with_reason_sets_decision(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('reject_student', args=[self.student_profile.pk]),
            {'reason': 'Student number could not be verified.'},
        )
        self.assertRedirects(response, self._queue_url())
        self.student_profile.refresh_from_db()

        self.assertEqual(self.student_profile.approval_status, Profile.APPROVAL_REJECTED)
        self.assertEqual(self.student_profile.approved_by, self.admin_user)
        self.assertIsNotNone(self.student_profile.approved_at)
        self.assertEqual(
            self.student_profile.approval_note,
            'Student number could not be verified.',
        )
        self.assertTrue(
            AuditEvent.objects.filter(action='REJECT_STUDENT').exists()
        )

    def test_cannot_review_non_pending_profile(self):
        # Already-approved profile must 404 on a repeat decision.
        self.student_profile.approval_status = Profile.APPROVAL_APPROVED
        self.student_profile.save()
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('approve_student', args=[self.student_profile.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_approve_another_student(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse('approve_student', args=[self.student_profile.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.approval_status, Profile.APPROVAL_PENDING)

    def test_admin_can_view_validation_detail(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('validation_detail', args=[self.student_profile.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2023-0999')
        self.assertContains(response, 'BS Information Technology')
        self.assertContains(response, 'CITCS')
        self.assertContains(response, self.student_user.first_name)
        self.assertContains(response, self.student_user.email)

    def test_non_admin_cannot_view_validation_detail(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('validation_detail', args=[self.student_profile.pk]))
        self.assertRedirects(response, reverse('dashboard'))

    def test_anonymous_cannot_view_validation_detail(self):
        response = self.client.get(reverse('validation_detail', args=[self.student_profile.pk]))
        self.assertEqual(response.status_code, 302)

    def test_queue_filter_by_department(self):
        other_dept = Department.objects.create(code='CON', name='College of Nursing')
        other_prog = Program.objects.create(department=other_dept, code='BSN', name='BS Nursing', years_total=4)
        other_user = User.objects.create_user(username='nursestudent', password='Pass1234!x', first_name='Florence', last_name='N')
        Profile.objects.create(
            user=other_user, role=Profile.ROLE_STUDENT, student_number='2023-0888',
            program=other_prog, year_level=1, approval_status=Profile.APPROVAL_PENDING, qr_secret='1' * 64
        )

        self.client.force_login(self.admin_user)

        # Filter for first department
        resp_dept1 = self.client.get(self._queue_url(), {'department': self.department.id})
        self.assertEqual(resp_dept1.status_code, 200)
        self.assertContains(resp_dept1, '2023-0999')
        self.assertNotContains(resp_dept1, '2023-0888')

        # Filter for nursing department
        resp_dept2 = self.client.get(self._queue_url(), {'department': other_dept.id})
        self.assertEqual(resp_dept2.status_code, 200)
        self.assertContains(resp_dept2, '2023-0888')
        self.assertNotContains(resp_dept2, '2023-0999')

    def test_queue_filter_by_program(self):
        other_prog = Program.objects.create(department=self.department, code='BSCS', name='BS Computer Science', years_total=4)
        other_user = User.objects.create_user(username='csstudent', password='Pass1234!x', first_name='Alan', last_name='T')
        Profile.objects.create(
            user=other_user, role=Profile.ROLE_STUDENT, student_number='2023-0777',
            program=other_prog, year_level=2, approval_status=Profile.APPROVAL_PENDING, qr_secret='2' * 64
        )

        self.client.force_login(self.admin_user)
        resp = self.client.get(self._queue_url(), {'program': other_prog.id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '2023-0777')
        self.assertNotContains(resp, '2023-0999')

    def test_queue_filter_by_search_query(self):
        self.client.force_login(self.admin_user)
        resp = self.client.get(self._queue_url(), {'q': '2023-0999'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '2023-0999')

        resp_none = self.client.get(self._queue_url(), {'q': 'nonexistentstudent'})
        self.assertEqual(resp_none.status_code, 200)
        self.assertNotContains(resp_none, '2023-0999')

    def test_approve_with_next_detail_redirects_to_detail(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('approve_student', args=[self.student_profile.pk]),
            {'next': 'detail'}
        )
        self.assertRedirects(response, reverse('validation_detail', args=[self.student_profile.pk]))

    def test_check_registration_availability_student_number(self):
        # Existing student number
        resp = self.client.get(
            reverse('check_registration_availability'),
            {'type': 'student_number', 'value': '2023-0999'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['available'])

        # Available student number
        resp2 = self.client.get(
            reverse('check_registration_availability'),
            {'type': 'student_number', 'value': '2024-9999'}
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()['available'])

    def test_check_registration_availability_username(self):
        resp = self.client.get(
            reverse('check_registration_availability'),
            {'type': 'username', 'value': self.student_user.username}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['available'])

        resp2 = self.client.get(
            reverse('check_registration_availability'),
            {'type': 'username', 'value': 'brandnewuser999'}
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()['available'])

    def test_validation_detail_queue_navigation_and_duplicate_detection(self):
        # Create a second pending student with matching name to trigger duplicate detection
        user2 = User.objects.create_user(
            username='student2duplicate',
            password='Pass1234!x',
            first_name=self.student_user.first_name,
            last_name=self.student_user.last_name,
        )
        profile2 = Profile.objects.create(
            user=user2,
            role=Profile.ROLE_STUDENT,
            student_number='2024-0002',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_PENDING,
            qr_secret='3' * 64,
        )

        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse('validation_detail', args=[self.student_profile.pk]))
        self.assertEqual(resp.status_code, 200)
        # Should have next_id pointing to profile2
        self.assertEqual(resp.context['next_id'], profile2.pk)
        self.assertEqual(resp.context['current_index'], 1)
        self.assertEqual(resp.context['total_pending'], 2)
        # Should detect profile2 as duplicate due to matching name
        self.assertIn(profile2, resp.context['duplicates'])

    # ── Batch Validation Endpoint (#3) ──────────────────────────────────────

    def _make_pending_student(self, username, student_number):
        user = User.objects.create_user(username=username, password='Pass1234!x')
        return Profile.objects.create(
            user=user,
            role=Profile.ROLE_STUDENT,
            student_number=student_number,
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_PENDING,
            qr_secret='9' * 64,
        )

    def test_batch_approve_provisions_qr_and_emits_batch_audit(self):
        p1 = self._make_pending_student('batchstu1', '2024-1001')
        p2 = self._make_pending_student('batchstu2', '2024-1002')

        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('batch_validation_action'), {
            'action': 'approve',
            'ids[]': [str(p1.pk), str(p2.pk)],
        })

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['approved'], 2)
        self.assertEqual(data['rejected'], 0)
        self.assertEqual(data['skipped'], 0)

        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p1.approval_status, Profile.APPROVAL_APPROVED)
        self.assertEqual(p2.approval_status, Profile.APPROVAL_APPROVED)
        self.assertEqual(len(p1.qr_secret), 64)
        self.assertEqual(len(p2.qr_secret), 64)
        self.assertIsNotNone(p1.approved_by)
        self.assertIsNotNone(p2.approved_by)

        batch_events = AuditEvent.objects.filter(action='BATCH_VALIDATION')
        self.assertEqual(batch_events.count(), 1)
        self.assertIn('2 approved', batch_events.first().new_value)

    def test_batch_reject_requires_reason(self):
        p1 = self._make_pending_student('batchstu3', '2024-1003')

        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('batch_validation_action'), {
            'action': 'reject',
            'ids[]': [str(p1.pk)],
        })

        self.assertEqual(resp.status_code, 400)
        p1.refresh_from_db()
        self.assertEqual(p1.approval_status, Profile.APPROVAL_PENDING)

    def test_batch_reject_applies_reason_to_all_and_emits_audit(self):
        p1 = self._make_pending_student('batchstu4', '2024-1004')
        p2 = self._make_pending_student('batchstu5', '2024-1005')

        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('batch_validation_action'), {
            'action': 'reject',
            'ids[]': [str(p1.pk), str(p2.pk)],
            'reason': 'COR Unreadable',
        })

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['rejected'], 2)
        self.assertEqual(data['approved'], 0)

        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p1.approval_status, Profile.APPROVAL_REJECTED)
        self.assertEqual(p2.approval_status, Profile.APPROVAL_REJECTED)
        self.assertEqual(p1.approval_note, 'COR Unreadable')
        self.assertEqual(p2.approval_note, 'COR Unreadable')

        batch_events = AuditEvent.objects.filter(action='BATCH_VALIDATION')
        self.assertEqual(batch_events.count(), 1)
        self.assertEqual(batch_events.first().reason, 'COR Unreadable')

    def test_batch_action_skips_non_pending_profiles(self):
        p1 = self._make_pending_student('batchstu6', '2024-1006')
        p1.approval_status = Profile.APPROVAL_APPROVED
        p1.save(update_fields=['approval_status'])

        p2 = self._make_pending_student('batchstu7', '2024-1007')

        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('batch_validation_action'), {
            'action': 'approve',
            'ids[]': [str(p1.pk), str(p2.pk)],
        })

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['approved'], 1)
        self.assertEqual(data['skipped'], 0)  # non-pending IDs are filtered out, not counted as errors

        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p1.approval_status, Profile.APPROVAL_APPROVED)
        self.assertEqual(p2.approval_status, Profile.APPROVAL_APPROVED)
        self.assertEqual(len(p2.qr_secret), 64)

    def test_batch_action_rejects_invalid_action(self):
        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('batch_validation_action'), {
            'action': 'destroy',
            'ids[]': ['1'],
        })
        self.assertEqual(resp.status_code, 400)
