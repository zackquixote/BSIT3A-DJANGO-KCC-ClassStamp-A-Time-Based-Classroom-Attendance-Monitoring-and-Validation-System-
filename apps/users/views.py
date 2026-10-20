"""
// ==============================================================================
// KCC CLASSSTAMP - USER MANAGEMENT CONTROLLER (RBAC: ADMIN ONLY)
// ==============================================================================
// Description: Administrative user management subsystem for creating, reviewing,
// updating, and revoking user accounts. Enforces strict role-based access control
// restricted to institutional administrators (Profile.ROLE_ADMIN) and superusers.
// References: docs/02_SECURITY.md | apps/core/decorators.py
// ==============================================================================
"""

import csv
import secrets
import string

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import role_required
from apps.core.models import AuditEvent, Department, Profile, Program


# // ==============================================================================
# // VIEW: User Management Page (Renders administrative user directory)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def user_list_page(request):
    """
    // [Admin Controller] User Management Directory View
    // Renders grouped lists of system accounts by role (Students / Teachers / Admins).
    // Supports multi-attribute search, status filters, and role-specific academic affiliations.
    """
    query = request.GET.get('q', '').strip()
    role_tab = request.GET.get('role', 'students').strip()  # 'students', 'teachers', 'admins'
    status_filter = request.GET.get('status', '').strip()   # 'active', 'inactive'
    dept_filter = request.GET.get('department', '').strip()
    prog_filter = request.GET.get('program', '').strip()
    year_filter = request.GET.get('year_level', '').strip()

    # System-wide KPIs for header cards
    total_users_count = User.objects.count()
    total_students_count = Profile.objects.filter(role=Profile.ROLE_STUDENT).count()
    total_teachers_count = Profile.objects.filter(role=Profile.ROLE_TEACHER).count()
    total_admins_count = User.objects.filter(
        Q(classstamp_profile__role=Profile.ROLE_ADMIN) | Q(is_superuser=True)
    ).distinct().count()
    total_inactive_count = User.objects.filter(is_active=False).count()

    # // [Query Optimization] select_related avoids N+1 queries for user profiles
    base_qs = User.objects.all().select_related(
        'classstamp_profile',
        'classstamp_profile__program',
        'classstamp_profile__department'
    ).order_by('-date_joined')

    # // [Search Filter] Matches username, student ID, first name, last name, or email address
    if query:
        base_qs = base_qs.filter(
            Q(username__icontains=query) |
            Q(classstamp_profile__student_number__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    # Status filter
    if status_filter == 'active':
        base_qs = base_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        base_qs = base_qs.filter(is_active=False)

    # Department filter (teachers / students)
    if dept_filter:
        base_qs = base_qs.filter(classstamp_profile__department_id=dept_filter)

    # Program filter (students)
    if prog_filter:
        base_qs = base_qs.filter(classstamp_profile__program_id=prog_filter)

    # Year level filter (students)
    if year_filter and year_filter.isdigit():
        base_qs = base_qs.filter(classstamp_profile__year_level=int(year_filter))

    # Split into role groups
    students_qs = base_qs.filter(classstamp_profile__role=Profile.ROLE_STUDENT)
    teachers_qs = base_qs.filter(classstamp_profile__role=Profile.ROLE_TEACHER).annotate(
        taught_count=Count('classstamp_profile__taught_classes', distinct=True)
    )
    # Admins = profile ADMIN role OR superuser/staff
    admins_qs = base_qs.filter(
        Q(classstamp_profile__role=Profile.ROLE_ADMIN) | Q(is_superuser=True)
    ).distinct()

    # Counts for active search/filters
    tab_students_count = students_qs.count()
    tab_teachers_count = teachers_qs.count()
    tab_admins_count = admins_qs.count()

    # Paginate the active tab — honour user-chosen page size (15/25/50/100)
    try:
        per_page = int(request.GET.get('per_page', 25))
    except (ValueError, TypeError):
        per_page = 25
    per_page = per_page if per_page in (15, 25, 50, 100) else 25

    if role_tab == 'teachers':
        paginator = Paginator(teachers_qs, per_page)
    elif role_tab == 'admins':
        paginator = Paginator(admins_qs, per_page)
    else:
        role_tab = 'students'
        paginator = Paginator(students_qs, per_page)

    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)

    departments = Department.objects.filter(is_active=True).order_by('name')
    programs = Program.objects.filter(is_active=True).order_by('name')

    return render(request, 'users/list.html', {
        'users': users,
        'query': query,
        'role_tab': role_tab,
        'status_filter': status_filter,
        'dept_filter': dept_filter,
        'prog_filter': prog_filter,
        'year_filter': year_filter,
        'per_page': per_page,
        'students_count': tab_students_count,
        'teachers_count': tab_teachers_count,
        'admins_count': tab_admins_count,
        'total_users_count': total_users_count,
        'total_students_count': total_students_count,
        'total_teachers_count': total_teachers_count,
        'total_admins_count': total_admins_count,
        'total_inactive_count': total_inactive_count,
        'departments': departments,
        'programs': programs,
    })


# // ==============================================================================
# // API / AJAX: User List Endpoint (JSON format for asynchronous tables)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def user_list_ajax(request):
    """
    // [AJAX Endpoint] Paginated user record retrieval for asynchronous client grids.
    // Serializes account states and maps Profile role metadata.
    """
    users_list = User.objects.all().select_related(
        'classstamp_profile',
        'classstamp_profile__program',
        'classstamp_profile__department'
    ).order_by('-date_joined')
    paginator = Paginator(users_list, 10)
    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)

    data = []
    for u in users.object_list:
        profile = getattr(u, 'classstamp_profile', None)
        role_label = profile.role if profile else ('SUPERUSER' if u.is_superuser else 'NONE')
        identifier = profile.student_number if (profile and profile.student_number) else u.username
        data.append({
            'id': u.id,
            'username': u.username,
            'identifier': identifier,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'email': u.email,
            'is_staff': u.is_staff,
            'is_active': u.is_active,
            'is_superuser': u.is_superuser,
            'role': role_label,
            'date_joined': u.date_joined.strftime('%b %d, %Y') if u.date_joined else '',
        })

    return JsonResponse({
        "data": data,
        "has_next": users.has_next(),
        "has_prev": users.has_previous(),
        "page": users.number,
        "pages": users.paginator.num_pages,
        "total": users.paginator.count,
    })


