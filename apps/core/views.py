from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


def _reset_lock_state(request):
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


from .models import Department, Profile, Program


def _validate_registration_data(data):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not username:
        errors['username'] = 'Username is required.'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    # Student-specific validations
    student_number = data.get('student_number', '').strip()
    if not student_number:
        errors['student_number'] = 'Student ID number is required.'
    elif Profile.objects.filter(student_number=student_number).exists():
        errors['student_number'] = 'This Student ID number is already registered.'

    program_id = data.get('program_id')
    if not program_id:
        errors['program_id'] = 'Please select your College Program.'
    elif not Program.objects.filter(pk=program_id, is_active=True).exists():
        errors['program_id'] = 'Selected program is invalid.'

    year_level = data.get('year_level')
    if not year_level:
        errors['year_level'] = 'Please select your Year Level.'
    else:
        try:
            y = int(year_level)
            if y < 1 or y > 5:
                errors['year_level'] = 'Invalid year level.'
        except (ValueError, TypeError):
            errors['year_level'] = 'Invalid year level.'

    return errors


@require_http_methods(['GET', 'POST'])
def login_view(request):
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

    # Flexible login lookup: by username, email, or student ID number
    user_obj = None
    if '@' in login_input:
        user_obj = User.objects.filter(email__iexact=login_input).first()
    else:
        user_obj = User.objects.filter(username__iexact=login_input).first()
        if not user_obj:
            student_profile = Profile.objects.filter(student_number__iexact=login_input).select_related('user').first()
            if student_profile:
                user_obj = student_profile.user

    user = None
    if user_obj:
        user = authenticate(request, username=user_obj.username, password=password)

    if user is not None:
        # Check approval status for students and teachers
        profile = getattr(user, 'classstamp_profile', None)
        if profile and profile.role != Profile.ROLE_ADMIN and not user.is_superuser:
            if profile.approval_status == Profile.APPROVAL_PENDING:
                messages.warning(
                    request,
                    'Your account registration is currently PENDING Admin validation. Please wait for approval before signing in.'
                )
                return render(request, 'auth/login.html')
            elif profile.approval_status == Profile.APPROVAL_REJECTED:
                reason = f" Reason: {profile.approval_note}" if profile.approval_note else ""
                messages.error(
                    request,
                    f'Your account registration was rejected by the Admin.{reason}'
                )
                return render(request, 'auth/login.html')

        _reset_lock_state(request)
        login(request, user)
        return redirect('dashboard')

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def home(request):
    return render(request, 'home.html')


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = Program.objects.filter(is_active=True).select_related('department').order_by('name')

    if request.method == 'GET':
        return render(request, 'auth/register.html', {
            'departments': departments,
            'programs': programs,
        })

    form_data = {
        'username': request.POST.get('username', '').strip(),
        'first_name': request.POST.get('first_name', '').strip(),
        'last_name': request.POST.get('last_name', '').strip(),
        'email': request.POST.get('email', '').strip(),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
        'student_number': request.POST.get('student_number', '').strip(),
        'department_id': request.POST.get('department_id', '').strip(),
        'program_id': request.POST.get('program_id', '').strip(),
        'year_level': request.POST.get('year_level', '').strip(),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {
            'errors': errors,
            'form_data': form_data,
            'departments': departments,
            'programs': programs,
        })

    user = User.objects.create_user(
        username=form_data['username'],
        first_name=form_data['first_name'],
        last_name=form_data['last_name'],
        email=form_data['email'],
        password=form_data['password'],
    )

    program = Program.objects.get(pk=form_data['program_id'])
    Profile.objects.create(
        user=user,
        role=Profile.ROLE_STUDENT,
        student_number=form_data['student_number'],
        program=program,
        department=program.department,
        year_level=int(form_data['year_level']),
        approval_status=Profile.APPROVAL_PENDING,
    )

    messages.success(
        request,
        'Registration submitted successfully! Your account is now pending Admin approval. You can sign in once validated.'
    )
    return redirect('login')


