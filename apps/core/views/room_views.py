"""
# // ==============================================================================
# // KCC CLASSSTAMP - CAMPUS ROOM MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Facilities & Instructional Infrastructure (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for managing campus classrooms, computer
# //   laboratories, building-specific rooms, and specialized instruction facilities.
# //   Handles listing, search/filter, AJAX create/update, soft-deactivation protection,
# //   and JSON options for timetable and Section Builder integration.
# // Security Reference: docs/02_SECURITY.md
# // ==============================================================================
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.decorators import role_required
from apps.core.models import ClassSlot, FacilityType, Profile, Room
from apps.core.serializers import serialize_room
from apps.core.services import (
    create_or_update_room,
    delete_or_deactivate_room,
)


# // Built-in types the scheduler and lab/lecture stats depend on.
PROTECTED_FACILITY_CODES = {'LECTURE', 'LABORATORY'}


def _attach_slot_counts(rooms):
    """
    // Attaches slot_count to each Room on the current page using the SAME
    // attachment rule as delete_or_deactivate_room(): room_ref FK OR legacy
    // code-string match (case-insensitive).
    //
    // Done in Python (two grouped queries + an in-memory join) rather than a
    // column-to-column SQL comparison, because tblcs_room.code and
    // tblcs_class_slot.room use different MySQL collations and `LIKE` between
    // them raises OperationalError 1267.
    """
    rooms = list(rooms)
    if not rooms:
        return rooms

    by_pk = {r.pk: r for r in rooms}
    by_code = {}
    for r in rooms:
        r.slot_count = 0
        by_code.setdefault((r.code or '').upper(), []).append(r)

    fk_rows = (
        ClassSlot.objects.filter(room_ref_id__in=by_pk)
        .values('room_ref_id')
        .annotate(c=Count('pk'))
    )
    for row in fk_rows:
        room = by_pk.get(row['room_ref_id'])
        if room is not None:
            room.slot_count += row['c']

    unlinked = (
        ClassSlot.objects.filter(room_ref=None)
        .exclude(room='')
        .values_list('room', flat=True)
    )
    for room_str in unlinked:
        for room in by_code.get((room_str or '').upper(), []):
            room.slot_count += 1
    return rooms


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def room_list(request):
    """
    // [Admin Controller] Room Directory
    // Lists campus facilities with type badges, capacity, weekly slot load, and status.
    """
    query = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '').strip().upper()
    status_filter = request.GET.get('status', 'all').strip().lower()

    facility_types = list(FacilityType.objects.all())
    type_labels = {ft.code: ft.name for ft in facility_types}
    type_counts = {
        row['room_type']: row['c']
        for row in Room.objects.values('room_type').annotate(c=Count('pk'))
    }

    rooms_qs = Room.objects.order_by('room_type', 'code')

    if query:
        rooms_qs = rooms_qs.filter(
            Q(code__icontains=query) |
            Q(name__icontains=query)
        )

    if type_filter and type_filter in type_labels:
        rooms_qs = rooms_qs.filter(room_type=type_filter)

    if status_filter == 'active':
        rooms_qs = rooms_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        rooms_qs = rooms_qs.filter(is_active=False)

    paginator = Paginator(rooms_qs, 25)
    page_number = request.GET.get('page', 1)
    rooms = paginator.get_page(page_number)
    _attach_slot_counts(rooms.object_list)
    for room in rooms.object_list:
        room.type_label = type_labels.get(room.room_type, room.get_room_type_display())

    # Single aggregate for the metric cards. Type counts include inactive rooms
    # so the cards always add up against Total Facilities; Active & Ready is
    # the only card filtered by is_active.
    stats = Room.objects.aggregate(
        total=Count('pk'),
        active=Count('pk', filter=Q(is_active=True)),
        labs=Count('pk', filter=Q(room_type=Room.ROOM_TYPE_LABORATORY)),
        lectures=Count('pk', filter=Q(room_type=Room.ROOM_TYPE_LECTURE)),
    )

    return render(request, 'core/admin/rooms.html', {
        'rooms': rooms,
        'query': query,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'room_type_choices': [(ft.code, ft.name) for ft in facility_types],
        'facility_types': facility_types,
        'facility_types_admin': [
            {
                'id': ft.pk,
                'code': ft.code,
                'name': ft.name,
                'room_count': type_counts.get(ft.code, 0),
                'protected': ft.code in PROTECTED_FACILITY_CODES,
            }
            for ft in facility_types
        ],
        'total_count': stats['total'],
        'active_count': stats['active'],
        'lab_count': stats['labs'],
        'lecture_count': stats['lectures'],
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def room_save(request):
    """
    // [Admin Controller] Create or Update Room
    // Validates code uniqueness, type, and capacity. Emits audit trail.
    """
    room_id = request.POST.get('id', '').strip()
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()
    room_type = request.POST.get('room_type', Room.ROOM_TYPE_LECTURE).strip().upper()
    capacity = request.POST.get('capacity', '40').strip()
    notes = request.POST.get('notes', '').strip()
    is_active = request.POST.get('is_active') in ['true', 'on', '1', True]

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    try:
        result = create_or_update_room(
            actor=request.user,
            code=code,
            name=name,
            room_type=room_type,
            capacity=capacity,
            is_active=is_active,
            notes=notes,
            room_id=int(room_id) if room_id else None,
        )
    except ValueError as e:
        err = str(e)
        if is_ajax:
            return JsonResponse({'error': err}, status=400)
        messages.error(request, err)
        return redirect('room_list')

    room = result['instance']
    msg = result['message']

    if is_ajax:
        return JsonResponse({
            'status': 'success',
            'message': msg,
            'room': serialize_room(room),
        })

    messages.success(request, msg)
    return redirect('room_list')


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def room_delete(request, pk):
    """
    // [Admin Controller] Delete or Soft-Deactivate Room
    // Protects rooms with attached schedule slots by deactivating rather than hard-deleting.
    """
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    try:
        result = delete_or_deactivate_room(actor=request.user, pk=pk)
    except ValueError as exc:
        if is_ajax:
            return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect('room_list')

    if is_ajax:
        return JsonResponse({'status': 'success', 'message': result['message'], 'type': result['type']})

    messages.success(request, result['message'])
    return redirect('room_list')


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def room_detail_json(request, pk):
    """
    // [AJAX] Returns serialized room details for editing / delete-confirm modals.
    // attached_slot_count uses the delete-protection rule so the UI warning
    // matches what delete_or_deactivate_room will actually do.
    """
    room = get_object_or_404(Room, pk=pk)
    attached = ClassSlot.objects.filter(
        Q(room_ref=room) | Q(room__iexact=room.code)
    ).count()
    return JsonResponse({
        'room': serialize_room(room),
        'attached_slot_count': attached,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def room_options_json(request):
    """
    // [AJAX] Returns active rooms for schedule pickers and wizards.
    // ADMIN-only, matching class_wizard_options: room enumeration is an
    // administrative dataset and must not be reachable by student sessions.
    """
    room_type = request.GET.get('room_type', '').strip().upper()
    rooms_qs = Room.objects.filter(is_active=True).annotate(
        slot_count=Count('slots', filter=Q(slots__is_active=True), distinct=True),
    ).order_by('room_type', 'code')
    if room_type:
        rooms_qs = rooms_qs.filter(room_type=room_type)

    data = [serialize_room(r) for r in rooms_qs]
    return JsonResponse({'rooms': data})


# // ==============================================================================
# // FACILITY TYPES — registrar-managed room classification CRUD
# // ==============================================================================


def _facility_type_payload(ft, room_count=0):
    return {
        'id': ft.pk,
        'code': ft.code,
        'name': ft.name,
        'sort_order': ft.sort_order,
        'room_count': room_count,
        'protected': ft.code in PROTECTED_FACILITY_CODES,
    }


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def facility_type_save(request):
    """
    // [Admin Controller] Create / Update a Facility Type
    """
    import re

    from django.db import IntegrityError

    from apps.core.models import AuditEvent

    type_id = request.POST.get('id', '').strip()
    code = request.POST.get('code', '').strip().upper()
    name = request.POST.get('name', '').strip()

    if not code:
        return JsonResponse({'status': 'error', 'error': 'Code is required (e.g. HSB).'}, status=400)
    if not re.fullmatch(r'[A-Z0-9]+(?:-[A-Z0-9]+)*', code):
        return JsonResponse({
            'status': 'error',
            'error': 'Code may only contain letters, digits, and single hyphens (e.g. HSB, HS-BLDG).',
        }, status=400)
    if len(code) > 20:
        return JsonResponse({'status': 'error', 'error': 'Code must be 20 characters or fewer.'}, status=400)
    if not name:
        return JsonResponse({'status': 'error', 'error': 'Display name is required.'}, status=400)
    if len(name) > 60:
        return JsonResponse({'status': 'error', 'error': 'Display name must be 60 characters or fewer.'}, status=400)

    if type_id:
        ft = get_object_or_404(FacilityType, pk=int(type_id))
        if code != ft.code and Room.objects.filter(room_type=ft.code).exists():
            return JsonResponse({
                'status': 'error',
                'error': 'This type is already used by rooms, so its code cannot change. Rename the label instead.',
            }, status=400)
        if code != ft.code and FacilityType.objects.filter(code__iexact=code).exclude(pk=ft.pk).exists():
            return JsonResponse({'status': 'error', 'error': f'"{code}" is already another facility type.'}, status=400)
        action = 'UPDATE_FACILITY_TYPE'
        message = f'Facility type "{name}" updated.'
    else:
        ft = FacilityType()
        action = 'CREATE_FACILITY_TYPE'
        message = f'Facility type "{name}" added.'

    ft.code = code
    ft.name = name
    try:
        ft.save()
    except IntegrityError:
        return JsonResponse({'status': 'error', 'error': f'"{code}" is already another facility type.'}, status=400)

    AuditEvent.objects.create(
        actor=request.user,
        action=action,
        object_type='FacilityType',
        object_id=str(ft.pk),
        reason=f'{ft.code} — {ft.name}',
    )
    return JsonResponse({
        'status': 'success',
        'message': message,
        'type': _facility_type_payload(ft, Room.objects.filter(room_type=ft.code).count()),
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def facility_type_delete(request, pk):
    """
    // [Admin Controller] Delete a Facility Type
    // Refuses while rooms are assigned to it, and keeps the built-in four.
    """
    from apps.core.models import AuditEvent

    ft = get_object_or_404(FacilityType, pk=pk)
    if ft.code in PROTECTED_FACILITY_CODES:
        return JsonResponse({
            'status': 'error',
            'error': 'This is a built-in facility type. You can rename it, but not delete it.',
        }, status=400)

    used = Room.objects.filter(room_type__iexact=ft.code).count()
    if used:
        return JsonResponse({
            'status': 'error',
            'error': f'{used} room(s) still use "{ft.name}". Reassign them before deleting this type.',
        }, status=400)

    label = str(ft)
    ft.delete()
    AuditEvent.objects.create(
        actor=request.user,
        action='DELETE_FACILITY_TYPE',
        object_type='FacilityType',
        object_id=str(pk),
        reason=label,
    )
    return JsonResponse({'status': 'success', 'message': f'Facility type "{label}" deleted.'})
