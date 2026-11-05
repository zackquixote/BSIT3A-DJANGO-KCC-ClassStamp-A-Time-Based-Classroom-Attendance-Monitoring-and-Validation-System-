"""
# // ==============================================================================
# // KCC CLASSSTAMP - AUTHENTICATION & REGISTRATION CONTROLLERS
# // ==============================================================================
# // Subsystem: Session Lifecycle, Brute-Force Rate Limiting & Account Creation
# // Description: Handles credential validation, multi-identifier login (Username /
# // Email / Student ID), session fixation prevention, session destruction (logout),
# // and student self-registration workflow with dynamic QR secret provisioning.
# // Security References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md
# // ==============================================================================
"""

import secrets

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.core.models import AuditEvent, Department, Profile, Program
from apps.core.services import provision_student_account
from apps.core.services.password_reset_service import (
    read_reset_token,
    request_reset,
    reset_password,
)
from apps.core.services.two_factor_service import (
    generate_recovery_codes,
    is_privileged,
    new_secret,
    provisioning_uri,
    qr_data_uri,
    remaining_recovery_codes,
    reset_two_factor,
    two_factor_required,
    verify_code,
    verify_code_for_secret,
    verify_second_factor,
)
from apps.core.views.helpers import (
    INVALID_LOGIN_MESSAGE,
    LOCK_DURATION,
    LOCKED_MESSAGE,
    MAX_FAILED_ATTEMPTS,
    _get_lock_state,
    _reset_lock_state,
    _set_lock_state,
    _record_failed_attempt,
    _validate_registration_data,
)

User = get_user_model()


# // Constants and helpers are defined in helpers/auth_helpers.py
# // and imported above — this file contains only HTTP view controllers.


