"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC CALENDAR CONTROLLERS
# // ==============================================================================
# // Subsystem: Academic Administration (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for the institutional calendar, term
# //   schedules, examination periods, holidays, and college events.
# //   Supports monthly, weekly, daily, and list views with real-time JSON feed,
# //   drag-and-drop rescheduling, overlap detection, and immutable audit logs.
# // Security References: docs/02_SECURITY.md | docs/06_ADMIN_IMPROVEMENTS_ROADMAP.md
# // ==============================================================================
"""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.decorators import role_required
from apps.core.models import (
    AcademicEvent,
    AcademicYear,
    AuditEvent,
    Profile,
)
from apps.core.services import seed_philippine_holidays


def _parse_iso_datetime(dt_str, is_end_of_day=False):
    """Safely converts string into timezone-aware datetime."""
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    if len(dt_str) == 10:  # YYYY-MM-DD
        if is_end_of_day:
            dt = datetime.strptime(dt_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        else:
            dt = datetime.strptime(dt_str, '%Y-%m-%d')
    else:
        dt = parse_datetime(dt_str)
        if not dt:
            dt = datetime.strptime(dt_str[:16], '%Y-%m-%dT%H:%M')
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _serialize_event(event):
    """Formats an AcademicEvent instance for FullCalendar consumption."""
    meta = event.category_meta
    start_dt = timezone.localtime(event.start_datetime) if timezone.is_aware(event.start_datetime) else event.start_datetime
    end_dt = timezone.localtime(event.end_datetime) if timezone.is_aware(event.end_datetime) else event.end_datetime

    # For FullCalendar all-day events, date-only string avoids time-shift display
    if event.is_all_day:
        start_val = start_dt.strftime('%Y-%m-%d')
        end_val = end_dt.strftime('%Y-%m-%d')
    else:
        start_val = start_dt.isoformat()
        end_val = end_dt.isoformat()

    creator_name = 'System'
    if event.created_by:
        creator_name = event.created_by.get_full_name() or event.created_by.username

    return {
        'id': event.id,
        'title': event.title,
        'start': start_val,
        'end': end_val,
        'allDay': event.is_all_day,
        'backgroundColor': meta['color'],
        'borderColor': meta['color'],
        'textColor': '#ffffff',
        'className': f"fc-event--{event.category.lower()} fc-status--{event.status.lower()}",
        'extendedProps': {
            'description': event.description or '',
            'category': event.category,
            'category_label': meta['label'],
            'category_icon': meta['icon'],
            'category_color': meta['color'],
            'category_bg': meta['bg'],
            'status': event.status,
            'status_display': event.get_status_display(),
            'location': event.location or '',
            'academic_year_id': event.academic_year_id,
            'academic_year_name': event.academic_year.name if event.academic_year else 'General',
            'semester': event.semester,
            'semester_display': event.get_semester_display(),
            'visibility': event.visibility,
            'visibility_display': event.get_visibility_display(),
            'is_all_day': event.is_all_day,
            'conflicts_count': event.get_conflicting_slots_count(),
            'start_formatted': start_dt.strftime('%b %d, %Y %I:%M %p') if not event.is_all_day else start_dt.strftime('%b %d, %Y'),
            'end_formatted': end_dt.strftime('%b %d, %Y %I:%M %p') if not event.is_all_day else end_dt.strftime('%b %d, %Y'),
            'created_by': creator_name,
            'updated_at': timezone.localtime(event.updated_at).strftime('%b %d, %Y %I:%M %p'),
        }
    }


# // ==============================================================================
# // VIEW: Admin Academic Calendar Main Dashboard (/admin/calendar/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_calendar_view(request):
    """
    // [Admin Controller] Academic Calendar Command Center.
    // Renders the interactive calendar interface with KPI metrics, active term badge,
    // category filters, and upcoming milestone summary.
    """
    now = timezone.now()
    today = now.date()
    active_year = AcademicYear.objects.filter(is_active=True).first()

    # KPI Telemetry
    total_events = AcademicEvent.objects.count()
    upcoming_events_count = AcademicEvent.objects.filter(
        start_datetime__gte=now,
        status=AcademicEvent.STATUS_SCHEDULED
    ).count()

    this_month_count = AcademicEvent.objects.filter(
        start_datetime__year=now.year,
        start_datetime__month=now.month,
        status=AcademicEvent.STATUS_SCHEDULED
    ).count()

    holidays_count = AcademicEvent.objects.filter(
        category=AcademicEvent.CATEGORY_HOLIDAY,
        status=AcademicEvent.STATUS_SCHEDULED
    ).count()

    # Semester progress bar (0-100%)
    semester_progress_pct = 0
    if active_year:
        total_days = (active_year.ends_on - active_year.starts_on).days or 1
        elapsed = max(0, (today - active_year.starts_on).days)
        semester_progress_pct = min(100, round(elapsed / total_days * 100))

    # Category event counts (single bulk query)
    cat_counts_qs = (
        AcademicEvent.objects
        .filter(status=AcademicEvent.STATUS_SCHEDULED)
        .values('category')
        .annotate(cnt=Count('id'))
    )
    category_counts = {row['category']: row['cnt'] for row in cat_counts_qs}

    # Merge category counts INTO the meta dict so template can use {{ meta.count }}
    category_meta_with_counts = {}
    for code, meta in AcademicEvent.CATEGORY_META.items():
        entry = dict(meta)
        entry['count'] = category_counts.get(code, 0)
        category_meta_with_counts[code] = entry

    # Today's events for sidebar "Today" panel
    today_events = list(
        AcademicEvent.objects.filter(
            start_datetime__date__lte=today,
            end_datetime__date__gte=today,
            status=AcademicEvent.STATUS_SCHEDULED,
        )
        .select_related('academic_year')
        .order_by('is_all_day', 'start_datetime')[:8]
    )

    # Next 10 upcoming events for sidebar feed
    upcoming_events = list(
        AcademicEvent.objects.filter(
            end_datetime__gte=now,
            status=AcademicEvent.STATUS_SCHEDULED
        )
        .select_related('academic_year')
        .order_by('start_datetime')[:10]
    )

    academic_years = AcademicYear.objects.order_by('-starts_on')

    context = {
        'total_events': total_events,
        'upcoming_events_count': upcoming_events_count,
        'this_month_count': this_month_count,
        'holidays_count': holidays_count,
        'upcoming_events': upcoming_events,
        'today_events': today_events,
        'category_counts': category_counts,
        'semester_progress_pct': semester_progress_pct,
        'active_academic_year': active_year,
        'academic_years': academic_years,
        'categories': AcademicEvent.CATEGORY_CHOICES,
        'category_meta': category_meta_with_counts,
        'statuses': AcademicEvent.STATUS_CHOICES,
        'semesters': AcademicEvent.SEMESTER_CHOICES,
        'visibilities': AcademicEvent.VISIBILITY_CHOICES,
        'now': now,
        'today': today,
    }
    return render(request, 'core/admin/calendar.html', context)


# // ==============================================================================
# // API / JSON: FullCalendar Event Stream Feed (/admin/calendar/events/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['GET'])
def admin_calendar_events_json(request):
    """
    // [AJAX Feed] Returns filtered calendar events within a given date window.
    // Query parameters:
    //   start: ISO datetime string (inclusive start of view)
    //   end: ISO datetime string (exclusive end of view)
    //   category: optional filter by category code
    //   academic_year: optional filter by academic_year_id
    //   semester: optional filter by semester code
    //   status: optional filter by status ('SCHEDULED' or 'CANCELED')
    //   q: search keyword matching title, description, or location
    """
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    category = request.GET.get('category', '').strip()
    ay_id = request.GET.get('academic_year', '').strip()
    semester = request.GET.get('semester', '').strip()
    status = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    qs = AcademicEvent.objects.select_related('academic_year', 'created_by')

    # Date range window
    if start_str:
        start_dt = parse_datetime(start_str)
        if not start_dt:
            try:
                start_dt = timezone.make_aware(datetime.strptime(start_str[:10], '%Y-%m-%d'))
            except Exception:
                start_dt = None
        if start_dt:
            qs = qs.filter(end_datetime__gte=start_dt)

    if end_str:
        end_dt = parse_datetime(end_str)
        if not end_dt:
            try:
                end_dt = timezone.make_aware(datetime.strptime(end_str[:10], '%Y-%m-%d'))
            except Exception:
                end_dt = None
        if end_dt:
            qs = qs.filter(start_datetime__lte=end_dt)

    # Filters
    if category:
        qs = qs.filter(category=category)
    if ay_id:
        qs = qs.filter(academic_year_id=ay_id)
    if semester:
        qs = qs.filter(semester=semester)
    if status:
        qs = qs.filter(status=status)
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(location__icontains=query)
        )

    events_data = [_serialize_event(e) for e in qs]
    return JsonResponse(events_data, safe=False)


# // ==============================================================================
# // API / JSON: Get Single Event Details (/admin/calendar/events/<pk>/get/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['GET'])
def admin_calendar_event_get(request, pk):
    """
    // [AJAX Read] Retrieves detailed data for a single academic event.
    """
    event = get_object_or_404(
        AcademicEvent.objects.select_related('academic_year', 'created_by', 'updated_by'),
        pk=pk
    )
    return JsonResponse({'status': 'success', 'event': _serialize_event(event)})


# // ==============================================================================
# // API / POST: Create or Update Event (/admin/calendar/events/save/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def admin_calendar_event_save(request):
    """
    // [AJAX Mutation] Creates or updates an institutional academic event.
    // Performs strict datetime validation, detects schedule overlaps, and records
    // immutable AuditEvent entries.
    """
    event_id = request.POST.get('event_id', '').strip()
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    category = request.POST.get('category', '').strip()
    status = request.POST.get('status', AcademicEvent.STATUS_SCHEDULED).strip()
    visibility = request.POST.get('visibility', AcademicEvent.VISIBILITY_ALL).strip()
    is_all_day = request.POST.get('is_all_day') in ['true', '1', 'on', True]
    location = request.POST.get('location', '').strip()
    academic_year_id = request.POST.get('academic_year', '').strip()
    semester = request.POST.get('semester', AcademicEvent.SEMESTER_ALL).strip()

    start_str = request.POST.get('start_datetime', '').strip()
    end_str = request.POST.get('end_datetime', '').strip()

    # Validation
    if not title:
        return JsonResponse({'error': 'Event title is required.'}, status=400)

    if category not in dict(AcademicEvent.CATEGORY_CHOICES):
        return JsonResponse({'error': 'Invalid event category.'}, status=400)

    if status not in dict(AcademicEvent.STATUS_CHOICES):
        status = AcademicEvent.STATUS_SCHEDULED

    if visibility not in dict(AcademicEvent.VISIBILITY_CHOICES):
        visibility = AcademicEvent.VISIBILITY_ALL

    if not start_str:
        return JsonResponse({'error': 'Start date & time is required.'}, status=400)

    # Parse datetimes using timezone-aware helper
    try:
        start_dt = _parse_iso_datetime(start_str, is_end_of_day=False)
    except Exception as exc:
        return JsonResponse({'error': f'Invalid start date format: {exc}'}, status=400)

    if end_str:
        try:
            end_dt = _parse_iso_datetime(end_str, is_end_of_day=is_all_day)
        except Exception as exc:
            return JsonResponse({'error': f'Invalid end date format: {exc}'}, status=400)
    else:
        end_dt = start_dt

    if end_dt < start_dt:
        return JsonResponse({'error': 'End date & time cannot be before start date & time.'}, status=400)

    # Academic Year verification
    ay = None
    if academic_year_id:
        try:
            ay = AcademicYear.objects.get(pk=academic_year_id)
        except AcademicYear.DoesNotExist:
            return JsonResponse({'error': 'Selected Academic Year does not exist.'}, status=404)

    # Check for overlapping events (Warning only, does not reject)
    overlap_qs = AcademicEvent.objects.filter(
        status=AcademicEvent.STATUS_SCHEDULED,
        start_datetime__lt=end_dt,
        end_datetime__gt=start_dt
    )
    if event_id:
        overlap_qs = overlap_qs.exclude(pk=event_id)
    overlapping_count = overlap_qs.count()
    overlap_warning = None
    if overlapping_count > 0:
        first_overlap = overlap_qs.first()
        overlap_warning = f"Notice: {overlapping_count} existing event(s) share this timeframe (e.g., '{first_overlap.title}')."

    # Save within transaction
    with transaction.atomic():
        if event_id:
            event = get_object_or_404(AcademicEvent, pk=event_id)
            old_snapshot = f"title='{event.title}', start='{event.start_datetime}', end='{event.end_datetime}', status='{event.status}'"

            event.title = title
            event.description = description
            event.category = category
            event.status = status
            event.visibility = visibility
            event.start_datetime = start_dt
            event.end_datetime = end_dt
            event.is_all_day = is_all_day
            event.location = location or None
            event.academic_year = ay
            event.semester = semester
            event.updated_by = request.user
            event.save()

            AuditEvent.objects.create(
                actor=request.user,
                action='UPDATE_ACADEMIC_EVENT',
                object_type='AcademicEvent',
                object_id=str(event.id),
                old_value=old_snapshot,
                new_value=f"title='{event.title}', start='{event.start_datetime}', end='{event.end_datetime}', status='{event.status}'",
                reason=f"Updated academic event #{event.id} by {request.user.username}"
            )
            action_verb = 'updated'
        else:
            event = AcademicEvent.objects.create(
                title=title,
                description=description,
                category=category,
                status=status,
                visibility=visibility,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_all_day=is_all_day,
                location=location or None,
                academic_year=ay,
                semester=semester,
                created_by=request.user,
                updated_by=request.user,
            )

            AuditEvent.objects.create(
                actor=request.user,
                action='CREATE_ACADEMIC_EVENT',
                object_type='AcademicEvent',
                object_id=str(event.id),
                new_value=f"title='{event.title}', start='{event.start_datetime}', end='{event.end_datetime}', cat='{event.category}'",
                reason=f"Created academic event '{event.title}' by {request.user.username}"
            )
            action_verb = 'created'

        conflicting_slots = event.get_conflicting_slots_count()
        if conflicting_slots > 0 and event.category in [AcademicEvent.CATEGORY_HOLIDAY, AcademicEvent.CATEGORY_ACADEMIC_TERM]:
            slot_msg = f"Schedule Notice: {conflicting_slots} active class timetable slot(s) coincide with this date span."
            overlap_warning = f"{overlap_warning} {slot_msg}" if overlap_warning else slot_msg

    return JsonResponse({
        'status': 'success',
        'message': f"Event '{event.title}' successfully {action_verb}.",
        'event': _serialize_event(event),
        'warning': overlap_warning,
    })


# // ==============================================================================
# // API / POST: Reschedule Event (Drag & Drop / Resize) (/admin/calendar/events/<pk>/reschedule/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def admin_calendar_event_reschedule(request, pk):
    """
    // [AJAX Mutation] Fast drag-and-drop or resize rescheduling endpoint.
    """
    event = get_object_or_404(AcademicEvent, pk=pk)

    start_str = request.POST.get('start', '').strip()
    end_str = request.POST.get('end', '').strip()
    is_all_day = request.POST.get('all_day') in ['true', '1', True]

    if not start_str:
        return JsonResponse({'error': 'New start datetime is required.'}, status=400)

    try:
        start_dt = _parse_iso_datetime(start_str, is_end_of_day=False)
    except Exception as exc:
        return JsonResponse({'error': f'Invalid start date: {exc}'}, status=400)

    if end_str:
        try:
            end_dt = _parse_iso_datetime(end_str, is_end_of_day=is_all_day)
        except Exception as exc:
            return JsonResponse({'error': f'Invalid end date: {exc}'}, status=400)
    else:
        # Default duration matching old duration
        old_duration = event.end_datetime - event.start_datetime
        end_dt = start_dt + old_duration

    if end_dt < start_dt:
        return JsonResponse({'error': 'End date & time cannot be before start date & time.'}, status=400)

    old_start = event.start_datetime
    old_end = event.end_datetime

    with transaction.atomic():
        event.start_datetime = start_dt
        event.end_datetime = end_dt
        if 'all_day' in request.POST:
            event.is_all_day = is_all_day
        event.updated_by = request.user
        event.save(update_fields=['start_datetime', 'end_datetime', 'is_all_day', 'updated_by', 'updated_at'])

        AuditEvent.objects.create(
            actor=request.user,
            action='RESCHEDULE_ACADEMIC_EVENT',
            object_type='AcademicEvent',
            object_id=str(event.id),
            old_value=f"start='{old_start}', end='{old_end}'",
            new_value=f"start='{start_dt}', end='{end_dt}'",
            reason=f"Rescheduled via calendar drag/resize by {request.user.username}"
        )

    return JsonResponse({
        'status': 'success',
        'message': f"'{event.title}' rescheduled to {timezone.localtime(start_dt).strftime('%b %d, %Y %I:%M %p')}.",
        'event': _serialize_event(event)
    })


# // ==============================================================================
# // API / POST: Cancel Event (/admin/calendar/events/<pk>/cancel/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def admin_calendar_event_cancel(request, pk):
    """
    // [AJAX Mutation] Marks an event as CANCELED while preserving it for historical reference.
    """
    event = get_object_or_404(AcademicEvent, pk=pk)

    if event.status == AcademicEvent.STATUS_CANCELED:
        # Un-cancel / Restore to Scheduled
        new_status = AcademicEvent.STATUS_SCHEDULED
        verb = 'restored to Scheduled'
    else:
        new_status = AcademicEvent.STATUS_CANCELED
        verb = 'canceled'

    with transaction.atomic():
        old_status = event.status
        event.status = new_status
        event.updated_by = request.user
        event.save(update_fields=['status', 'updated_by', 'updated_at'])

        AuditEvent.objects.create(
            actor=request.user,
            action='CANCEL_ACADEMIC_EVENT' if new_status == AcademicEvent.STATUS_CANCELED else 'RESTORE_ACADEMIC_EVENT',
            object_type='AcademicEvent',
            object_id=str(event.id),
            old_value=f"status='{old_status}'",
            new_value=f"status='{new_status}'",
            reason=f"Event #{event.id} status changed to {new_status} by {request.user.username}"
        )

    return JsonResponse({
        'status': 'success',
        'message': f"'{event.title}' successfully {verb}.",
        'event': _serialize_event(event)
    })


# // ==============================================================================
# // API / POST: Delete Event (/admin/calendar/events/<pk>/delete/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def admin_calendar_event_delete(request, pk):
    """
    // [AJAX Mutation] Permanently deletes an event record with audit logging.
    """
    event = get_object_or_404(AcademicEvent, pk=pk)
    title = event.title
    event_id = event.id

    with transaction.atomic():
        AuditEvent.objects.create(
            actor=request.user,
            action='DELETE_ACADEMIC_EVENT',
            object_type='AcademicEvent',
            object_id=str(event_id),
            old_value=f"title='{title}', start='{event.start_datetime}', cat='{event.category}'",
            reason=f"Deleted academic event #{event_id} by {request.user.username}"
        )
        event.delete()

    return JsonResponse({
        'status': 'success',
        'message': f"Event '{title}' was permanently deleted.",
        'event_id': event_id
    })


# // ==============================================================================
# // API / POST: Synchronize Philippine Holidays (/admin/calendar/sync-holidays/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def admin_calendar_sync_holidays(request):
    """
    // [AJAX Action] Automatically seeds official Philippine holidays into Academic Calendar.
    // Ingests current and upcoming academic calendar holidays with idempotent deduplication.
    """
    now = timezone.now()
    active_year = AcademicYear.objects.filter(is_active=True).first()

    res1 = seed_philippine_holidays(now.year, actor=request.user, academic_year=active_year)
    res2 = seed_philippine_holidays(now.year + 1, actor=request.user, academic_year=active_year)
    total_created = res1['created_count'] + res2['created_count']
    total_existing = res1['existing_count'] + res2['existing_count']

    return JsonResponse({
        'status': 'success',
        'message': f"Philippine Holidays synced! Ingested {total_created} new holiday(s) ({total_existing} already present).",
        'created_count': total_created,
        'existing_count': total_existing,
    })

