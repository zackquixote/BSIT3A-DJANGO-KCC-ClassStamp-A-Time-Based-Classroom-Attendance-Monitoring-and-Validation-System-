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
# // Security Reference: docs/02_SECURITY.md
# // ==============================================================================
"""

import math
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
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

def client_ip(request) -> str:
    """Client address from the socket.

    Forwarding headers are deliberately not trusted: without a known,
    configured reverse proxy any client can set X-Forwarded-For and rotate
    through unlimited rate-limit buckets. One trusted value beats a spoofable
    "best effort".
    """
    return request.META.get('REMOTE_ADDR', 'unknown')


def _throttle_keys(request, identifier=''):
    ip = client_ip(request)
    normalized = (identifier or '').strip().lower()
    return normalized, ip


def _reset_lock_state(request, identifier=''):
    """
    // Clears failed attempt counters and active unlock timestamps from the user session.
    // Called on successful login or after lockout duration has expired.
    """
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None
    normalized, ip = _throttle_keys(request, identifier)
    cache.delete(f'login_failures:ip:{ip}')
    cache.delete(f'login_lock:ip:{ip}')
    if normalized:
        cache.delete(f'login_failures:account:{normalized}')
        cache.delete(f'login_lock:account:{normalized}')


def _record_failed_attempt(request, identifier='', timeout_seconds=300):
    normalized, ip = _throttle_keys(request, identifier)
    ip_key = f'login_failures:ip:{ip}'
    ip_failures = cache.get(ip_key, 0) + 1
    cache.set(ip_key, ip_failures, timeout_seconds)
    if normalized:
        account_key = f'login_failures:account:{normalized}'
        account_failures = cache.get(account_key, 0) + 1
        cache.set(account_key, account_failures, timeout_seconds)
        return max(ip_failures, account_failures)
    return ip_failures


def _get_lock_state(request, identifier=''):
    """
    // Inspects session metadata to determine if the client is actively throttled.
    //
    // Returns: (failed_attempts: int, remaining_seconds: int | None)
    //   - remaining_seconds is None if no active lockout exists.
    //   - remaining_seconds > 0 if the client is still within a lockout window.
    """
    normalized, ip = _throttle_keys(request, identifier)
    account_failures = cache.get(f'login_failures:account:{normalized}', 0) if normalized else 0
    ip_failures = cache.get(f'login_failures:ip:{ip}', 0)
    failed_attempts = max(account_failures, ip_failures, request.session.get('failed_attempts', 0))
    lock_time = request.session.get('lock_time')
    locks = []
    if normalized:
        locks.append(cache.get(f'login_lock:account:{normalized}'))
    locks.append(cache.get(f'login_lock:ip:{ip}'))
    active_locks = [value for value in locks if value]
    if active_locks:
        lock_time = max(active_locks)

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        # // Corrupted timestamp format: clear state and allow retry
        _reset_lock_state(request)
        return 0, None

    now = timezone.now()
    if now < unlock_time:
        # // Rounded up, never truncated: int() released the client up to a
        # // second before the server accepted an attempt again, so the first
        # // retry after a visible countdown ended in a fresh lockout.
        remaining = math.ceil((unlock_time - now).total_seconds())
        return failed_attempts, remaining

    # // Lockout duration has expired; restore clean state
    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request, identifier=''):
    """
    // Activates temporary lockout window for the client session upon threshold breach.
    // Returns: remaining_seconds (int) — how long until the lock expires.
    """
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    timeout = int(LOCK_DURATION.total_seconds())
    normalized, ip = _throttle_keys(request, identifier)
    cache.set(f'login_lock:ip:{ip}', lock_until.isoformat(), timeout)
    cache.set(f'login_failures:ip:{ip}', MAX_FAILED_ATTEMPTS, timeout)
    if normalized:
        cache.set(f'login_lock:account:{normalized}', lock_until.isoformat(), timeout)
        cache.set(f'login_failures:account:{normalized}', MAX_FAILED_ATTEMPTS, timeout)
    return int(LOCK_DURATION.total_seconds())


# // ==============================================================================
# // SECTION 3: REGISTRATION FORM VALIDATION HELPER
# // ==============================================================================

def _validate_registration_data(data, proof_file=None):
    """
    // [Input Sanitization & Server-Side Validation]
    // Verifies form data against user uniqueness, email syntax, password complexity,
    // and academic constraints (program length vs requested standing year).
    //
    // Arguments:
    //   data (dict): POST form field values.
    //   proof_file (File): Uploaded COR / school-ID proof. Required — the admin
    //                      validates every account against this document, so a
    //                      registration without it can never be approved.
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

    # // 3. Student Registration Password Validation
    # Mirrors the live 4-rule checklist on the registration form
    # (#passwordChecklist in templates/auth/register.html) one-to-one:
    #   length >= 8, lower + upper case, at least 1 number, at least 1 symbol.
    # Similarity / common-password rejection stays relaxed so a student is never
    # rejected for a rule the checklist never showed.
    if not password:
        errors['password'] = 'Password is required.'
    elif password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'
    else:
        pwd_problems = []
        if len(password) < 8:
            pwd_problems.append('Password must be at least 8 characters long.')
        if not re.search(r'[a-z]', password) or not re.search(r'[A-Z]', password):
            pwd_problems.append('Password must include both lowercase and uppercase letters (a-z and A-Z).')
        if not re.search(r'\d', password):
            pwd_problems.append('Password must include at least 1 number (0-9).')
        if not re.search(r'[^A-Za-z0-9\s]', password):
            pwd_problems.append(
                'Password must include at least 1 symbol or special character '
                '(for example ! @ # $ % ^ & *).'
            )
        if pwd_problems:
            errors['password'] = ' '.join(pwd_problems)

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

    student_type = data.get('student_type', 'REGULAR').strip().upper()
    if student_type and student_type not in ['REGULAR', 'IRREGULAR', 'TRANSFEREE']:
        errors['student_type'] = 'Invalid student classification selected.'

    # // 5. COR / School ID Proof — required for admin validation
    if proof_file is None or not getattr(proof_file, 'name', ''):
        errors['registration_proof'] = (
            'Please upload your Certificate of Registration (COR) or school ID photo. '
            'It is required before your account can be validated.'
        )
    elif not getattr(proof_file, 'size', 0):
        errors['registration_proof'] = 'The uploaded file is empty. Please upload a valid COR or ID photo.'

    return errors
