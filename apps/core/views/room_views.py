"""
# // ==============================================================================
# // KCC CLASSSTAMP - CAMPUS ROOM MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Facilities & Instructional Infrastructure (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for managing campus classrooms, computer
# //   laboratories, AVRs, and specialized instruction facilities.
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
from apps.core.models import ClassSlot, Profile, Room
from apps.core.serializers import serialize_room
from apps.core.services import (
    create_or_update_room,
    delete_or_deactivate_room,
)


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

    rooms_qs = Room.objects.order_by('room_type', 'code')

    if query:
        rooms_qs = rooms_qs.filter(
            Q(code__icontains=query) |
            Q(name__icontains=query)
        )

    if type_filter and type_filter in [c[0] for c in Room.ROOM_TYPE_CHOICES]:
        rooms_qs = rooms_qs.filter(room_type=type_filter)

    if status_filter == 'active':
        rooms_qs = rooms_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        rooms_qs = rooms_qs.filter(is_active=False)

    paginator = Paginator(rooms_qs, 25)
    page_number = request.GET.get('page', 1)
    rooms = paginator.get_page(page_number)
    _attach_slot_counts(rooms.object_list)

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
        'room_type_choices': Room.ROOM_TYPE_CHOICES,
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
