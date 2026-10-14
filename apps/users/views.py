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

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.core.decorators import role_required
from apps.core.models import Profile


# // ==============================================================================
# // VIEW: User Management Page (Renders administrative user directory)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def user_list_page(request):
    """
    // [Admin Controller] User Management Directory View
    // Renders grouped lists of system accounts by role (Students / Teachers / Admins).
    // Supports multi-attribute search filter across all groups.
    """
    query = request.GET.get('q', '').strip()
    role_tab = request.GET.get('role', 'students').strip()  # 'students', 'teachers', 'admins'

    # // [Query Optimization] select_related avoids N+1 queries for user profiles
    base_qs = User.objects.all().select_related('classstamp_profile').order_by('-date_joined')

    # // [Search Filter] Matches username, first name, last name, or email address
    if query:
        base_qs = base_qs.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    # Split into role groups
    students_qs = base_qs.filter(classstamp_profile__role=Profile.ROLE_STUDENT)
    teachers_qs = base_qs.filter(classstamp_profile__role=Profile.ROLE_TEACHER)
    # Admins = profile ADMIN role OR superuser/staff with no student/teacher profile
    admins_qs = base_qs.filter(
        Q(classstamp_profile__role=Profile.ROLE_ADMIN) | Q(is_superuser=True)
    ).distinct()

    # Paginate the active tab
    per_page = 15
    if role_tab == 'teachers':
        paginator = Paginator(teachers_qs, per_page)
    elif role_tab == 'admins':
        paginator = Paginator(admins_qs, per_page)
    else:
        role_tab = 'students'
        paginator = Paginator(students_qs, per_page)

    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)

    return render(request, 'users/list.html', {
        'users': users,
        'query': query,
        'role_tab': role_tab,
        'students_count': students_qs.count(),
        'teachers_count': teachers_qs.count(),
        'admins_count': admins_qs.count(),
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
    users_list = User.objects.all().select_related('classstamp_profile').order_by('-date_joined')
    paginator = Paginator(users_list, 10)
    page_number = request.GET.get('page', 1)
    users = paginator.get_page(page_number)

    data = []
    for u in users.object_list:
        profile = getattr(u, 'classstamp_profile', None)
        role_label = profile.role if profile else ('SUPERUSER' if u.is_superuser else 'NONE')
        data.append({
            'id': u.id,
            'username': u.username,
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
    user = get_object_or_404(User.objects.select_related('classstamp_profile'), pk=pk)
    profile = getattr(user, 'classstamp_profile', None)
    role_label = profile.role if profile else ('SUPERUSER' if user.is_superuser else 'NONE')

    return JsonResponse({
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "role": role_label,
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
    // Handles credential updates, active/staff flags, and prevents duplicate usernames/emails.
    """
    user_id = request.POST.get("id")

    if user_id:
        user = get_object_or_404(User, pk=user_id)
    else:
        user = User()

    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()

    # // [Validation Rule] Username presence check
    if not username:
        return JsonResponse({"error": "Username is required."}, status=400)

    # // [Conflict Prevention] Verify uniqueness of username and email across accounts
    dup_qs = User.objects.filter(Q(username=username) | (Q(email=email) & ~Q(email="")))
    if user_id:
        dup_qs = dup_qs.exclude(pk=user_id)
    if dup_qs.filter(username=username).exists():
        return JsonResponse({"error": "That username is already taken."}, status=400)
    if email and dup_qs.filter(email=email).exists():
        return JsonResponse({"error": "That email is already in use."}, status=400)

    user.username = username
    user.first_name = request.POST.get("first_name", "").strip()
    user.last_name = request.POST.get("last_name", "").strip()
    user.email = email
    user.is_staff = request.POST.get("is_staff") == "true"
    user.is_active = request.POST.get("is_active") == "true"

    password = request.POST.get("password")
    if password:
        user.set_password(password)
    elif not user_id:
        return JsonResponse({"error": "Password is required for new users."}, status=400)

    try:
        user.save()
    except IntegrityError:
        return JsonResponse({"error": "Could not save user due to a conflict (duplicate username/email)."}, status=400)

    profile = getattr(user, 'classstamp_profile', None)
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
        return JsonResponse({"error": "You cannot delete yourself"}, status=400)

    user.delete()
    return JsonResponse({"status": "deleted"})