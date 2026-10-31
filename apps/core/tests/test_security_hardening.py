"""
# // ==============================================================================
# // KCC CLASSSTAMP - SECURITY HARDENING TESTS (SPRINT 1)
# // ==============================================================================
# // Covers:
# //   - 1.1 Credential lifecycle: QR rotation, qr_rotated_at, offline-badge
# //     revocation, audit trail, and non-student rejection.
# //   - 1.2 Protected document delivery: owner/admin/assigned-teacher access to
# //     registration proofs and excuse-slip attachments.
# //   - 1.3 Upload validation: size, extension, PDF signature, and image decode
# //     checks at the validator, form, service, and view boundaries.
# // ==============================================================================
"""

import hashlib
import io
import re
import shutil
import tempfile
from datetime import time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from apps.core.forms.registration_form import RegistrationForm
from apps.core.models import (
    AttendanceRecord,
    AuditEvent,
    ExcuseSlip,
    OfflineBadge,
)
from apps.core.services.credential_service import rotate_student_credentials
from apps.core.tests.test_week5 import BaseWeek5FixtureMixin
from apps.core.validators import validate_uploaded_document
from apps.core.views.validation_views import _redirect_after_validation

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is pinned in requirements.txt
    Image = None

User = get_user_model()


def _png_bytes(width=32, height=32, color=(20, 120, 220)):
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buffer, format='PNG')
    return buffer.getvalue()