# // ==============================================================================
# // API / AJAX: Single User Inspection Endpoint
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def user_get_ajax(request, pk):
    """
    // [AJAX Endpoint] Fetches account details for populating the administrative edit modal.
    """
    user = get_object_or_404(
        User.objects.select_related('classstamp_profile', 'classstamp_profile__program', 'classstamp_profile__department'),
        pk=pk
    )
    profile = getattr(user, 'classstamp_profile', None)
    role_label = profile.role if profile else ('ADMIN' if user.is_superuser or user.is_staff else 'STUDENT')
    identifier = profile.student_number if (profile and profile.student_number) else user.username

    return JsonResponse({
        "id": user.id,
        "username": user.username,
        "identifier": identifier,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "role": role_label,
        "program_id": profile.program_id if profile else None,
        "department_id": profile.department_id if profile else None,
        "year_level": profile.year_level if profile else None,
    })


# // ==============================================================================
# // API / AJAX: User Mutation Controller (Create or Update)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def user_save_ajax(request):
    """
    // [AJAX Mutation] Saves or updates a system account.
    // Handles credential updates, active/staff flags, and synchronizes institutional Profile.
    """
    user_id = request.POST.get("id")
    is_new = not bool(user_id)

    if user_id:
        user = get_object_or_404(User, pk=user_id)
    else:
        user = User()

    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    role = request.POST.get("role", "").strip().upper()
    program_id = request.POST.get("program_id")
    department_id = request.POST.get("department_id")
    year_level = request.POST.get("year_level")

    # // [Validation Rule] Identifier presence check
    if not username:
        return JsonResponse({"error": "Identifier / Student ID is required."}, status=400)

    # // [Conflict Prevention] Verify uniqueness of username and email across accounts
    dup_qs = User.objects.filter(Q(username=username) | (Q(email=email) & ~Q(email="")))
    if user_id:
        dup_qs = dup_qs.exclude(pk=user_id)
    if dup_qs.filter(username=username).exists():
        err_msg = "That Student ID is already registered." if role == Profile.ROLE_STUDENT else "That username is already taken."
        return JsonResponse({"error": err_msg}, status=400)
    if email and dup_qs.filter(email=email).exists():
        return JsonResponse({"error": "That email is already in use."}, status=400)

    # If student, also verify student_number uniqueness on Profile
    if role == Profile.ROLE_STUDENT:
        prof_dup = Profile.objects.filter(student_number=username)
        if user_id:
            prof_dup = prof_dup.exclude(user_id=user_id)
        if prof_dup.exists():
            return JsonResponse({"error": "A student profile with this Student ID already exists."}, status=400)

    user.username = username
    user.first_name = request.POST.get("first_name", "").strip()
    user.last_name = request.POST.get("last_name", "").strip()
    user.email = email

    is_active_val = request.POST.get("is_active")
    user.is_active = is_active_val in ["true", "on", "1", True]

    # System automatically assigns staff status strictly to Administrator accounts
    user.is_staff = (role == Profile.ROLE_ADMIN)

    password = request.POST.get("password")
    if password:
        password = password.strip()
        if password:
            user.set_password(password)
    elif is_new:
        return JsonResponse({"error": "Password is required for new accounts."}, status=400)

    try:
        user.save()
        profile = getattr(user, 'classstamp_profile', None)
        target_role = role or (profile.role if profile else Profile.ROLE_STUDENT)

        # Resolve academic relationships
        selected_program = None
        if program_id:
            selected_program = Program.objects.filter(pk=program_id).first()
        if not selected_program and target_role == Profile.ROLE_STUDENT:
            selected_program = Program.objects.filter(is_active=True).first()

        selected_dept = None
        if department_id:
            selected_dept = Department.objects.filter(pk=department_id).first()
        if not selected_dept and target_role == Profile.ROLE_TEACHER:
            selected_dept = Department.objects.filter(is_active=True).first()

        selected_year = int(year_level) if (year_level and str(year_level).isdigit()) else 1

        if not profile:
            if target_role == Profile.ROLE_STUDENT:
                profile = Profile.objects.create(
                    user=user,
                    role=Profile.ROLE_STUDENT,
                    student_number=username,
                    program=selected_program,
                    year_level=selected_year,
                    approval_status=Profile.APPROVAL_APPROVED,
                    approved_by=request.user,
                    approved_at=timezone.now(),
                    qr_secret=secrets.token_hex(32),
                )
            elif target_role == Profile.ROLE_TEACHER:
                profile = Profile.objects.create(
                    user=user,
                    role=Profile.ROLE_TEACHER,
                    department=selected_dept,
                    approval_status=Profile.APPROVAL_APPROVED,
                    approved_by=request.user,
                    approved_at=timezone.now(),
                )
            else:
                profile = Profile.objects.create(
                    user=user,
                    role=Profile.ROLE_ADMIN,
                    approval_status=Profile.APPROVAL_APPROVED,
                )
        else:
            fields_to_update = []
            if role and profile.role != role:
                profile.role = role
                fields_to_update.append('role')

            if profile.role == Profile.ROLE_STUDENT:
                if profile.student_number != username:
                    profile.student_number = username
                    fields_to_update.append('student_number')
                if selected_program and profile.program != selected_program:
                    profile.program = selected_program
                    fields_to_update.append('program')
                if year_level and profile.year_level != selected_year:
                    profile.year_level = selected_year
                    fields_to_update.append('year_level')
            elif profile.role == Profile.ROLE_TEACHER:
                if selected_dept and profile.department != selected_dept:
                    profile.department = selected_dept
                    fields_to_update.append('department')

            if fields_to_update:
                profile.save(update_fields=fields_to_update)

        AuditEvent.objects.create(
            actor=request.user,
            action='CREATE_USER' if is_new else 'UPDATE_USER',
            object_type='User',
            object_id=str(user.pk),
            new_value=f"{user.get_full_name() or user.username} ({user.email}) - Role: {profile.role if profile else 'USER'}",
        )
    except IntegrityError as e:
        return JsonResponse({"error": f"Database integrity error: {str(e)}"}, status=400)

    role_label = profile.role if profile else ('SUPERUSER' if user.is_superuser else 'NONE')

    return JsonResponse({
        "status": "success",
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "role": role_label,
    })


