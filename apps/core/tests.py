from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AuditEvent, Department, Profile, Program

User = get_user_model()


class HomeViewTests(TestCase):
    def test_home_renders_for_authenticated_user(self):
        user = User.objects.create_user(username='admin', password='secret1234')

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)


class RegistrationViewTests(TestCase):
    """Regression tests for POST /register/.

    The live MySQL database enforces a CHECK constraint ``chk_cs_profile_shape``
    on ``tblcs_profile`` that is NOT captured in migrations (so it does not exist
    in the test database). These tests therefore assert the exact row *shape*
    the view produces, guarding against regressions that would raise
    ``IntegrityError`` (4025) against the real database:

      * a STUDENT profile must NOT carry a department_id,
      * a STUDENT profile must carry a 64-character qr_secret at insert time,
      * year_level must respect the selected program's length (BEFORE INSERT
        trigger ``trg_cs_profile_bi`` rejects a year beyond ``years_total``).
    """

    def setUp(self):
        self.department = Department.objects.create(
            code='CITCS',
            name='College of Information Technology and Computer Studies',
        )
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name='BS Information Technology',
            years_total=4,
        )

    def _valid_payload(self, **overrides):
        payload = {
            'username': 'jdelacruz',
            'first_name': 'Juan',
            'last_name': 'Dela Cruz',
            'email': 'juan@example.com',
            'password': 'S3cure!Passphrase',
            'confirm_password': 'S3cure!Passphrase',
            'student_number': '2023-0145',
            'department_id': str(self.department.id),
            'program_id': str(self.program.id),
            'year_level': '1',
        }
        payload.update(overrides)
        return payload

    def test_successful_registration_creates_pending_student_profile(self):
        response = self.client.post(reverse('register'), self._valid_payload())

        # Redirects to login on success.
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

        # A user and a profile are created.
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get(username='jdelacruz')
        profile = user.classstamp_profile

        self.assertEqual(profile.role, Profile.ROLE_STUDENT)
        self.assertEqual(profile.approval_status, Profile.APPROVAL_PENDING)
        self.assertEqual(profile.program, self.program)
        self.assertEqual(profile.year_level, 1)
        self.assertEqual(profile.student_number, '2023-0145')

    def test_student_profile_shape_satisfies_check_constraint(self):
        """The created profile must satisfy chk_cs_profile_shape."""
        self.client.post(reverse('register'), self._valid_payload())

        profile = Profile.objects.get(user__username='jdelacruz')

        # department_id must be NULL for a STUDENT row.
        self.assertIsNone(profile.department_id)
        # qr_secret must be present and exactly 64 characters.
        self.assertIsNotNone(profile.qr_secret)
        self.assertEqual(len(profile.qr_secret), 64)
        self.assertRegex(profile.qr_secret, r'^[0-9a-f]{64}$')

    def test_registration_rejects_year_level_beyond_program_length(self):
        """A 4-year program must reject year level 5 (trigger trg_cs_profile_bi)."""
        response = self.client.post(
            reverse('register'),
            self._valid_payload(year_level='5'),
        )

        # Form is re-rendered with an error; nothing is created.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Profile.objects.count(), 0)

    def test_registration_rejects_duplicate_student_number(self):
        self.client.post(reverse('register'), self._valid_payload())
        response = self.client.post(
            reverse('register'),
            self._valid_payload(username='another', email='another@example.com'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.count(), 1)

    def test_registration_rejects_password_mismatch(self):
        response = self.client.post(
            reverse('register'),
            self._valid_payload(confirm_password='Different!Pass123'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)



class LoginFlowTests(TestCase):
    """End-to-end auth: log in via the login view, land on the role dashboard.

    Verifies the full chain you asked for:
      * every dashboard requires authentication (login_required),
      * after login each role is redirected to /home/ which renders that
        role's own dashboard template,
      * pending/rejected non-admin accounts cannot pass the login gate.
    """

    def setUp(self):
        self.department = Department.objects.create(code='CITCS', name='College of IT')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )

        self.admin_user = User.objects.create_user(username='adminx', password='Pass!2345')
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.teacher_user = User.objects.create_user(username='teachx', password='Pass!2345')
        Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER,
            department=self.department, approval_status=None,
        )

        self.student_user = User.objects.create_user(username='studx', password='Pass!2345')
        self.student_profile = Profile.objects.create(
            user=self.student_user, role=Profile.ROLE_STUDENT,
            student_number='2023-1234', program=self.program, year_level=2,
            approval_status=Profile.APPROVAL_APPROVED, qr_secret='a' * 64,
        )

        self.pending_user = User.objects.create_user(username='pendx', password='Pass!2345')
        Profile.objects.create(
            user=self.pending_user, role=Profile.ROLE_STUDENT,
            student_number='2023-5678', program=self.program, year_level=1,
            approval_status=Profile.APPROVAL_PENDING, qr_secret='b' * 64,
        )

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        # Redirects to the login view (mounted at site root '/', name 'login').
        self.assertEqual(response.url, reverse('login') + '?next=' + reverse('dashboard'))

    def test_admin_login_redirects_to_admin_dashboard(self):
        logged_in = self.client.login(username='adminx', password='Pass!2345')
        self.assertTrue(logged_in)
        response = self.client.post(reverse('login'), {
            'username': 'adminx', 'password': 'Pass!2345',
        })
        # Already authenticated -> login view redirects to the dashboard.
        self.assertRedirects(response, reverse('dashboard'))

        dash = self.client.get(reverse('dashboard'))
        self.assertTemplateUsed(dash, 'core/admin/dashboard.html')

    def test_teacher_login_lands_on_teacher_dashboard(self):
        self.client.login(username='teachx', password='Pass!2345')
        dash = self.client.get(reverse('dashboard'))
        self.assertTemplateUsed(dash, 'core/teacher/dashboard.html')

    def test_student_login_lands_on_student_dashboard(self):
        self.client.login(username='studx', password='Pass!2345')
        dash = self.client.get(reverse('dashboard'))
        self.assertTemplateUsed(dash, 'core/student/dashboard.html')

    def test_pending_student_cannot_reach_dashboard_via_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'pendx', 'password': 'Pass!2345',
        })
        # Re-renders login (status 200), never authenticated/redirected to dashboard.
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/login.html')

    def test_wrong_password_does_not_authenticate(self):
        response = self.client.post(reverse('login'), {
            'username': 'adminx', 'password': 'totally-wrong',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)



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
        return reverse('validation_queue')

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


class DashboardDispatchTests(TestCase):
    """After login, ``/home/`` must render the dashboard matching the role."""

    def setUp(self):
        self.department = Department.objects.create(code='CITCS', name='College of IT')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )

    def _make(self, username, role, **profile_kwargs):
        user = User.objects.create_user(username=username, password='Pass1234!x')
        Profile.objects.create(user=user, role=role, **profile_kwargs)
        return user

    def test_admin_lands_on_admin_dashboard(self):
        user = self._make('boss', Profile.ROLE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/admin/dashboard.html')

    def test_teacher_lands_on_teacher_dashboard(self):
        user = self._make('teach', Profile.ROLE_TEACHER, department=self.department)
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/teacher/dashboard.html')

    def test_student_lands_on_student_dashboard(self):
        user = self._make(
            'stud', Profile.ROLE_STUDENT,
            program=self.program, year_level=1, student_number='2023-7000',
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/student/dashboard.html')

    def test_superuser_without_profile_gets_admin_dashboard(self):
        user = User.objects.create_superuser(
            username='rooty', password='Pass1234!x', email='r@x.com',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/admin/dashboard.html')

    def test_plain_user_without_profile_gets_fallback_home(self):
        user = User.objects.create_user(username='nobody', password='Pass1234!x')
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)


class DepartmentProgramCrudTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username='admin_boss', password='Boss!Password1')
        self.admin_profile = Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)

        self.student_user = User.objects.create_user(username='student_kid', password='Kid!Password1')
        self.student_profile = Profile.objects.create(user=self.student_kid if hasattr(self, 'student_kid') else self.student_user, role=Profile.ROLE_STUDENT)

        self.dept = Department.objects.create(code='CITCS', name='College of Information Tech')
        self.prog = Program.objects.create(department=self.dept, code='BSIT', name='BS in Info Tech', years_total=4)

    def test_admin_can_view_department_and_program_lists(self):
        self.client.force_login(self.admin_user)
        r_dept = self.client.get(reverse('department_list'))
        self.assertEqual(r_dept.status_code, 200)
        self.assertTemplateUsed(r_dept, 'core/admin/departments.html')

        r_prog = self.client.get(reverse('program_list'))
        self.assertEqual(r_prog.status_code, 200)
        self.assertTemplateUsed(r_prog, 'core/admin/programs.html')

    def test_student_cannot_access_department_list(self):
        self.client.force_login(self.student_user)
        r = self.client.get(reverse('department_list'))
        self.assertEqual(r.status_code, 302)

    def test_admin_can_create_and_edit_department(self):
        self.client.force_login(self.admin_user)
        # Create
        res = self.client.post(reverse('department_save'), {
            'code': 'CAS',
            'name': 'College of Arts and Sciences',
            'is_active': 'true',
        })
        self.assertEqual(res.status_code, 302)
        cas = Department.objects.get(code='CAS')
        self.assertEqual(cas.name, 'College of Arts and Sciences')

        # Edit
        res_edit = self.client.post(reverse('department_save'), {
            'id': cas.id,
            'code': 'CAS',
            'name': 'College of Arts, Letters and Sciences',
            'is_active': 'true',
        })
        self.assertEqual(res_edit.status_code, 302)
        cas.refresh_from_db()
        self.assertEqual(cas.name, 'College of Arts, Letters and Sciences')

    def test_admin_can_create_and_edit_program(self):
        self.client.force_login(self.admin_user)
        # Create
        res = self.client.post(reverse('program_save'), {
            'department_id': self.dept.id,
            'code': 'BSCS',
            'name': 'Bachelor of Science in Computer Science',
            'years_total': 4,
            'is_active': 'true',
        })
        self.assertEqual(res.status_code, 302)
        bscs = Program.objects.get(code='BSCS')
        self.assertEqual(bscs.department, self.dept)
        self.assertEqual(bscs.years_total, 4)

        # Edit
        res_edit = self.client.post(reverse('program_save'), {
            'id': bscs.id,
            'department_id': self.dept.id,
            'code': 'BSCS',
            'name': 'BS in Computer Science (Enhanced)',
            'years_total': 4,
            'is_active': 'true',
        })
        self.assertEqual(res_edit.status_code, 302)
        bscs.refresh_from_db()
        self.assertEqual(bscs.name, 'BS in Computer Science (Enhanced)')

    def test_protected_department_deactivates_when_children_exist(self):
        self.client.force_login(self.admin_user)
        # self.dept has self.prog attached
        res = self.client.post(reverse('department_delete', args=[self.dept.id]))
        self.assertEqual(res.status_code, 302)
        self.dept.refresh_from_db()
        self.assertFalse(self.dept.is_active)
        self.assertTrue(Department.objects.filter(pk=self.dept.id).exists())


