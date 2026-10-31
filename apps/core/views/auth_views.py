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
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.core.models import AuditEvent, Department, Profile, Program
from apps.core.services import provision_student_account
from apps.core.services.two_factor_service import (
    is_privileged,
    new_secret,
    provisioning_uri,
    qr_data_uri,
    two_factor_required,
    verify_code,
    verify_code_for_secret,
)
from apps.core.views.helpers import (
    INVALID_LOGIN_MESSAGE,
    LOCK_DURATION,
    LOCKED_MESSAGE,
    MAX_FAILED_ATTEMPTS,
    _get_lock_state,
    _reset_lock_state,
    _set_lock_state,
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

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    login_input = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')

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
        _reset_lock_state(request)
        login(request, user)
        request.session.cycle_key()
        return redirect('dashboard')

    # // [Failure Route] Increment failure counter and apply lockout if threshold reached
    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


# // ==============================================================================
# // VIEW: Logout Controller
# // ==============================================================================
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

    if not verify_code(profile, request.POST.get('code', '')):
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
    _reset_lock_state(request)
    login(request, profile.user, backend='django.contrib.auth.backends.ModelBackend')
    request.session.cycle_key()
    AuditEvent.objects.create(
        actor=profile.user,
        action='TWO_FACTOR_SUCCESS',
        object_type='Profile',
        object_id=str(profile.pk),
        reason='Signed in with password and authenticator code',
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

