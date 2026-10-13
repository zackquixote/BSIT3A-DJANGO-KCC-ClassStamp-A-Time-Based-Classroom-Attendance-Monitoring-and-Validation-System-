"""
// ==============================================================================
// KCC CLASSSTAMP - CORE APPLICATION VIEWS & CONTROLLERS
// ==============================================================================
// Description: Primary controller layer handling session authentication,
// brute-force attack mitigation, multi-role dispatching (Admin, Teacher, Student),
// student self-registration workflow, and administrative account validation queue.
// References: docs/02_SECURITY.md | docs/01_DEV_PLAN.md
// ==============================================================================
"""

import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .decorators import approved_required, role_required
from .models import (
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    Department,
    Enrollment,
    Profile,
    Program,
)

User = get_user_model()


# // ==============================================================================
# // SECTION 1: AUTHENTICATION CONSTANTS & RATE-LIMITING LOCKOUT CONFIGURATION
# // ==============================================================================
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


# // ==============================================================================
# // HELPER: Reset rate-limiting session parameters
# // ==============================================================================
def _reset_lock_state(request):
    """
    // Clears failed attempt counters and active unlock timestamps from the user session.
    """
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


# // ==============================================================================
# // HELPER: Evaluate current rate-limiting lock state
# // ==============================================================================
def _get_lock_state(request):
    """
    // Inspects session metadata to determine if the client is actively throttled.
    // Returns: (failed_attempts: int, remaining_seconds: int | None)
    """
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        # // Corrupted timestamp format fallback
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    # // Lockout duration has expired; restore clean state
    _reset_lock_state(request)
    return 0, None


# // ==============================================================================
# // HELPER: Trigger rate-limiting lockout
# // ==============================================================================
def _set_lock_state(request):
    """
    // Activates temporary lockout window for the client session upon threshold breach.
    """
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


# // ==============================================================================
# // HELPER: Validate Student Registration Payload
# // ==============================================================================
def _validate_registration_data(data):
    """
    // [Input Sanitization & Server-Side Validation]
    // Verifies form data against user uniqueness, email syntax, password complexity,
    // and academic constraints (program length vs requested standing year).
    """
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    # // 1. User Identity Fields
    if not username:
        errors['username'] = 'Username is required.'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    # // 2. Email Validation
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

    # // 3. Password Security & Confirmation
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

    # // 4. Student Academic Credentials
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
            # // [Database Trigger Compliance]
            # // Upper bound must respect the chosen program's total years, otherwise
            # // the BEFORE INSERT trigger `trg_cs_profile_bi` will reject the transaction.
            max_years = 5
            if program_id and not errors.get('program_id'):
                selected_program = Program.objects.filter(
                    pk=program_id, is_active=True
                ).first()
                if selected_program:
                    max_years = selected_program.years_total
            if y < 1 or y > max_years:
                errors['year_level'] = (
                    f'Year level must be between 1 and {max_years} for the selected program.'
                )
        except (ValueError, TypeError):
            errors['year_level'] = 'Invalid year level.'

    return errors


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
    // Terminates current user session and clears authentication cookies.
    """
    logout(request)
    return redirect('login')


# // ==============================================================================
# // VIEW: Smart Role-Aware Dashboard Dispatcher (/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
def dashboard_redirect(request):
    """
    // [RBAC Dispatcher] Evaluates the authenticated user's role and issues
    // a permanent redirect to the corresponding role-specific dashboard URL:
    // - ADMIN / Superuser -> /admin/dashboard/
    // - TEACHER           -> /teacher/dashboard/
    // - STUDENT           -> /student/dashboard/
    // Fallback renders home.html for accounts with no assigned profile.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    role = profile.role if profile else None

    # // [Superuser Escalation] Superusers without an explicit profile get admin portal
    if role is None and request.user.is_superuser:
        role = Profile.ROLE_ADMIN

    # // [Role Routing] Render dedicated role portal
    if role == Profile.ROLE_ADMIN:
        return admin_dashboard(request)
    if role == Profile.ROLE_TEACHER:
        return teacher_dashboard(request)
    if role == Profile.ROLE_STUDENT:
        if profile.approval_status == Profile.APPROVAL_APPROVED:
            return student_dashboard(request)
        return render(request, 'home.html')

    # // Fallback for bare accounts with no role
    return render(request, 'home.html')