# // ==============================================================================
# // VIEW: Login Controller (Flexible Multi-Identifier Sign-In)
# // ==============================================================================
@require_http_methods(['GET', 'POST'])
def login_view(request):
    """
    // [Authentication Controller]
    // Handles user sign-in with multi-identifier lookup:
    // 1. By direct Username
    // 2. By Email address
    // 3. By Student ID number (maps via Profile.student_number)
    //
    // Security & RBAC Enforcement:
    // - Enforces rate-limiting lockout after 5 consecutive failures.
    // - Verifies account approval status (Pending/Rejected accounts are blocked).
    // - Cycles session keys upon privilege change to prevent session-fixation attacks.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    login_input = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    failed_attempts, remaining = _get_lock_state(request, login_input)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    # // [Flexible Identity Lookup]
    user_obj = None
    if '@' in login_input:
        user_obj = User.objects.filter(email__iexact=login_input).first()
    else:
        user_obj = User.objects.filter(username__iexact=login_input).first()
        if not user_obj:
            student_profile = (
                Profile.objects.filter(student_number__iexact=login_input)
                .select_related('user')
                .first()
            )
            if student_profile:
                user_obj = student_profile.user

    user = None
    if user_obj:
        user = authenticate(request, username=user_obj.username, password=password)

    if user is not None:
        # // [Superuser Profile Self-Provisioning]
        profile = getattr(user, 'classstamp_profile', None)
        if user.is_superuser and not profile:
            profile, _ = Profile.objects.get_or_create(user=user, defaults={'role': Profile.ROLE_ADMIN})

        # // [RBAC Approval Lifecycle Guard]
        if profile and profile.role != Profile.ROLE_ADMIN and not user.is_superuser:
            if profile.approval_status == Profile.APPROVAL_PENDING:
                messages.warning(
                    request,
                    'Your account registration is currently PENDING Admin validation. '
                    'Please wait for approval before signing in.'
                )
                return render(request, 'auth/login.html')
            elif profile.approval_status == Profile.APPROVAL_REJECTED:
                reason = f" Reason: {profile.approval_note}" if profile.approval_note else ""
                messages.error(
                    request,
                    f'Your account registration was rejected by the Admin.{reason}'
                )
                return render(request, 'auth/login.html')

        # // [Second Factor] A password alone must not mint an authenticated
        # // session for a privileged account. Park the identity in the session and
        # // hand off to the TOTP step; the failure counter is NOT reset until the
        # // code is also accepted, so a stolen password still hits the lockout.
        if two_factor_required(profile):
            request.session.cycle_key()
            request.session[PENDING_2FA_USER_KEY] = user.pk
            request.session[PENDING_2FA_AT_KEY] = timezone.now().timestamp()
            request.session[PENDING_2FA_ATTEMPTS_KEY] = 0
            return redirect('two_factor_verify')

        # // [Success Route] Reset failed attempt trackers and rotate session key
        _reset_lock_state(request, login_input)
        login(request, user)
        request.session.cycle_key()
        return redirect('dashboard')

    # // [Failure Route] Increment failure counter and apply lockout if threshold reached
    failed_attempts = _record_failed_attempt(request, login_input)
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request, login_input)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


# // ==============================================================================
# // VIEW: Logout Controller
# // ==============================================================================
@require_http_methods(['POST'])
def logout_view(request):
    """
    // Terminates current user session, clears authentication cookies,
    // and returns strict Cache-Control headers to invalidate browser history cache.
    """
    logout(request)
    response = redirect('login')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


# // ==============================================================================
# // VIEW: Session Keepalive Endpoint (/session/keepalive/)
# // ==============================================================================
@require_http_methods(['POST'])
def session_keepalive(request):
    """
    // [AJAX Controller] Refreshes session last_activity timestamp to prevent
    // premature timeout when the user interacts with the session warning dialog.
    """
    if request.user.is_authenticated:
        request.session['last_activity'] = timezone.now().isoformat()
        return JsonResponse({'ok': True, 'refreshed': True})
    return JsonResponse({'ok': False, 'error': 'unauthenticated'}, status=401)


# // ==============================================================================
# // VIEW: Student Self-Registration Controller
# // ==============================================================================
@require_http_methods(['GET', 'POST'])
def register_view(request):
    """
    // [Registration Controller]
    // Handles public student self-registration:
    // 1. Presents dynamic department & program options.
    // 2. Creates the primary Auth User record.
    // 3. Generates the Student Profile with PENDING approval state.
    // 4. Seeds a 64-char QR TOTP secret required by database constraint `chk_cs_profile_shape`.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = Program.objects.filter(is_active=True).select_related('department').order_by('name')

    if request.method == 'GET':
        return render(request, 'auth/register.html', {
            'departments': departments,
            'programs': programs,
        })

    student_num = request.POST.get('student_number', '').strip()
    form_data = {
        'username': request.POST.get('username', '').strip() or student_num,
        'first_name': request.POST.get('first_name', '').strip(),
        'last_name': request.POST.get('last_name', '').strip(),
        'gender': request.POST.get('gender', '').strip().upper(),
        'phone_number': request.POST.get('phone_number', '').strip(),
        'email': request.POST.get('email', '').strip(),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
        'student_number': student_num,
        'student_type': request.POST.get('student_type', 'REGULAR').strip().upper() or 'REGULAR',
        'department_id': request.POST.get('department_id', '').strip(),
        'program_id': request.POST.get('program_id', '').strip(),
        'year_level': request.POST.get('year_level', '').strip(),
    }
    proof_file = request.FILES.get('registration_proof')

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {
            'departments': departments,
            'programs': programs,
            'errors': errors,
            'form_data': form_data,
        })

    try:
        provision_student_account(form_data, proof_file)
    except ValidationError as exc:
        return render(request, 'auth/register.html', {
            'departments': departments,
            'programs': programs,
            'errors': {'registration_proof': ' '.join(exc.messages)},
            'form_data': form_data,
        })

    messages.success(
        request,
        'Registration submitted successfully! Your account is now pending Admin approval. '
        'You can sign in once validated.'
    )
    return redirect('login')


