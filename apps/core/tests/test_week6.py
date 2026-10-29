"""
# // ==============================================================================
# // KCC CLASSSTAMP - WEEK 6 QUICK WINS / POLISH TESTS
# // ==============================================================================
# // Covers:
# //   - S-02: QR badge photo watermark (proxy-sharing deterrent)
# //   - A-16: Automatic WebP compression of uploaded proof images
# //   - A-15: 1-click database backup download (admin)
# //   - A-12: Teacher department reassignment modal endpoint
# // ==============================================================================
"""

import io
import shutil
import tempfile
import zlib
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import AuditEvent, Department
from apps.core.services import optimize_proof_upload
from apps.core.services import backup_service
from apps.core.tests.test_week5 import BaseWeek5FixtureMixin

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is pinned in requirements.txt
    Image = None


def _png_bytes(width=64, height=64, color=(200, 30, 30)):
    buffer = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buffer, format='PNG')
    return buffer.getvalue()


# // ==============================================================================
# // S-02: QR BADGE PHOTO WATERMARK
# // ==============================================================================
class QrBadgeWatermarkTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls._make_admin(cls)
        cls.student_user, cls.student_profile = cls._make_student(
            cls, username='w6_badge_student', student_number='2026-00421',
        )

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        self.client.force_login(self.student_user)

    def _set_proof(self, name, content):
        self.student_profile.registration_proof.save(name, ContentFile(content), save=True)

    def test_no_proof_renders_no_photo_block(self):
        res = self.client.get(reverse('student_qr_badge'))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['proof_is_image'])
        self.assertNotContains(res, '<div class="badge-id-photo"')

    def test_image_proof_flags_and_watermarks(self):
        self._set_proof('cor.png', _png_bytes())
        res = self.client.get(reverse('student_qr_badge'))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['proof_is_image'])
        self.assertTrue(res.context['proof'])
        self.assertContains(res, '<div class="badge-id-photo"')
        self.assertContains(res, 'badge-id-photo__watermark')
        self.assertContains(res, '2026-00421')

    def test_non_image_proof_no_watermark(self):
        self._set_proof('cor.pdf', b'%PDF-1.4 fake pdf')
        res = self.client.get(reverse('student_qr_badge'))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['proof_is_image'])
        self.assertNotContains(res, '<div class="badge-id-photo"')


# // ==============================================================================
# // A-16: AUTO-WEBP STORAGE OPTIMIZER
# // ==============================================================================
class StorageOptimizerTests(TestCase):
    def test_none_passes_through(self):
        self.assertIsNone(optimize_proof_upload(None))

    def test_png_converts_to_webp(self):
        upload = SimpleUploadedFile('proof.png', _png_bytes(200, 100), content_type='image/png')
        result = optimize_proof_upload(upload)
        self.assertTrue(result.name.endswith('.webp'))
        converted = Image.open(io.BytesIO(result.read()))
        self.assertEqual(converted.format, 'WEBP')
        self.assertEqual(converted.size, (200, 100))

    def test_large_image_downscaled_to_max_dimension(self):
        upload = SimpleUploadedFile('huge.png', _png_bytes(2400, 1200), content_type='image/png')
        result = optimize_proof_upload(upload)
        converted = Image.open(io.BytesIO(result.read()))
        self.assertEqual(converted.size, (1600, 800))

    def test_pdf_passes_through_unchanged(self):
        upload = SimpleUploadedFile('cor.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
        result = optimize_proof_upload(upload)
        self.assertIs(result, upload)

    def test_corrupt_raster_passes_through(self):
        upload = SimpleUploadedFile('broken.png', b'not an image', content_type='image/png')
        result = optimize_proof_upload(upload)
        self.assertIs(result, upload)

    def test_original_filename_stem_preserved(self):
        upload = SimpleUploadedFile('my_cor_proof.JPG', _png_bytes(), content_type='image/jpeg')
        result = optimize_proof_upload(upload)
        self.assertEqual(result.name, 'my_cor_proof.webp')


# // ==============================================================================
# // A-15: 1-CLICK DATABASE BACKUP
# // ==============================================================================
class FakePopen:
    instances = []

    def __init__(self, command, **kwargs):
        self.command = command
        self.env = kwargs.get('env') or {}
        self.stdout = io.BytesIO(b'-- SQL dump\nINSERT INTO core_profile VALUES (1);\n')
        self.stderr = io.BytesIO(b'')
        FakePopen.instances.append(self)

    def wait(self):
        return 0


class DatabaseBackupTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls)
        cls.teacher_user, cls.teacher_profile = cls._make_teacher(cls)

    def setUp(self):
        FakePopen.instances = []
        patcher = patch.object(backup_service.subprocess, 'Popen', FakePopen)
        self.mock_popen = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(
            backup_service.shutil, 'which',
            return_value='C:/xampp/mysql/bin/mysqldump.exe',
        )
        self.mock_which = patcher.start()
        self.addCleanup(patcher.stop)

    def test_admin_downloads_gzip_snapshot(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('admin_db_backup'))

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/gzip')
        self.assertRegex(
            res['Content-Disposition'],
            r'attachment; filename="classstamp_backup_\d{8}_\d{6}\.sql\.gz"',
        )
        payload = zlib.decompress(b''.join(res.streaming_content), wbits=31)
        self.assertIn(b'-- SQL dump', payload)

        self.assertEqual(len(FakePopen.instances), 1)
        command = FakePopen.instances[0].command
        self.assertIn('--no-tablespaces', command)
        self.assertIn('--single-transaction', command)
        self.assertIn('MYSQL_PWD', FakePopen.instances[0].env)

        audit = AuditEvent.objects.filter(action='DB_BACKUP_DOWNLOAD', actor=self.admin)
        self.assertTrue(audit.exists())
        self.assertEqual(audit.first().object_type, 'Database')

    def test_each_download_audited(self):
        self.client.force_login(self.admin)
        self.client.get(reverse('admin_db_backup'))
        self.client.get(reverse('admin_db_backup'))
        self.assertEqual(
            AuditEvent.objects.filter(action='DB_BACKUP_DOWNLOAD', actor=self.admin).count(),
            2,
        )

    def test_teacher_blocked(self):
        self.client.force_login(self.teacher_user)
        res = self.client.get(reverse('admin_db_backup'))
        self.assertEqual(res.status_code, 302)
        self.assertFalse(AuditEvent.objects.filter(action='DB_BACKUP_DOWNLOAD').exists())
        self.assertEqual(FakePopen.instances, [])

    def test_anonymous_redirected(self):
        res = self.client.get(reverse('admin_db_backup'))
        self.assertEqual(res.status_code, 302)
        self.assertFalse(AuditEvent.objects.filter(action='DB_BACKUP_DOWNLOAD').exists())

    def test_missing_mysqldump_redirects_with_error(self):
        self.mock_which.return_value = None
        self.client.force_login(self.admin)
        res = self.client.get(reverse('admin_db_backup'))
        self.assertRedirects(res, reverse('admin_dashboard'))
        self.assertFalse(AuditEvent.objects.filter(action='DB_BACKUP_DOWNLOAD').exists())

    def test_dump_failure_raises_on_stream_consumption(self):
        class FailingPopen(FakePopen):
            def __init__(self, command, **kwargs):
                super().__init__(command, **kwargs)
                self.stderr = io.BytesIO(b'Access denied for user root')

            def wait(self):
                return 2

        original = backup_service.subprocess.Popen
        backup_service.subprocess.Popen = FailingPopen
        self.addCleanup(setattr, backup_service.subprocess, 'Popen', original)

        self.client.force_login(self.admin)
        res = self.client.get(reverse('admin_db_backup'))
        self.assertEqual(res.status_code, 200)
        with self.assertRaises(RuntimeError):
            b''.join(res.streaming_content)