# // ==============================================================================
# // VIEW: Admin Dashboard Portal (/admin/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_dashboard(request):
    """
    // [Admin Portal] Renders admin overview with institutional metrics.
    """
    return render(request, 'core/admin/dashboard.html', _admin_dashboard_stats())


# // ==============================================================================
# // VIEW: Teacher Dashboard Portal (/teacher/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_TEACHER)
def teacher_dashboard(request):
    """
    // [Teacher Portal] Renders teacher's class list and active session summary.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    return render(request, 'core/teacher/dashboard.html', _teacher_dashboard_stats(profile))


# // ==============================================================================
# // VIEW: Student Dashboard Portal (/student/dashboard/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_STUDENT)
@approved_required
def student_dashboard(request):
    """
    // [Student Portal] Renders student's personal attendance summary.
    // Guarded by approved_required to prevent PENDING/REJECTED students from viewing.
    """
    profile = getattr(request.user, 'classstamp_profile', None)
    return render(request, 'core/student/dashboard.html', _student_dashboard_stats(profile))


# // ==============================================================================
# // HELPER: Admin Dashboard Statistical Aggregation
# // ==============================================================================
def _admin_dashboard_stats():
    """
    // Computes institutional metrics for display on the admin overview interface.
    """
    return {
        'pending_count': Profile.objects.filter(
            role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_PENDING,
        ).count(),
        'student_count': Profile.objects.filter(
            role=Profile.ROLE_STUDENT, approval_status=Profile.APPROVAL_APPROVED,
        ).count(),
        'teacher_count': Profile.objects.filter(
            role=Profile.ROLE_TEACHER, approval_status=Profile.APPROVAL_APPROVED,
        ).count(),
        'open_session_count': ClassSession.objects.filter(status=ClassSession.STATUS_OPEN).count(),
        'department_count': Department.objects.count(),
        'program_count': Program.objects.count(),
    }


# // ==============================================================================
# // HELPER: Teacher Dashboard Metrics & Class Retrieval
# // ==============================================================================
def _teacher_dashboard_stats(profile):
    """
    // Queries classes assigned to the requesting teacher and identifies active sessions.
    """
    classes = (
        Class.objects.filter(teacher_profile=profile, is_active=True)
        .select_related('subject', 'academic_year')
        .order_by('class_code')
    )
    return {
        'classes': classes,
        'class_count': classes.count(),
        'open_session_count': ClassSession.objects.filter(
            slot__class_obj__teacher_profile=profile,
            status=ClassSession.STATUS_OPEN,
        ).count(),
    }


# // ==============================================================================
# // HELPER: Student Dashboard Attendance Metrics
# // ==============================================================================
def _student_dashboard_stats(profile):
    """
    // Summarizes attendance statuses and active enrollments for the student.
    """
    records = AttendanceRecord.objects.filter(student_profile=profile)
    return {
        'present_count': records.filter(status=AttendanceRecord.STATUS_PRESENT).count(),
        'late_count': records.filter(status=AttendanceRecord.STATUS_LATE).count(),
        'absent_count': records.filter(status=AttendanceRecord.STATUS_ABSENT).count(),
        'excused_count': records.filter(status=AttendanceRecord.STATUS_EXCUSED).count(),
        'enrolled_class_count': Enrollment.objects.filter(
            student_profile=profile, status=Enrollment.STATUS_ACTIVE,
        ).count(),
    }


# // ==============================================================================
# // VIEW: Student Self-Registration Controller
# // ==============================================================================
@require_http_methods(['GET', 'POST'])
def register_view(request):
    """
    // [Registration Controller]
    // Handles public student registration:
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

    # // Create User Authentication Record
    user = User.objects.create_user(
        username=form_data['username'],
        first_name=form_data['first_name'],
        last_name=form_data['last_name'],
        email=form_data['email'],
        password=form_data['password'],
    )

    # // Create Bound Student Profile
    program = Program.objects.get(pk=form_data['program_id'])
    proof_file = request.FILES.get('registration_proof')

    Profile.objects.create(
        user=user,
        role=Profile.ROLE_STUDENT,
        student_number=form_data['student_number'],
        registration_proof=proof_file,
        program=program,
        year_level=int(form_data['year_level']),
        approval_status=Profile.APPROVAL_PENDING,
        # // Database constraint `chk_cs_profile_shape` requires department_id = NULL for STUDENT.
        # // Requires a 64-character hex secret initialized at registration time.
        qr_secret=secrets.token_hex(32),
    )

    messages.success(
        request,
        'Registration submitted successfully! Your account is now pending Admin approval. '
        'You can sign in once validated.'
    )
    return redirect('login')


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
# // SECTION 2: ADMINISTRATOR ACCOUNT VALIDATION WORKFLOW
# // ==============================================================================

