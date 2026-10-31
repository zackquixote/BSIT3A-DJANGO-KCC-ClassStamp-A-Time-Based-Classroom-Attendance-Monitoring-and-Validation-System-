"""
# // ==============================================================================
# // KCC CLASSSTAMP - TEST SUITE PACKAGE INITIALISER
# // ==============================================================================
# // Subsystem: Quality Assurance / Regression Guard
# // Description: Re-exports every test class from each domain module so that
# //   `python manage.py test apps.core` continues to discover and run all 52
# //   tests without any path changes.
# //
# // Module layout (mirrors apps/core/views/ split):
# //   test_home.py          — HomeViewTests (dashboard redirect smoke tests)
# //   test_auth.py          — RegistrationViewTests, LoginFlowTests
# //   test_validation.py    — AccountValidationTests (approval/rejection workflow)
# //   test_dashboard.py     — DashboardDispatchTests (role-based routing)
# //   test_departments.py   — DepartmentProgramCrudTests (academic org CRUD)
# //   test_middleware.py    — CacheControlMiddlewareTests
# //   test_students.py      — StudentDirectoryViewTests (directory, CSV, import)
# // ==============================================================================
"""

from .test_home import HomeViewTests
from .test_auth import RegistrationViewTests, LoginFlowTests
from .test_validation import AccountValidationTests
from .test_dashboard import DashboardDispatchTests
from .test_departments import DepartmentProgramCrudTests
from .test_middleware import CacheControlMiddlewareTests
from .test_students import StudentDirectoryViewTests
from .test_security_hardening import (
    CredentialLifecycleTests,
    ProtectedDocumentTests,
    UploadValidationTests,
)

__all__ = [
    'HomeViewTests',
    'RegistrationViewTests',
    'LoginFlowTests',
    'AccountValidationTests',
    'DashboardDispatchTests',
    'DepartmentProgramCrudTests',
    'CacheControlMiddlewareTests',
    'StudentDirectoryViewTests',
    'CredentialLifecycleTests',
    'ProtectedDocumentTests',
    'UploadValidationTests',
]