# // ==============================================================================
# // VIEW: AJAX Registration Availability Checker
# // ==============================================================================
@require_http_methods(['GET'])
def check_registration_availability(request):
    """
    // [AJAX Utility] Real-Time Registration Uniqueness Checker
    // Checks availability of username, student number, or email before form submission.
    """
    field_type = request.GET.get('type', '').strip().lower()
    value = request.GET.get('value', '').strip()

    if not value:
        return JsonResponse({'available': True, 'message': ''})

    if field_type == 'student_number':
        exists = Profile.objects.filter(student_number__iexact=value).exists()
        if exists:
            return JsonResponse({'available': False, 'message': f'Student ID "{value}" is already registered.'})
        return JsonResponse({'available': True, 'message': 'Student ID is available.'})

    elif field_type == 'username':
        exists = User.objects.filter(username__iexact=value).exists()
        if exists:
            return JsonResponse({'available': False, 'message': f'Username "{value}" is already taken.'})
        return JsonResponse({'available': True, 'message': 'Username is available.'})

    elif field_type == 'email':
        exists = User.objects.filter(email__iexact=value).exists()
        if exists:
            return JsonResponse({'available': False, 'message': f'Email "{value}" is already in use.'})
        return JsonResponse({'available': True, 'message': 'Email address is available.'})

    return JsonResponse({'available': True, 'message': ''})


# // ==============================================================================
# // VIEW: Admin Force-Reset User Password (#4)
# // ==============================================================================
from django.contrib.auth.decorators import login_required  # noqa: E402 (already imported)
from apps.core.decorators import role_required as _role_required  # noqa: E402


@login_required(login_url='login')
@_role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def admin_reset_user_password(request, user_id):
    """
    // [Admin Security Action] Force-reset a teacher or student account password.
    // Generates a random 10-char temporary password and sets it immediately.
    // Returns JSON {temp_password: '...'} for the admin to relay to the user.
    // Emits ADMIN_PASSWORD_RESET to AuditEvent.
    """
    from apps.core.models import AuditEvent

    target_user = None
    try:
        target_user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)

    # Only allow resetting teachers and students (not other admins)
    profile = getattr(target_user, 'classstamp_profile', None)
    if profile is None or profile.role == Profile.ROLE_ADMIN:
        return JsonResponse({'error': 'Cannot reset password for this account type.'}, status=403)

    # Generate secure 10-char alphanumeric temp password
    alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(10))

    target_user.set_password(temp_password)
    target_user.save(update_fields=['password'])

    AuditEvent.objects.create(
        actor=request.user,
        action='ADMIN_PASSWORD_RESET',
        object_type='User',
        object_id=str(target_user.pk),
        reason=f'Admin forced password reset for {target_user.username} ({profile.role})',
    )

    return JsonResponse({
        'temp_password': temp_password,
        'username': target_user.username,
        'full_name': target_user.get_full_name() or target_user.username,
    })


# // ==============================================================================
# // TWO-FACTOR AUTHENTICATION (ADMIN / REGISTRAR)
# // ==============================================================================
# // The password is factor one. For a privileged account with TOTP enrolled, the
# // login view parks the identity in the session and sends the browser here;
# // no authenticated session exists until the code is also accepted.
PENDING_2FA_USER_KEY = 'pending_2fa_user_id'
PENDING_2FA_AT_KEY = 'pending_2fa_at'
PENDING_2FA_ATTEMPTS_KEY = 'pending_2fa_attempts'
PENDING_2FA_SECRET_KEY = 'pending_2fa_secret'
PENDING_2FA_TTL_SECONDS = 300
MAX_2FA_ATTEMPTS = 5


def _clear_pending_2fa(request):
    """Drop every trace of an unfinished second-factor challenge."""
    for key in (
        PENDING_2FA_USER_KEY,
        PENDING_2FA_AT_KEY,
        PENDING_2FA_ATTEMPTS_KEY,
        PENDING_2FA_SECRET_KEY,
    ):
        request.session.pop(key, None)


# // ==============================================================================
# // SELF-SERVICE PASSWORD RESET
# // ==============================================================================
PASSWORD_RESET_MAX_PER_WINDOW = 5
PASSWORD_RESET_WINDOW_SECONDS = 900


