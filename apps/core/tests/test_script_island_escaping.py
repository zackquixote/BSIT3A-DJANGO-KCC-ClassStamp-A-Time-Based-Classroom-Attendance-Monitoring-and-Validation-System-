"""
# // ==============================================================================
# // KCC CLASSSTAMP - JSON SCRIPT ISLAND ESCAPING TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Template Data Handoff
# // Description: The admin pages hand JSON to JavaScript through
# //   `<script type="application/json">` islands rendered with `|safe`. That turns
# //   autoescaping off, so the serializer is the only thing standing between a
# //   stored value and an early `</script>`. These tests pin the escape at the unit
# //   level and again through the rendered wizard page.
# // Reference: docs/09_SECURITY_AUDIT_2026-11-14.md
# // ==============================================================================
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Department, Profile, Program
from apps.core.views.helpers.script_json import script_json

User = get_user_model()

HOSTILE = '</script><script>alert(1)</script>'


class ScriptJsonTests(TestCase):
    """The serializer must defuse `</` without changing the JSON it produces."""

    def test_closing_tag_never_reaches_the_document(self):
        payload = script_json([{'name': HOSTILE}])

        self.assertNotIn('</script', payload.lower())
        self.assertIn('<\\/script', payload)

    def test_escaped_payload_still_parses(self):
        payload = script_json([{'name': HOSTILE, 'nested': {'x': '</SCRIPT>'}}])

        self.assertEqual(
            json.loads(payload),
            [{'name': HOSTILE, 'nested': {'x': '</SCRIPT>'}}],
        )

    def test_plain_payload_is_unchanged(self):
        self.assertEqual(script_json(['IT-Lab 1']), '["IT-Lab 1"]')


class WizardIslandTests(TestCase):
    """A hostile program name must not break out of the wizard's island."""

    def setUp(self):
        self.department = Department.objects.create(code='CITCS', name='College of IT')
        self.program = Program.objects.create(
            department=self.department,
            code='BSIT',
            name=f'BS Information Technology {HOSTILE}',
            years_total=4,
        )
        self.admin_user = User.objects.create_user(
            username='island_admin', password='IslandTest!2026',
        )
        Profile.objects.create(user=self.admin_user, role=Profile.ROLE_ADMIN)
        self.client.force_login(self.admin_user)

    def test_wizard_programs_island_escapes_the_closing_tag(self):
        response = self.client.get(reverse('class_wizard_setup'))
        body = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="wizard-programs"', body)
        self.assertNotIn('</script><script>alert(1)', body)
        self.assertIn('<\\/script><script>alert(1)', body)

    def test_wizard_departments_island_is_also_escaped(self):
        self.department.name = f'College of IT {HOSTILE}'
        self.department.save(update_fields=['name'])

        body = self.client.get(reverse('class_wizard_setup')).content.decode('utf-8')

        self.assertIn('id="wizard-departments"', body)
        self.assertNotIn('</script><script>alert(1)', body)
