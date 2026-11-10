#!/usr/bin/env python
"""Thin manage.py wrapper for restricted Python environments.

Some bundled/embedded Python builds (e.g. `._pth`-configured distributions)
do not put the script's directory on `sys.path`, which breaks the standard
``python manage.py ...`` invocation with ``ModuleNotFoundError: mysite``.
This wrapper explicitly inserts the project root and then delegates to
Django's standard command-line entry point. Usage is identical to manage.py:

    python pmanage.py test apps.core.tests.test_week7 --verbosity 1
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')


def main():
    """Run administrative tasks."""
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