def _reset_request_throttled(request) -> bool:
    """Fixed-window throttle per client address, to stop reset-mail floods."""
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    key = f'classstamp:pwreset:{ip}'
    try:
        hits = cache.incr(key)
    except ValueError:
        cache.add(key, 1, PASSWORD_RESET_WINDOW_SECONDS)
        hits = 1
    return hits > PASSWORD_RESET_MAX_PER_WINDOW


@require_http_methods(['GET', 'POST'])
def password_reset_request(request):
    """
    // [Public] Ask for a reset link.
    // The response is identical whether or not the account exists — the reset flow
    // must not become a directory of who studies here.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        if _reset_request_throttled(request):
            messages.error(request, 'Too many reset requests. Please wait a few minutes.')
            return render(request, 'auth/password_reset_request.html')

        identifier = request.POST.get('identifier', '').strip()
        request_reset(identifier, request)
        return render(request, 'auth/password_reset_request.html', {'submitted': True})

    return render(request, 'auth/password_reset_request.html')


@require_http_methods(['GET', 'POST'])
def password_reset_confirm(request, token):
    """[Public] Set a new password using the emailed token."""
    user = read_reset_token(token)
    if user is None:
        messages.error(request, 'This reset link is invalid or has expired. Request a new one.')
        return redirect('password_reset_request')

    context = {'token': token, 'account': user.get_username()}

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        if new_password != confirm_password:
            messages.error(request, 'The two passwords do not match.')
            return render(request, 'auth/password_reset_confirm.html', context)
        try:
            reset_password(token, new_password)
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, 'auth/password_reset_confirm.html', context)

        messages.success(request, 'Password updated. Sign in with your new password.')
        return redirect('login')

    return render(request, 'auth/password_reset_confirm.html', context)


@require_http_methods(['GET', 'POST'])
def two_factor_verify(request):
    """
    // [Login Step 2] Authenticator challenge presented after a correct password.
    // The challenge window is short (5 minutes) and the attempt budget is
    // separate from the password lockout, so guessing codes cannot extend a
    // hijacked session indefinitely.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    user_id = request.session.get(PENDING_2FA_USER_KEY)
    issued_at = request.session.get(PENDING_2FA_AT_KEY) or 0
    if not user_id or (timezone.now().timestamp() - issued_at) > PENDING_2FA_TTL_SECONDS:
        _clear_pending_2fa(request)
        messages.error(request, 'Your verification window expired. Please sign in again.')
        return redirect('login')

    profile = Profile.objects.filter(user_id=user_id).select_related('user').first()
    if profile is None or not two_factor_required(profile):
        _clear_pending_2fa(request)
        return redirect('login')

    if request.method == 'GET':
        return render(request, 'auth/two_factor_verify.html')

    attempts = (request.session.get(PENDING_2FA_ATTEMPTS_KEY) or 0) + 1
    request.session[PENDING_2FA_ATTEMPTS_KEY] = attempts

    if attempts > MAX_2FA_ATTEMPTS:
        AuditEvent.objects.create(
            actor=profile.user,
            action='TWO_FACTOR_LOCKED',
            object_type='Profile',
            object_id=str(profile.pk),
            reason='Too many incorrect authenticator codes',
        )
        _clear_pending_2fa(request)
        messages.error(request, 'Too many incorrect codes. Please sign in again.')
        return redirect('login')

    # A recovery code is accepted here too — a lost phone must not lock an
    # administrator out of their own institution.
    outcome = verify_second_factor(profile, request.POST.get('code', ''))

    if not outcome['ok']:
        AuditEvent.objects.create(
            actor=profile.user,
            action='TWO_FACTOR_FAILED',
            object_type='Profile',
            object_id=str(profile.pk),
            reason=f'Incorrect authenticator code (attempt {attempts})',
        )
        messages.error(
            request,
            f'Invalid or expired code. {MAX_2FA_ATTEMPTS - attempts} attempt(s) left.',
        )
        return render(request, 'auth/two_factor_verify.html')

    _clear_pending_2fa(request)
    _reset_lock_state(request, profile.user.username)
    login(request, profile.user, backend='django.contrib.auth.backends.ModelBackend')
    request.session.cycle_key()
    AuditEvent.objects.create(
        actor=profile.user,
        action='TWO_FACTOR_SUCCESS',
        object_type='Profile',
        object_id=str(profile.pk),
        reason=(
            'Signed in with a recovery code'
            if outcome['method'] == 'RECOVERY'
            else 'Signed in with password and authenticator code'
        ),
    )
    if outcome['method'] == 'RECOVERY':
        messages.warning(
            request,
            f'Recovery code accepted — {outcome["remaining"]} remaining. '
            f'Generate a fresh set from Account Security when you can.',
        )
    return redirect('dashboard')


