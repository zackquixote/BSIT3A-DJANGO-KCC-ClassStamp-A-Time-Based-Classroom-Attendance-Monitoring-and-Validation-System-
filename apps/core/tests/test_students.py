"""
# // ==============================================================================
# // KCC CLASSSTAMP - STUDENT DIRECTORY VIEW TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Student Management Module
# // Description: Tests for the admin-only Student Directory including:
# //   - RBAC enforcement (admin-only access)
# //   - Directory listing and search filters
# //   - CSV export correctness
# //   - Bulk CSV import (with auto-approve)
# //   - Sample CSV template download
# //   - Per-page pagination control
# // ==============================================================================
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Department, Profile, Program

User = get_user_model()


class StudentDirectoryViewTests(TestCase):
    """Tests for the admin student directory, CSV export/import, and sample download."""

    def setUp(self):
        # Admin user via superuser shortcut (no explicit Profile needed)
        self.admin = User.objects.create_superuser(username='admin_dir', password='password123')

        self.dept = Department.objects.create(code='CMAT', name='College of Management')
        self.prog = Program.objects.create(
            department=self.dept, code='BSIT', name='BS Information Tech', years_total=4,
        )
        self.student_user = User.objects.create_user(
            username='stu1', first_name='Juan', last_name='Luna', email='jluna@kcc.ph',
        )
        self.profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            program=self.prog,
            year_level=2,
            student_number='2024-0099',
            approval_status=Profile.APPROVAL_APPROVED,
        )

    # ------------------------------------------------------------------
    # Access Control
    # ------------------------------------------------------------------

    def test_student_directory_requires_admin(self):
        # Anonymous request must be redirected away.
        res = self.client.get(reverse('student_directory'))
        self.assertEqual(res.status_code, 302)

    def test_student_directory_renders_for_admin(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '2024-0099')
        self.assertContains(res, 'Juan Luna')

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def test_student_directory_filters(self):
        self.client.force_login(self.admin)

        # Filter by department — should include the student
        res = self.client.get(reverse('student_directory'), {'department': str(self.dept.id)})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '2024-0099')

        # Filter by a year level the student is NOT in
        res_empty = self.client.get(reverse('student_directory'), {'year_level': '4'})
        self.assertEqual(res_empty.status_code, 200)
        self.assertNotContains(res_empty, '2024-0099')

    # ------------------------------------------------------------------
    # CSV Export
    # ------------------------------------------------------------------

    def test_student_directory_export_csv(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory_export_csv'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')
        content = res.content.decode('utf-8')
        self.assertIn('2024-0099', content)
        self.assertIn('Juan', content)
        self.assertIn('Luna', content)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def test_student_directory_page_size(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_directory'), {'per_page': '40'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['per_page'], 40)

    # ------------------------------------------------------------------
    # Sample CSV Template Download
    # ------------------------------------------------------------------

    def test_sample_csv_download(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('student_import_sample_csv'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')
        content = res.content.decode('utf-8')
        self.assertIn('student_number', content)
        self.assertIn('BSIT-3A', content)

    # ------------------------------------------------------------------
    # Bulk CSV Import
    # ------------------------------------------------------------------

    def test_bulk_csv_import(self):
        self.client.force_login(self.admin)
        csv_content = (
            "student_number,first_name,last_name,email,program,year_level,section\n"
            "2024-0555,Carlos,Yulo,carlos@kcc.ph,BSIT,3,BSIT-3A\n"
        ).encode('utf-8')
        csv_file = SimpleUploadedFile("section_roster.csv", csv_content, content_type="text/csv")
        res = self.client.post(reverse('student_directory_import_csv'), {
            'csv_file': csv_file,
            'auto_approve': 'on',
        })
        self.assertEqual(res.status_code, 200)

        # Verify the imported student exists and has the correct field values.
        self.assertTrue(Profile.objects.filter(student_number='2024-0555').exists())
        imported_student = Profile.objects.get(student_number='2024-0555')
        self.assertEqual(imported_student.approval_status, Profile.APPROVAL_APPROVED)
        self.assertEqual(imported_student.user.first_name, 'Carlos')
        self.assertEqual(imported_student.user.last_name, 'Yulo')
        # QR secret must be 64 characters at the point of import.
        self.assertEqual(len(imported_student.qr_secret), 64)

    # ------------------------------------------------------------------
    # Initials & Avatar Badge
    # ------------------------------------------------------------------

    def test_profile_initials_computation(self):
        # 1. Standard first + last name: "Juan Luna" -> "JL"
        self.assertEqual(self.profile.initials, "JL")

        # 2. Multi-word first name + last name: "Yaster Josua Dado" -> "YD"
        u2 = User.objects.create_user(username='yj_dado', first_name='Yaster Josua', last_name='Dado')
        p2 = Profile.objects.create(user=u2, role=Profile.ROLE_STUDENT, program=self.prog, year_level=3, student_number='2024-611044')
        self.assertEqual(p2.initials, "YD")

        # 3. Full name in first_name with empty last_name: "Yaster Josua Dado" -> "YD"
        u3 = User.objects.create_user(username='yj_full', first_name='Yaster Josua Dado', last_name='')
        p3 = Profile.objects.create(user=u3, role=Profile.ROLE_STUDENT, program=self.prog, year_level=3, student_number='2024-611045')
        self.assertEqual(p3.initials, "YD")

        # 4. Single word in first_name: "Ronelo" -> "RO"
        u4 = User.objects.create_user(username='ronelo', first_name='Ronelo', last_name='')
        p4 = Profile.objects.create(user=u4, role=Profile.ROLE_STUDENT, program=self.prog, year_level=3, student_number='2024-611046')
        self.assertEqual(p4.initials, "RO")

        # 5. Username fallback when names are empty
        u5 = User.objects.create_user(username='admin')
        p5 = Profile.objects.create(user=u5, role=Profile.ROLE_ADMIN)
        self.assertEqual(p5.initials, "AD")