# // ==============================================================================
# // API / AJAX: User Deletion Controller
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def user_delete_ajax(request, pk):
    """
    // [AJAX Mutation] Permanently deletes a user account.
    // Self-deletion guard prevents administrators from locking themselves out of the system.
    """
    user = get_object_or_404(User, pk=pk)
    if request.user == user:
        return JsonResponse({"error": "You cannot delete yourself."}, status=400)

    user_info = f"{user.get_full_name() or user.username} ({user.email})"
    user_id_str = str(user.pk)

    user.delete()

    AuditEvent.objects.create(
        actor=request.user,
        action='DELETE_USER',
        object_type='User',
        object_id=user_id_str,
        old_value=user_info,
    )

    return JsonResponse({"status": "deleted"})


# // ==============================================================================
# // API / AJAX: Quick Status Toggle (Activate / Deactivate Account)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def user_toggle_status_ajax(request, pk):
    """
    // [AJAX Mutation] Instantly toggles an account between Active and Inactive state.
    // Self-deactivation guard prevents active administrators from locking themselves out.
    """
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        return JsonResponse({"error": "You cannot deactivate your own active session."}, status=400)

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])

    status_str = "activated" if target_user.is_active else "deactivated"
    display_name = target_user.get_full_name() or target_user.username

    AuditEvent.objects.create(
        actor=request.user,
        action='UPDATE_USER_STATUS',
        object_type='User',
        object_id=str(target_user.pk),
        new_value=f"Account {status_str}: {display_name} (ID: {target_user.pk})",
    )

    return JsonResponse({
        "status": "success",
        "is_active": target_user.is_active,
        "message": f"Account for {display_name} was {status_str} successfully."
    })