# // ==============================================================================
# // 1.1 CREDENTIAL LIFECYCLE
# // ==============================================================================
class CredentialLifecycleTests(BaseWeek5FixtureMixin, TestCase):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()
        self.academic_year = self._make_academic_year()
        self.admin = self._make_admin()
        self.teacher_user, self.teacher_profile = self._make_teacher()
        self.student_user, self.student = self._make_student(
            'cred_student', '2026-7101',
        )

    def _badge(self, consumed=False):
        return OfflineBadge.objects.create(
            student_profile=self.student,
            token_hash=hashlib.sha256(f'badge-{timezone.now()}'.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=48),
            consumed_at=timezone.now() if consumed else None,
        )

    def test_rotation_revokes_unconsumed_badges_and_stamps_time(self):
        old_secret = self.student.qr_secret
        badge = self._badge()

        result = rotate_student_credentials(
            self.student, actor=self.admin, reason='Unit test rotation',
        )

        self.student.refresh_from_db()
        self.assertNotEqual(self.student.qr_secret, old_secret)
        self.assertEqual(len(self.student.qr_secret), 64)
        self.assertIsNotNone(self.student.qr_rotated_at)
        self.assertEqual(result['revoked_offline_badges'], 1)
        self.assertFalse(OfflineBadge.objects.filter(pk=badge.pk).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action='STUDENT_QR_RESET', object_id=str(self.student.pk),
            ).exists()
        )

    def test_rotation_preserves_consumed_badges(self):
        badge = self._badge(consumed=True)
        rotate_student_credentials(self.student, actor=self.admin, reason='Unit test')
        self.assertTrue(OfflineBadge.objects.filter(pk=badge.pk).exists())

    def test_rotation_rejects_non_student_profiles(self):
        with self.assertRaises(ValueError):
            rotate_student_credentials(self.teacher_profile, actor=self.admin)

    def test_admin_reset_endpoint_stamps_rotation_time(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('student_qr_reset_ajax'), {'student_id': self.student.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertIsNotNone(self.student.qr_rotated_at)

    def test_profile_editor_reset_uses_same_revocation_path(self):
        badge = self._badge()
        self.client.force_login(self.admin)
        response = self.client.post(reverse('student_profile_update_ajax'), {
            'student_id': self.student.pk,
            'student_number': self.student.student_number,
            'first_name': 'Ana',
            'last_name': 'Cruz',
            'department': self.department.pk,
            'program': self.program.pk,
            'year_level': self.student.year_level,
            'reset_qr': '1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['qr_reset'])
        self.student.refresh_from_db()
        self.assertIsNotNone(self.student.qr_rotated_at)
        self.assertFalse(OfflineBadge.objects.filter(pk=badge.pk).exists())


# // ==============================================================================
# // 1.2 PROTECTED DOCUMENT DELIVERY
# // ==============================================================================
class ProtectedDocumentTests(BaseWeek5FixtureMixin, TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.department = self._make_department()
        self.program = self._make_program()
        self.academic_year = self._make_academic_year()
        self.admin = self._make_admin()
        self.teacher_user, self.teacher_profile = self._make_teacher()
        self.other_teacher_user, _ = self._make_teacher('other_teacher')
        self.student_user, self.student = self._make_student(
            'doc_student', '2026-7201',
        )
        self.other_student_user, _ = self._make_student(
            'other_doc_student', '2026-7202',
        )

        self.student.registration_proof.save(
            'cor.png', ContentFile(_png_bytes()), save=True,
        )

        self.class_obj = self._make_class(self.teacher_profile, code='SEC-1A')
        self.slot = self._make_slot(
            self.class_obj,
            weekday=timezone.localdate().weekday(),
            starts_at=time(8, 0),
            ends_at=time(9, 0),
        )
        self.session = self._make_session(self.slot, timezone.localdate())
        self.slip = ExcuseSlip.objects.create(
            student_profile=self.student,
            session=self.session,
            reason='Medical appointment',
            attachment=SimpleUploadedFile(
                'medcert.png', _png_bytes(), content_type='image/png',
            ),
        )

    def _get_proof(self):
        return self.client.get(
            reverse('registration_proof_document', args=[self.student.pk]),
        )

    def _get_attachment(self):
        return self.client.get(
            reverse('excuse_slip_attachment_document', args=[self.slip.pk]),
        )

    def test_owner_can_view_own_registration_proof(self):
        self.client.force_login(self.student_user)
        response = self._get_proof()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('image/png'))
        self.assertIn(b'PNG', b''.join(response.streaming_content))

    def test_admin_can_view_any_registration_proof(self):
        self.client.force_login(self.admin)
        self.assertEqual(self._get_proof().status_code, 200)

    def test_other_student_cannot_view_registration_proof(self):
        self.client.force_login(self.other_student_user)
        self.assertEqual(self._get_proof().status_code, 403)

    def test_teacher_cannot_view_registration_proof(self):
        self.client.force_login(self.teacher_user)
        self.assertEqual(self._get_proof().status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self._get_proof()
        self.assertEqual(response.status_code, 302)

    def test_missing_proof_returns_404(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse(
                'registration_proof_document',
                args=[self.other_student_user.classstamp_profile.pk],
            ),
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_own_excuse_attachment(self):
        self.client.force_login(self.student_user)
        self.assertEqual(self._get_attachment().status_code, 200)

    def test_assigned_teacher_can_view_excuse_attachment(self):
        self.client.force_login(self.teacher_user)
        self.assertEqual(self._get_attachment().status_code, 200)

    def test_other_teacher_cannot_view_excuse_attachment(self):
        self.client.force_login(self.other_teacher_user)
        self.assertEqual(self._get_attachment().status_code, 403)

    def test_admin_can_view_excuse_attachment(self):
        self.client.force_login(self.admin)
        self.assertEqual(self._get_attachment().status_code, 200)


# // ==============================================================================
# // 1.3 UPLOAD VALIDATION
# // ==============================================================================
class UploadValidationTests(BaseWeek5FixtureMixin, TestCase):
    def setUp(self):
        self.department = self._make_department()
        self.program = self._make_program()

    def test_rejects_disallowed_extension(self):
        upload = SimpleUploadedFile('malware.exe', b'MZ')
        with self.assertRaises(ValidationError):
            validate_uploaded_document(upload)

    def test_rejects_oversized_file(self):
        upload = SimpleUploadedFile(
            'huge.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png',
        )
        with self.assertRaises(ValidationError):
            validate_uploaded_document(upload)

    def test_rejects_fake_pdf(self):
        upload = SimpleUploadedFile(
            'fake.pdf', b'this is not a pdf', content_type='application/pdf',
        )
        with self.assertRaises(ValidationError):
            validate_uploaded_document(upload)

    def test_accepts_valid_pdf(self):
        upload = SimpleUploadedFile(
            'cor.pdf', b'%PDF-1.7\n%%EOF', content_type='application/pdf',
        )
        validate_uploaded_document(upload)

    def test_rejects_fake_image(self):
        upload = SimpleUploadedFile(
            'fake.png', b'not an image', content_type='image/png',
        )
        with self.assertRaises(ValidationError):
            validate_uploaded_document(upload)

    def test_accepts_valid_png(self):
        upload = SimpleUploadedFile(
            'cor.png', _png_bytes(), content_type='image/png',
        )
        validate_uploaded_document(upload)

    def test_registration_form_rejects_executable_proof(self):
        form = RegistrationForm(
            data={
                'username': 'upload_student',
                'first_name': 'Ana',
                'last_name': 'Cruz',
                'email': 'upload_student@example.com',
                'password': 'S3cure!Kcc2026',
                'confirm_password': 'S3cure!Kcc2026',
                'student_number': '2026-7301',
                'program_id': self.program.pk,
                'year_level': 1,
            },
            files={
                'registration_proof': SimpleUploadedFile('malware.exe', b'MZ'),
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn('registration_proof', form.errors)

    def test_excuse_view_rejects_invalid_attachment(self):
        teacher_user, teacher_profile = self._make_teacher('excuse_teacher')
        self.academic_year = self._make_academic_year()
        student_user, student = self._make_student('excuse_student', '2026-7302')
        class_obj = self._make_class(teacher_profile, code='SEC-2A')
        slot = self._make_slot(
            class_obj, weekday=timezone.localdate().weekday(),
            starts_at=time(9, 0), ends_at=time(10, 0),
        )
        session = self._make_session(slot, timezone.localdate())
        self._make_record(session, student, AttendanceRecord.STATUS_ABSENT)

        self.client.force_login(student_user)
        response = self.client.post(reverse('student_excuse_slips'), {
            'session_id': session.pk,
            'reason': 'Sick leave',
            'attachment': SimpleUploadedFile('malware.exe', b'MZ'),
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ExcuseSlip.objects.filter(session=session).exists())


# // ==============================================================================
# // 1.4 OUTPUT ENCODING AND URL CONTRACTS
# // ==============================================================================
class RosterModalEscapingTests(TestCase):
    """
    // The roster modal builds HTML strings in JavaScript. Every student-supplied
    // field interpolated into innerHTML must pass through escapeHtml().
    """

    def test_roster_modal_escapes_interpolated_student_fields(self):
        source = (Path(settings.BASE_DIR) / 'static' / 'js' / 'classes' / 'roster_modal.js').read_text(
            encoding='utf-8'
        )
        self.assertIn('function escapeHtml', source)
        for field in (
            's.profile_id', 's.student_name', 's.student_id', 's.program',
            'en.student_name', 'en.student_id', 'en.program', 'en.enrolled_at',
            'en.enrollment_id', 'err',
        ):
            self.assertIn(
                f'escapeHtml({field})', source,
                f'{field} must be escaped before being written to innerHTML',
            )


class ExcuseReviewUrlContractTests(TestCase):
    """
    // The template emits the reverse() of excuse_slip_review_ajax with id 0 and
    // the JS strips the placeholder to build /<id>/review/. Verify the contract
    // so the two halves cannot drift into a 404 again.
    """

    def test_placeholder_prefix_composes_a_resolvable_review_url(self):
        placeholder = reverse('excuse_slip_review_ajax', args=[0])
        self.assertTrue(placeholder.endswith('/0/review/'))
        prefix = re.sub(r'0/review/?$', '', placeholder)
        composed = f'{prefix}1/review/'
        self.assertEqual(resolve(composed).url_name, 'excuse_slip_review_ajax')


class ValidationRedirectSafetyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, referer):
        request = self.factory.post('/validation/approve/2026-0001/')
        request.META['HTTP_HOST'] = 'testserver'
        if referer is not None:
            request.META['HTTP_REFERER'] = referer
        return request

    def test_external_referer_falls_back_to_local_queue(self):
        response = _redirect_after_validation(
            self._request('https://evil.example/validation/'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('validation_pending_queue'))

    def test_scheme_relative_referer_falls_back_to_local_queue(self):
        response = _redirect_after_validation(
            self._request('//evil.example/validation/'),
        )
        self.assertEqual(response.url, reverse('validation_pending_queue'))

    def test_local_validation_referer_is_followed(self):
        target = '/validation/?tab=reviewed'
        response = _redirect_after_validation(self._request(f'http://testserver{target}'))
        self.assertEqual(response.url, f'http://testserver{target}')


class ViewPackageExportTests(TestCase):
    def test_all_entries_are_unique_strings(self):
        from apps.core import views

        self.assertTrue(all(isinstance(name, str) for name in views.__all__))
        self.assertEqual(len(views.__all__), len(set(views.__all__)))
        exec('from apps.core.views import *', {})  # must not raise TypeError
