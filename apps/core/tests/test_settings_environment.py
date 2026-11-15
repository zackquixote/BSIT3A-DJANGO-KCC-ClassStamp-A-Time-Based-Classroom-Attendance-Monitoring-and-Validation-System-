"""
# // ==============================================================================
# // KCC CLASSSTAMP - SETTINGS ENVIRONMENT SELECTION TESTS
# // ==============================================================================
# // Subsystem: Quality Assurance — Deployment Configuration
# // Description: `mysite/settings/__init__.py` decides between the development and
# //   production modules. Getting that wrong is how the live site ended up serving
# //   DEBUG=True, so each branch is pinned here: unset off-server, unset on
# //   PythonAnywhere, an explicit value, and a typo.
# // Reference: docs/09_SECURITY_AUDIT_2026-11-14.md
# // ==============================================================================
"""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# // The bundled interpreter runs with safe_path, so the project root has to be
# // put back on sys.path inside the child process as well.
CHILD = (
    'import sys; sys.path.insert(0, {root!r});'
    'import mysite.settings as s;'
    'print("DEBUG", s.DEBUG);'
    'print("PROD", getattr(s, "SECURE_HSTS_SECONDS", 0) > 0)'
).format(root=str(PROJECT_ROOT))


def _run(**overrides):
    env = {key: value for key, value in os.environ.items() if key != 'DJANGO_ENV'}
    for key in ('PYTHONANYWHERE_DOMAIN', 'PYTHONANYWHERE_SITE'):
        env.pop(key, None)
    env.update(overrides)
    return subprocess.run(
        [sys.executable, '-c', CHILD],
        cwd=str(PROJECT_ROOT), env=env, text=True, capture_output=True,
    )


class SettingsSelectionTests(SimpleTestCase):
    """The default must depend on where the code runs, not on convenience."""

    def test_local_machine_defaults_to_development(self):
        completed = _run()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('DEBUG True', completed.stdout)
        self.assertIn('PROD False', completed.stdout)

    def test_pythonanywhere_without_django_env_fails_closed(self):
        # // An empty value keeps a developer's local .env out of the result:
        # // python-dotenv does not override a variable that is already set.
        completed = _run(PYTHONANYWHERE_DOMAIN='pythonanywhere.com', DJANGO_SECRET_KEY='')

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', completed.stderr)
        self.assertNotIn('DEBUG True', completed.stdout)

    def test_explicit_production_uses_the_hardened_module(self):
        completed = _run(
            DJANGO_ENV='production',
            DJANGO_SECRET_KEY='s' * 60,
            DJANGO_ALLOWED_HOSTS='kccclassstamp.pythonanywhere.com',
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('DEBUG False', completed.stdout)
        self.assertIn('PROD True', completed.stdout)

    def test_unknown_value_is_rejected_rather_than_downgraded(self):
        completed = _run(DJANGO_ENV='productionn')

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('not a known environment', completed.stderr)
        self.assertNotIn('DEBUG True', completed.stdout)