# // ==============================================================================
# // API / AJAX: Quick Password Reset Controller
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def user_reset_password_ajax(request, pk):
    """
    // [AJAX Mutation] Resets an account password with either a custom password
    // or an auto-generated high-entropy temporary credential.
    """
    target_user = get_object_or_404(User, pk=pk)
    custom_pwd = request.POST.get('password', '').strip()

    if custom_pwd:
        new_password = custom_pwd
    else:
        # Generate 10-char high-entropy temporary password
        chars = string.ascii_letters + string.digits
        rnd = ''.join(secrets.choice(chars) for _ in range(8))
        new_password = f"KCC-{rnd}"

    target_user.set_password(new_password)
    target_user.save(update_fields=['password'])

    display_name = target_user.get_full_name() or target_user.username
    AuditEvent.objects.create(
        actor=request.user,
        action='RESET_PASSWORD',
        object_type='User',
        object_id=str(target_user.pk),
        new_value=f"Administrative password reset for {display_name} ({target_user.email})",
    )

    return JsonResponse({
        "status": "success",
        "temporary_password": new_password,
        "username": target_user.username,
        "display_name": display_name,
        "message": f"Password has been reset successfully for {display_name}."
    })


# // ==============================================================================
# // VIEW: User Directory CSV Export Controller
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def user_export_csv(request):
    """
    // [Admin Controller] Streams role-tailored CSV records of system users.
    // Respects role tab, search query, status, department, and program filters.
    """
    role_tab = request.GET.get('role', 'students').strip()
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    dept_filter = request.GET.get('department', '').strip()
    prog_filter = request.GET.get('program', '').strip()
    year_filter = request.GET.get('year_level', '').strip()

    base_qs = User.objects.all().select_related(
        'classstamp_profile',
        'classstamp_profile__program',
        'classstamp_profile__department'
    ).order_by('-date_joined')

    if query:
        base_qs = base_qs.filter(
            Q(username__icontains=query) |
            Q(classstamp_profile__student_number__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    if status_filter == 'active':
        base_qs = base_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        base_qs = base_qs.filter(is_active=False)

    if dept_filter:
        base_qs = base_qs.filter(classstamp_profile__department_id=dept_filter)

    if prog_filter:
        base_qs = base_qs.filter(classstamp_profile__program_id=prog_filter)

    if year_filter and year_filter.isdigit():
        base_qs = base_qs.filter(classstamp_profile__year_level=int(year_filter))

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    timestamp = timezone.now().strftime('%Y%m%d_%H%M')
    response['Content-Disposition'] = f'attachment; filename="kcc_{role_tab}_users_{timestamp}.csv"'

    writer = csv.writer(response)

    if role_tab == 'teachers':
        writer.writerow([
            'User ID', 'Full Name', 'Faculty Username / ID', 'Department',
            'Email', 'Active Status', 'Staff Member', 'Date Joined', 'Last Login'
        ])
        teachers_qs = base_qs.filter(classstamp_profile__role=Profile.ROLE_TEACHER)
        for u in teachers_qs:
            prof = getattr(u, 'classstamp_profile', None)
            dept_name = prof.department.name if (prof and prof.department) else 'Unassigned'
            writer.writerow([
                u.id,
                u.get_full_name() or u.username,
                u.username,
                dept_name,
                u.email or 'N/A',
                'Active' if u.is_active else 'Inactive',
                'Yes' if u.is_staff else 'No',
                u.date_joined.strftime('%Y-%m-%d %H:%M') if u.date_joined else '',
                u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else 'Never'
            ])
    elif role_tab == 'admins':
        writer.writerow([
            'User ID', 'Full Name', 'Username', 'Email',
            'Role Classification', 'Superuser', 'Staff Member',
            'Active Status', 'Date Joined', 'Last Login'
        ])
        admins_qs = base_qs.filter(
            Q(classstamp_profile__role=Profile.ROLE_ADMIN) | Q(is_superuser=True)
        ).distinct()
        for u in admins_qs:
            prof = getattr(u, 'classstamp_profile', None)
            role_type = 'Superuser' if u.is_superuser else ('Administrator' if prof and prof.role == Profile.ROLE_ADMIN else 'Staff')
            writer.writerow([
                u.id,
                u.get_full_name() or u.username,
                u.username,
                u.email or 'N/A',
                role_type,
                'Yes' if u.is_superuser else 'No',
                'Yes' if u.is_staff else 'No',
                'Active' if u.is_active else 'Inactive',
                u.date_joined.strftime('%Y-%m-%d %H:%M') if u.date_joined else '',
                u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else 'Never'
            ])
    else:
        # Students
        writer.writerow([
            'User ID', 'Full Name', 'Student ID', 'Degree Program', 'Year Level',
            'Student Type', 'Validation Status', 'Email', 'Active Status', 'Date Joined'
        ])
        students_qs = base_qs.filter(classstamp_profile__role=Profile.ROLE_STUDENT)
        for u in students_qs:
            prof = getattr(u, 'classstamp_profile', None)
            prog_code = prof.program.code if (prof and prof.program) else 'N/A'
            year_lvl = f"Year {prof.year_level}" if (prof and prof.year_level) else 'Year 1'
            st_type = prof.get_student_type_display() if (prof and hasattr(prof, 'get_student_type_display')) else 'Regular'
            val_status = prof.get_approval_status_display() if (prof and hasattr(prof, 'get_approval_status_display')) else 'Pending'
            student_num = prof.student_number if (prof and prof.student_number) else u.username
            writer.writerow([
                u.id,
                u.get_full_name() or student_num,
                student_num,
                prog_code,
                year_lvl,
                st_type,
                val_status,
                u.email or 'N/A',
                'Active' if u.is_active else 'Inactive',
                u.date_joined.strftime('%Y-%m-%d %H:%M') if u.date_joined else ''
            ])

    return response