@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def validation_queue(request):
    """
    // [Admin Controller] Student Validation Queue
    // Lists pending student registrations awaiting administrative identity verification.
    // Also exhibits the most recent 20 reviewed profiles for auditing transparency.
    // Supports multi-department filtering, program filtering, and instant search.
    """
    selected_dept = request.GET.get('department', '').strip()
    selected_prog = request.GET.get('program', '').strip()
    query = request.GET.get('q', '').strip()

    base_pending = Profile.objects.filter(
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )
    total_pending_count = base_pending.count()

    # Pre-calculate counts of pending students per department for quick tabs and filtering
    departments = Department.objects.filter(is_active=True).annotate(
        pending_count=Count(
            'programs__profiles',
            filter=Q(
                programs__profiles__role=Profile.ROLE_STUDENT,
                programs__profiles__approval_status=Profile.APPROVAL_PENDING,
            )
        )
    ).order_by('name')

    # Pre-calculate counts of pending students per program
    programs = Program.objects.filter(is_active=True).select_related('department').annotate(
        pending_count=Count(
            'profiles',
            filter=Q(
                profiles__role=Profile.ROLE_STUDENT,
                profiles__approval_status=Profile.APPROVAL_PENDING,
            )
        )
    ).order_by('name')

    pending = base_pending.select_related('user', 'program', 'program__department').order_by('created_at')

    # Apply backend filters if query parameters are provided
    if selected_dept:
        try:
            pending = pending.filter(program__department_id=int(selected_dept))
        except (ValueError, TypeError):
            selected_dept = ''

    if selected_prog:
        try:
            pending = pending.filter(program_id=int(selected_prog))
        except (ValueError, TypeError):
            selected_prog = ''

    if query:
        pending = pending.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query) |
            Q(student_number__icontains=query)
        )

    recently_reviewed = (
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status__in=[Profile.APPROVAL_APPROVED, Profile.APPROVAL_REJECTED],
        )
        .select_related('user', 'program', 'program__department', 'approved_by')
        .order_by('-approved_at')[:20]
    )

    return render(request, 'core/admin/validation_queue.html', {
        'pending': pending,
        'recently_reviewed': recently_reviewed,
        'pending_count': total_pending_count,
        'filtered_count': pending.count(),
        'departments': departments,
        'programs': programs,
        'selected_department': selected_dept,
        'selected_program': selected_prog,
        'query': query,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def validation_detail(request, student_number):
    """
    // [Admin Controller] Detailed Student Registration Review
    // Displays the full e-registration submission details for an individual student
    // so an administrator can verify credentials and decide whether to approve or reject.
    // Includes queue navigation (next/prev student) and duplicate detection.
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user', 'program', 'program__department', 'approved_by'),
        student_number=student_number,
        role=Profile.ROLE_STUDENT,
    )

    # Queue Navigation: Find next and previous pending students in queue
    pending_numbers = list(
        Profile.objects.filter(
            role=Profile.ROLE_STUDENT,
            approval_status=Profile.APPROVAL_PENDING,
        ).order_by('created_at').values_list('student_number', flat=True)
    )

    prev_number = None
    next_number = None
    current_index = None
    total_pending = len(pending_numbers)

    if profile.student_number in pending_numbers:
        idx = pending_numbers.index(profile.student_number)
        current_index = idx + 1
        if idx > 0:
            prev_number = pending_numbers[idx - 1]
        if idx < total_pending - 1:
            next_number = pending_numbers[idx + 1]

    # Duplicate Detection: Check for potential matching profiles by student number, name, or email
    duplicates = Profile.objects.filter(
        Q(student_number=profile.student_number) |
        (Q(user__first_name__iexact=profile.user.first_name) & Q(user__last_name__iexact=profile.user.last_name)) |
        Q(user__email__iexact=profile.user.email)
    ).exclude(pk=profile.pk).select_related('user', 'program', 'program__department')[:5]

    # Fetch audit events relating to this profile for full transparency
    audit_events = AuditEvent.objects.filter(
        object_type='Profile',
        object_id=str(profile.pk)
    ).select_related('actor').order_by('-created_at')

    return render(request, 'core/admin/validation_detail.html', {
        'student_profile': profile,
        'audit_events': audit_events,
        'prev_id': prev_number,
        'next_id': next_number,
        'current_index': current_index,
        'total_pending': total_pending,
        'duplicates': duplicates,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def approve_student(request, student_number):
    """
    // [Admin Action] Approve Student Registration
    //
    // Security & Trigger Specifications:
    // - Confirms the student's identity against school registrar records.
    // - Satisfies DB trigger `trg_cs_profile_bu`: sets approved_by and approved_at.
    // - Rotates and seals a new 64-character QR secret for dynamic attendance stamping.
    // - Records immutable APPROVE_STUDENT entry into AuditEvent.
    """
    profile = get_object_or_404(
        Profile,
        student_number=student_number,
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )

    profile.approval_status = Profile.APPROVAL_APPROVED
    profile.approved_by = request.user
    profile.approved_at = timezone.now()
    profile.approval_note = None

    # // [Cryptographic QR Seed Rotation]
    profile.qr_secret = secrets.token_hex(32)
    profile.qr_rotated_at = timezone.now()
    profile.save()

    # // [Immutable Audit Logging]
    AuditEvent.objects.create(
        actor=request.user,
        action='APPROVE_STUDENT',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'Approved {profile.student_number} ({profile.user.get_username()})',
    )

    messages.success(request, f'{profile.user.get_full_name() or profile.user.get_username()} has been approved.')
    next_url = request.POST.get('next')
    if next_url == 'detail':
        return redirect('validation_detail', student_number=profile.student_number)
    return redirect('validation_queue')


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def reject_student(request, student_number):
    """
    // [Admin Action] Reject Student Registration
    //
    // Security & Trigger Specifications:
    // - Mandates non-empty `approval_note` (reason) as required by database triggers.
    // - Records timestamps and administrative reviewer ID.
    // - Emits REJECT_STUDENT record to AuditEvent.
    """
    profile = get_object_or_404(
        Profile,
        student_number=student_number,
        role=Profile.ROLE_STUDENT,
        approval_status=Profile.APPROVAL_PENDING,
    )

    next_url = request.POST.get('next')
    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, 'A rejection reason is required.')
        if next_url == 'detail':
            return redirect('validation_detail', student_number=profile.student_number)
        return redirect('validation_queue')

    profile.approval_status = Profile.APPROVAL_REJECTED
    profile.approved_by = request.user
    profile.approved_at = timezone.now()
    profile.approval_note = reason
    profile.save()

    # // [Immutable Audit Logging]
    AuditEvent.objects.create(
        actor=request.user,
        action='REJECT_STUDENT',
        object_type='Profile',
        object_id=str(profile.pk),
        new_value=f'Rejected {profile.student_number} ({profile.user.get_username()})',
        reason=reason,
    )

    messages.success(request, f'{profile.user.get_full_name() or profile.user.get_username()} has been rejected.')
    if next_url == 'detail':
        return redirect('validation_detail', student_number=profile.student_number)
    return redirect('validation_queue')


# // ==============================================================================
# // SECTION 3: ACADEMIC ORGANISATION - DEPARTMENT MANAGEMENT (RBAC: ADMIN ONLY)
# // ==============================================================================

@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def department_list(request):
    """
    // [Admin Controller] Department Directory
    // Lists all college departments with program counts and active status.
    """
    query = request.GET.get('q', '').strip()
    departments_qs = (
        Department.objects.annotate(
            program_count=Count('programs', distinct=True),
            faculty_count=Count('profiles', distinct=True),
        )
        .order_by('name')
    )

    if query:
        departments_qs = departments_qs.filter(
            Q(code__icontains=query) | Q(name__icontains=query)
        )

    paginator = Paginator(departments_qs, 10)
    page_number = request.GET.get('page', 1)
    departments = paginator.get_page(page_number)

    total_count = Department.objects.count()
    active_count = Department.objects.filter(is_active=True).count()
    inactive_count = total_count - active_count

    return render(request, 'core/admin/departments.html', {
        'departments': departments,
        'query': query,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def department_save(request):
    """
    // [Admin Controller] Create or Update Academic Department
    // Handles validation for unique department code and name.
    """
    dept_id = request.POST.get('id', '').strip()
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    is_active = request.POST.get('is_active') in ['true', 'on', '1', True]

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if not code:
        err = 'Department code is required (e.g. CCS, CITCS).'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('department_list')

    if not name:
        err = 'Department name is required.'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('department_list')

    # Uniqueness check
    code_exists = Department.objects.filter(code__iexact=code)
    name_exists = Department.objects.filter(name__iexact=name)
    if dept_id:
        code_exists = code_exists.exclude(pk=dept_id)
        name_exists = name_exists.exclude(pk=dept_id)

    if code_exists.exists():
        err = f'Department code "{code}" is already in use.'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('department_list')

    if name_exists.exists():
        err = f'Department name "{name}" is already registered.'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('department_list')

    if dept_id:
        dept = get_object_or_404(Department, pk=dept_id)
        old_val = f'{dept.code} - {dept.name} (active: {dept.is_active})'
        dept.code = code
        dept.name = name
        dept.is_active = is_active
        dept.save()
        action = 'UPDATE_DEPARTMENT'
        msg = f'Department "{dept.code}" updated successfully.'
    else:
        dept = Department.objects.create(code=code, name=name, is_active=is_active)
        old_val = None
        action = 'CREATE_DEPARTMENT'
        msg = f'Department "{dept.code} — {dept.name}" created successfully.'

    AuditEvent.objects.create(
        actor=request.user,
        action=action,
        object_type='Department',
        object_id=str(dept.pk),
        old_value=old_val,
        new_value=f'{dept.code} - {dept.name} (active: {dept.is_active})',
    )

    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'message': msg,
            'department': {
                'id': dept.id,
                'code': dept.code,
                'name': dept.name,
                'is_active': dept.is_active,
            }
        })

    messages.success(request, msg)
    return redirect('department_list')


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def department_delete(request, pk):
    """
    // [Admin Controller] Delete or Deactivate Department
    // Safeguard: If programs or teachers are attached, soft-deactivate rather than hard-delete.
    """
    dept = get_object_or_404(Department, pk=pk)
    has_programs = dept.programs.exists()
    has_faculty = dept.profiles.exists()

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if has_programs or has_faculty:
        dept.is_active = False
        dept.save()
        AuditEvent.objects.create(
            actor=request.user,
            action='DEACTIVATE_DEPARTMENT',
            object_type='Department',
            object_id=str(dept.pk),
            new_value='is_active=False',
            reason='Protected deactivation due to existing child associations',
        )
        msg = f'Department "{dept.code}" was deactivated (attached to {dept.programs.count()} programs and {dept.profiles.count()} faculty).'
        status_type = 'deactivated'
    else:
        code = dept.code
        dept_id_str = str(dept.pk)
        dept.delete()
        AuditEvent.objects.create(
            actor=request.user,
            action='DELETE_DEPARTMENT',
            object_type='Department',
            object_id=dept_id_str,
            old_value=f'{code}',
        )
        msg = f'Department "{code}" was permanently deleted.'
        status_type = 'deleted'

    if is_ajax:
        return JsonResponse({'status': 'success', 'message': msg, 'type': status_type})

    messages.success(request, msg)
    return redirect('department_list')


# // ==============================================================================
# // SECTION 4: ACADEMIC ORGANISATION - PROGRAM MANAGEMENT (RBAC: ADMIN ONLY)
# // ==============================================================================

@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def program_list(request):
    """
    // [Admin Controller] Degree Program Directory
    // Lists all college programs with parent department, duration, and student count.
    """
    query = request.GET.get('q', '').strip()
    dept_filter = request.GET.get('department', '').strip()

    programs_qs = (
        Program.objects.select_related('department')
        .annotate(
            student_count=Count('profiles', distinct=True),
        )
        .order_by('department__name', 'code')
    )

    if query:
        programs_qs = programs_qs.filter(
            Q(code__icontains=query) |
            Q(name__icontains=query) |
            Q(department__name__icontains=query) |
            Q(department__code__icontains=query)
        )

    if dept_filter:
        programs_qs = programs_qs.filter(department_id=dept_filter)

    paginator = Paginator(programs_qs, 10)
    page_number = request.GET.get('page', 1)
    programs = paginator.get_page(page_number)

    departments = Department.objects.filter(is_active=True).order_by('name')
    total_count = Program.objects.count()
    active_count = Program.objects.filter(is_active=True).count()

    return render(request, 'core/admin/programs.html', {
        'programs': programs,
        'departments': departments,
        'query': query,
        'dept_filter': dept_filter,
        'total_count': total_count,
        'active_count': active_count,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def program_save(request):
    """
    // [Admin Controller] Create or Update Academic Program
    """
    prog_id = request.POST.get('id', '').strip()
    dept_id = request.POST.get('department_id', '').strip()
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    years_total = request.POST.get('years_total', '4').strip()
    is_active = request.POST.get('is_active') in ['true', 'on', '1', True]

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if not dept_id:
        err = 'Please select a parent department.'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('program_list')

    dept = get_object_or_404(Department, pk=dept_id)

    if not code:
        err = 'Program code is required (e.g. BSIT, BSCS).'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('program_list')

    if not name:
        err = 'Program descriptive name is required.'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('program_list')

    try:
        years = int(years_total)
        if years < 1 or years > 8:
            raise ValueError()
    except ValueError:
        err = 'Program duration must be between 1 and 8 years.'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('program_list')

    code_exists = Program.objects.filter(code__iexact=code)
    if prog_id:
        code_exists = code_exists.exclude(pk=prog_id)

    if code_exists.exists():
        err = f'Program code "{code}" already exists.'
        if is_ajax: return JsonResponse({'error': err}, status=400)
        messages.error(request, err); return redirect('program_list')

    if prog_id:
        prog = get_object_or_404(Program, pk=prog_id)
        old_val = f'{prog.code} - {prog.name} (dept={prog.department.code}, yrs={prog.years_total}, active={prog.is_active})'
        prog.department = dept
        prog.code = code
        prog.name = name
        prog.years_total = years
        prog.is_active = is_active
        prog.save()
        action = 'UPDATE_PROGRAM'
        msg = f'Program "{prog.code}" updated successfully.'
    else:
        prog = Program.objects.create(
            department=dept,
            code=code,
            name=name,
            years_total=years,
            is_active=is_active,
        )
        old_val = None
        action = 'CREATE_PROGRAM'
        msg = f'Program "{prog.code} — {prog.name}" created under {dept.code} successfully.'

    AuditEvent.objects.create(
        actor=request.user,
        action=action,
        object_type='Program',
        object_id=str(prog.pk),
        old_value=old_val,
        new_value=f'{prog.code} - {prog.name} (dept={dept.code}, yrs={prog.years_total}, active={prog.is_active})',
    )

    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'message': msg,
            'program': {
                'id': prog.id,
                'code': prog.code,
                'name': prog.name,
                'department_id': dept.id,
                'department_code': dept.code,
                'years_total': prog.years_total,
                'is_active': prog.is_active,
            }
        })

    messages.success(request, msg)
    return redirect('program_list')


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def program_delete(request, pk):
    """
    // [Admin Controller] Delete or Deactivate Degree Program
    // Safeguard: If student profiles exist under program, soft-deactivate to prevent FK collision.
    """
    prog = get_object_or_404(Program, pk=pk)
    has_students = prog.profiles.exists()
    has_curriculum = prog.curriculum_entries.exists()

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if has_students or has_curriculum:
        prog.is_active = False
        prog.save()
        AuditEvent.objects.create(
            actor=request.user,
            action='DEACTIVATE_PROGRAM',
            object_type='Program',
            object_id=str(prog.pk),
            new_value='is_active=False',
            reason='Protected deactivation due to existing student enrollments or curriculum bindings',
        )
        msg = f'Program "{prog.code}" was deactivated (attached to {prog.profiles.count()} students or curriculum entries).'
        status_type = 'deactivated'
    else:
        code = prog.code
        prog_id_str = str(prog.pk)
        prog.delete()
        AuditEvent.objects.create(
            actor=request.user,
            action='DELETE_PROGRAM',
            object_type='Program',
            object_id=prog_id_str,
            old_value=code,
        )
        msg = f'Program "{code}" was permanently deleted.'
        status_type = 'deleted'

    if is_ajax:
        return JsonResponse({'status': 'success', 'message': msg, 'type': status_type})

    messages.success(request, msg)
    return redirect('program_list')

