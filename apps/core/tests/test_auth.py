"""
# // ==============================================================================
# // KCC CLASSSTAMP - AUTHENTICATION VIEW TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Auth Module
# // Description: Regression tests for student self-registration (POST /register/)
# //   and the login/logout flow for all three roles (admin, teacher, student).
# //
# // Live DB Constraints Guarded:
# //   - chk_cs_profile_shape: student profile must have NULL department_id and
# //     a 64-char qr_secret at INSERT time.
# //   - trg_cs_profile_bi: year_level must not exceed program.years_total.
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Department, Profile, Program

import io

from PIL import Image

User = get_user_model()


def _proof_upload(filename='cor.png', width=32, height=32):
    """A real PNG (magic bytes + Pillow-decodable) for the required COR upload."""
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), (20, 120, 220)).save(buffer, format='PNG')
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type='image/png')


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
            'gender': 'M',
            'phone_number': '09171234567',
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

    def _post(self, **overrides):
        """POST the payload with the now-mandatory COR/ID proof attached.

        The test client takes uploads inside the data dict (a file object is
        detected by its ``read`` attribute); it has no ``files=`` kwarg.
        """
        payload = self._valid_payload(**overrides)
        payload['registration_proof'] = _proof_upload()
        return self.client.post(reverse('register'), payload)

    def test_successful_registration_creates_pending_student_profile(self):
        response = self._post()

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
        self._post()

        profile = Profile.objects.get(user__username='jdelacruz')

        # department_id must be NULL for a STUDENT row.
        self.assertIsNone(profile.department_id)
        # qr_secret must be present and exactly 64 characters.
        self.assertIsNotNone(profile.qr_secret)
        self.assertEqual(len(profile.qr_secret), 64)
        self.assertRegex(profile.qr_secret, r'^[0-9a-f]{64}$')

    def test_registration_rejects_year_level_beyond_program_length(self):
        """A 4-year program must reject year level 5 (trigger trg_cs_profile_bi)."""
        response = self._post(year_level='5')

        # Form is re-rendered with an error; nothing is created.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Profile.objects.count(), 0)

    def test_registration_rejects_duplicate_student_number(self):
        self._post()
        response = self._post(username='another', email='another@example.com')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.count(), 1)

    def test_registration_rejects_password_mismatch(self):
        response = self._post(confirm_password='NotTheSamePass1!')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)

    def test_registration_rejects_password_without_symbol(self):
        """Rule 4 of the live checklist: at least 1 symbol / special character.
        The server must reject exactly what the checklist shows as still gray."""
        response = self._post(password='Juan2026', confirm_password='Juan2026')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, 'at least 1 symbol or special character')

    def test_registration_accepts_four_rule_password(self):
        """8+ chars, mixed case, a digit and a symbol — all four rules green."""
        response = self._post(password='Juan2026!', confirm_password='Juan2026!')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_is_not_stricter_than_the_visible_checklist(self):
        """Registration only enforces the four rules shown on the form.

        Django's similarity / common-password validators are bypassed here on
        purpose: a student must never be rejected for a rule the checklist did
        not display. The reset / change-password flows still apply them.
        """
        response = self._post(
            username='jdelacruz',
            password='Jdelacruz1!',
            confirm_password='Jdelacruz1!',
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_without_cor_or_id_proof_is_rejected(self):
        """The COR / school-ID proof is mandatory: the admin validates every
        student against it, so no account may be created without one."""
        response = self.client.post(reverse('register'), self._valid_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Profile.objects.count(), 0)
        self.assertContains(response, 'Certificate of Registration (COR) or school ID photo')


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

    # // [Multi-Identifier Sign-In] The form says "Student ID or email", so both
    # // must reach the same account, and the username path must keep working.
    TEST_PASSWORD = 'MultiId!2026'

    def _pin_known_password(self, user):
        """Set a password this test knows, so the identifier is the only variable."""
        user.set_password(self.TEST_PASSWORD)
        user.save(update_fields=['password'])

    def test_login_with_student_id_number(self):
        """Student ID: the username is 'studx', the ID on the profile is different."""
        self._pin_known_password(self.student_user)

        response = self.client.post(reverse('login'), {
            'username': '2023-1234', 'password': self.TEST_PASSWORD,
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.student_user.pk)

    def test_login_with_email(self):
        self.student_user.email = 'studx@example.com'
        self.student_user.save(update_fields=['email'])
        self._pin_known_password(self.student_user)

        response = self.client.post(reverse('login'), {
            'username': 'studx@example.com', 'password': self.TEST_PASSWORD,
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.student_user.pk)

    def test_login_with_email_is_case_insensitive(self):
        self.student_user.email = 'studx@example.com'
        self.student_user.save(update_fields=['email'])
        self._pin_known_password(self.student_user)

        response = self.client.post(reverse('login'), {
            'username': 'STUDX@EXAMPLE.COM', 'password': self.TEST_PASSWORD,
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_with_username_still_works(self):
        self._pin_known_password(self.student_user)

        response = self.client.post(reverse('login'), {
            'username': 'studx', 'password': self.TEST_PASSWORD,
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_with_faculty_id_number(self):
        """Faculty sign in with their Faculty ID, same as students with Student ID."""
        teacher_profile = self.teacher_user.classstamp_profile
        teacher_profile.employee_number = 'FAC-0912'
        teacher_profile.save(update_fields=['employee_number'])
        self._pin_known_password(self.teacher_user)

        response = self.client.post(reverse('login'), {
            'username': 'fac-0912', 'password': self.TEST_PASSWORD,
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.teacher_user.pk)

    def test_unknown_identifier_does_not_authenticate(self):
        self._pin_known_password(self.student_user)

        response = self.client.post(reverse('login'), {
            'username': '2099-0000', 'password': self.TEST_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