@login_required(login_url='login')
@_role_required(Profile.ROLE_ADMIN)
@require_http_methods(['GET', 'POST'])
def two_factor_setup(request):
    """
    // [Enrollment] Pairs an authenticator app with a privileged account.
    // GET  -> render the QR + manual key for a not-yet-saved seed
    // POST action=enable  -> confirm the first code, then persist the seed
    // POST action=disable -> remove the factor (requires a current code)
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    if profile is None or not is_privileged(profile):
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'disable':
            if not verify_code(profile, request.POST.get('code', '')):
                messages.error(
                    request,
                    'Enter a valid authenticator code before disabling two-factor authentication.',
                )
                return redirect('two_factor_setup')

            profile.totp_enabled = False
            profile.totp_secret = ''
            profile.totp_confirmed_at = None
            profile.save(update_fields=['totp_enabled', 'totp_secret', 'totp_confirmed_at'])
            # Retire the backup codes with the factor: they are a second door to
            # the same account and must not outlive it.
            reset_two_factor(profile)
            AuditEvent.objects.create(
                actor=request.user,
                action='TWO_FACTOR_DISABLED',
                object_type='Profile',
                object_id=str(profile.pk),
                reason='Second factor removed by the account holder',
            )
            messages.success(request, 'Two-factor authentication has been disabled.')
            return redirect('two_factor_setup')

        pending_secret = request.session.get(PENDING_2FA_SECRET_KEY, '')
        if not pending_secret or not verify_code_for_secret(pending_secret, request.POST.get('code', '')):
            messages.error(
                request,
                'That code did not match. Scan the QR again and enter the current 6-digit code.',
            )
            return redirect('two_factor_setup')

        profile.totp_secret = pending_secret
        profile.totp_enabled = True
        profile.totp_confirmed_at = timezone.now()
        profile.save(update_fields=['totp_secret', 'totp_enabled', 'totp_confirmed_at'])
        request.session.pop(PENDING_2FA_SECRET_KEY, None)

        # Shown once, on the next page load, then dropped from the session.
        # The plaintext never touches the database.
        request.session['new_recovery_codes'] = generate_recovery_codes(profile)
        AuditEvent.objects.create(
            actor=request.user,
            action='TWO_FACTOR_ENABLED',
            object_type='Profile',
            object_id=str(profile.pk),
            reason='Authenticator app paired successfully',
        )
        messages.success(request, 'Two-factor authentication is now active for this account.')
        return redirect('two_factor_setup')

    context = {'profile': profile, 'enabled': profile.totp_enabled}

    if profile.totp_enabled:
        context['recovery_remaining'] = remaining_recovery_codes(profile)

    # One-shot display of freshly generated backup codes.
    new_codes = request.session.pop('new_recovery_codes', None)
    if new_codes:
        context['new_recovery_codes'] = new_codes

    if not profile.totp_enabled:
        secret = request.session.get(PENDING_2FA_SECRET_KEY)
        if not secret:
            secret = new_secret()
            request.session[PENDING_2FA_SECRET_KEY] = secret
        uri = provisioning_uri(profile, secret)
        context.update({
            'secret': secret,
            'otpauth_uri': uri,
            'qr_data_uri': qr_data_uri(uri),
        })

    return render(request, 'auth/two_factor_setup.html', context)