# // ==============================================================================
# // A-12: TEACHER DEPARTMENT REASSIGNMENT
# // ==============================================================================
class TeacherReassignTests(BaseWeek5FixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = cls._make_department(cls)
        cls.program = cls._make_program(cls)
        cls.academic_year = cls._make_academic_year(cls)
        cls.admin = cls._make_admin(cls)
        cls.teacher_user, cls.teacher_profile = cls._make_teacher(cls)
        cls.student_user, cls.student_profile = cls._make_student(
            cls, username='w6_reassign_student', student_number='2026-00999',
        )
        cls.business = Department.objects.create(
            code='CBA', name='College of Business Administration', is_active=True,
        )
        cls.inactive = Department.objects.create(
            code='ARCHIVED', name='Archived Department', is_active=False,
        )

    def _post(self, pk, dept_id):
        return self.client.post(
            reverse('teacher_reassign_ajax', args=[pk]),
            data={'dept_id': dept_id},
        )

    def test_reassign_success(self):
        self.client.force_login(self.admin)
        res = self._post(self.teacher_profile.pk, self.business.pk)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['department_code'], 'CBA')
        self.assertEqual(data['class_count'], 0)
        self.assertIn('reassigned', data['message'])

        self.teacher_profile.refresh_from_db()
        self.assertEqual(self.teacher_profile.department, self.business)

        audit = AuditEvent.objects.get(action='TEACHER_REASSIGNED')
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.old_value, 'College of Computer Studies')
        self.assertEqual(audit.new_value, 'College of Business Administration')
        self.assertEqual(audit.object_id, str(self.teacher_profile.pk))

    def test_class_count_reported_and_load_kept(self):
        self.client.force_login(self.admin)
        class_obj = self._make_class(self.teacher_profile, code='BSIT-2B')
        res = self._post(self.teacher_profile.pk, self.business.pk)
        self.assertEqual(res.json()['class_count'], 1)
        class_obj.refresh_from_db()
        self.assertEqual(class_obj.teacher_profile, self.teacher_profile)

    def test_same_department_rejected(self):
        self.client.force_login(self.admin)
        res = self._post(self.teacher_profile.pk, self.department.pk)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])
        self.assertIn('already assigned', res.json()['error'])
        self.assertFalse(AuditEvent.objects.filter(action='TEACHER_REASSIGNED').exists())

    def test_invalid_dept_id_rejected(self):
        self.client.force_login(self.admin)
        res = self._post(self.teacher_profile.pk, 'not-a-number')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])

    def test_unknown_teacher_404(self):
        self.client.force_login(self.admin)
        res = self._post(999999, self.business.pk)
        self.assertEqual(res.status_code, 404)

    def test_student_profile_404(self):
        self.client.force_login(self.admin)
        res = self._post(self.student_profile.pk, self.business.pk)
        self.assertEqual(res.status_code, 404)

    def test_inactive_department_404(self):
        self.client.force_login(self.admin)
        res = self._post(self.teacher_profile.pk, self.inactive.pk)
        self.assertEqual(res.status_code, 404)

    def test_get_method_not_allowed(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('teacher_reassign_ajax', args=[self.teacher_profile.pk]))
        self.assertEqual(res.status_code, 405)

    def test_teacher_blocked(self):
        self.client.force_login(self.teacher_user)
        res = self._post(self.teacher_profile.pk, self.business.pk)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(AuditEvent.objects.filter(action='TEACHER_REASSIGNED').exists())

    def test_anonymous_redirected(self):
        res = self._post(self.teacher_profile.pk, self.business.pk)
        self.assertEqual(res.status_code, 302)
