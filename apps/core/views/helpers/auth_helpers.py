"""
# // ==============================================================================
# // KCC CLASSSTAMP - AUTHENTICATION HELPER UTILITIES
# // ==============================================================================
# // Subsystem: Session Rate-Limiting & Registration Validation Support
# // Description: Pure utility functions used by auth_views.py:
# //
# //   CONSTANTS:
# //     MAX_FAILED_ATTEMPTS  — Login failures before lockout triggers
# //     LOCK_DURATION        — How long the lockout window lasts
# //     INVALID_LOGIN_MESSAGE — Standard "wrong credentials" message
# //     LOCKED_MESSAGE        — Standard "too many attempts" message
# //
# //   RATE-LIMITING HELPERS:
# //     _reset_lock_state()  — Clears failed-attempt session counters
# //     _get_lock_state()    — Reads session to determine lockout status
# //     _set_lock_state()    — Activates lockout window
# //
# //   REGISTRATION HELPER:
# //     _validate_registration_data() — Full server-side form validation
# //       guarding username uniqueness, email syntax, password complexity,
# //       academic year-level vs program-length constraints, and
# //       student ID uniqueness.
# //
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md
# // ==============================================================================
"""

import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from apps.core.models import Profile, Program

User = get_user_model()


# // ==============================================================================
# // SECTION 1: RATE-LIMITING CONSTANTS
# // ==============================================================================

# // Maximum consecutive failed login attempts before session lockout is triggered
MAX_FAILED_ATTEMPTS = 5

# // Duration of the lockout window after threshold breach
LOCK_DURATION = timedelta(minutes=1)

# // Standard user-facing error messages
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


# // ==============================================================================
# // SECTION 2: SESSION RATE-LIMITING HELPERS
# // ==============================================================================

def _reset_lock_state(request):
    """
    // Clears failed attempt counters and active unlock timestamps from the user session.
    // Called on successful login or after lockout duration has expired.
    """
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    """
    // Inspects session metadata to determine if the client is actively throttled.
    //
    // Returns: (failed_attempts: int, remaining_seconds: int | None)
    //   - remaining_seconds is None if no active lockout exists.
    //   - remaining_seconds > 0 if the client is still within a lockout window.
    """
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        # // Corrupted timestamp format: clear state and allow retry
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    # // Lockout duration has expired; restore clean state
    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    """
    // Activates temporary lockout window for the client session upon threshold breach.
    // Returns: remaining_seconds (int) — how long until the lock expires.
    """
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


# // ==============================================================================
# // SECTION 3: REGISTRATION FORM VALIDATION HELPER
# // ==============================================================================

def _validate_registration_data(data):
    """
    // [Input Sanitization & Server-Side Validation]
    // Verifies form data against user uniqueness, email syntax, password complexity,
    // and academic constraints (program length vs requested standing year).
    //
    // Arguments:
    //   data (dict): POST form field values.
    //
    // Returns:
    //   errors (dict): Field-keyed validation error messages. Empty dict = valid.
    //
    // Guards these live-DB constraints:
    //   - chk_cs_profile_shape: year_level <= program.years_total
    //   - User.username and User.email uniqueness
    //   - Profile.student_number uniqueness
    """
    errors = {}

    student_number = data.get('student_number', '').strip()
    username = data.get('username', '').strip() or student_number
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    gender = data.get('gender', '').strip().upper()
    phone_number = data.get('phone_number', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    # // 1. User Identity Fields
    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not gender:
        errors['gender'] = 'Please select your gender.'
    elif gender not in ['M', 'F']:
        errors['gender'] = 'Invalid gender selected.'

    if not phone_number:
        errors['phone_number'] = 'Phone number is required.'
    else:
        clean_phone = re.sub(r'[\s\-\(\)\+]', '', phone_number)
        if not clean_phone.isdigit() or len(clean_phone) < 10 or len(clean_phone) > 13:
            errors['phone_number'] = 'Please enter a valid mobile number (e.g., 09123456789).'

    # // 2. Email Validation
    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'

    # // 3. Password Complexity Validation (uses Django AUTH_PASSWORD_VALIDATORS)
    if not password:
        errors['password'] = 'Password is required.'
    elif password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'
    else:
        dummy_user = User(username=username, email=email, first_name=first_name, last_name=last_name)
        try:
            validate_password(password, dummy_user)
        except ValidationError as e:
            errors['password'] = ' '.join(e.messages)

    # // 4. Academic Enrollment Constraints
    if not student_number:
        errors['student_number'] = 'Student ID number is required.'
    elif Profile.objects.filter(student_number=student_number).exists():
        errors['student_number'] = 'Student ID number already registered.'
    elif User.objects.filter(username=username).exists():
        errors['student_number'] = 'An account with this Student ID or username already exists.'

    program_id = data.get('program_id', '').strip()
    year_level = data.get('year_level', '').strip()
    program = None

    if not program_id:
        errors['program_id'] = 'Please select a program.'
    else:
        try:
            program = Program.objects.get(pk=int(program_id), is_active=True)
        except (Program.DoesNotExist, ValueError):
            errors['program_id'] = 'Selected program is invalid or inactive.'
            program = None

    if not year_level:
        errors['year_level'] = 'Please select a year level.'
    elif program:
        try:
            yl_int = int(year_level)
            if yl_int < 1 or yl_int > program.years_total:
                errors['year_level'] = (
                    f'Year level {yl_int} is invalid for {program.code} '
                    f'(maximum {program.years_total} years).'
                )
        except (ValueError, TypeError):
            errors['year_level'] = 'Invalid year level.'

    return errors
