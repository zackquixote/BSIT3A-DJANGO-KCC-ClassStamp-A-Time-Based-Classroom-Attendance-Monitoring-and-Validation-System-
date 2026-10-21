"""
# // ==============================================================================
# // KCC CLASSSTAMP - ADMIN AUDIT LOG & AJAX FEED CONTROLLERS
# // ==============================================================================
# // Subsystem: Transparency & Live Dashboard Data Layer
# // Description:
# //   - admin_audit_log          -- Paginated AuditEvent browser for admins
# //   - admin_activity_feed_json -- AJAX endpoint: last 10 attendance stamps (JSON)
# //   - admin_pending_count_json -- AJAX endpoint: current pending count (JSON)
# // References: docs/02_SECURITY.md SS AuditEvent
# // ==============================================================================
"""

import csv

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.decorators import role_required
from apps.core.models import AuditEvent, Profile
from apps.core.views.helpers.dashboard_helpers import (
    get_activity_feed,
    get_pending_count,
)

AUTH_ACTIONS = ['USER_LOGIN', 'USER_LOGOUT', 'LOGIN_FAILED']


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_audit_log(request):
    category = request.GET.get('category', 'all').strip()
    action_filter = request.GET.get('action', '').strip()
    search_q = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date', '').strip()
    per_page_str = request.GET.get('per_page', '25').strip()

    # Determine per_page limit
    if per_page_str == 'all':
        per_page = 1000
    else:
        try:
            per_page = int(per_page_str)
            if per_page not in [25, 50, 100]:
                per_page = 25
        except (ValueError, TypeError):
            per_page = 25

    events_qs = AuditEvent.objects.select_related('actor').order_by('-created_at')

    # Category Tab filtering
    if category == 'admin':
        events_qs = events_qs.exclude(action__in=AUTH_ACTIONS)
    elif category == 'auth':
        events_qs = events_qs.filter(action__in=AUTH_ACTIONS)
    else:
        category = 'all'

    # Action type filter
    if action_filter:
        events_qs = events_qs.filter(action=action_filter)

    # Date filter
    if date_filter:
        try:
            events_qs = events_qs.filter(created_at__date=date_filter)
        except Exception:
            pass

    # Keyword search across actor, action, object, and remarks
    if search_q:
        events_qs = events_qs.filter(
            Q(action__icontains=search_q)
            | Q(actor__username__icontains=search_q)
            | Q(actor__first_name__icontains=search_q)
            | Q(actor__last_name__icontains=search_q)
            | Q(object_type__icontains=search_q)
            | Q(object_id__icontains=search_q)
            | Q(reason__icontains=search_q)
            | Q(new_value__icontains=search_q)
            | Q(old_value__icontains=search_q)
        )

    # Global Counts for Tab Badges
    count_all = AuditEvent.objects.count()
    count_admin = AuditEvent.objects.exclude(action__in=AUTH_ACTIONS).count()
    count_auth = AuditEvent.objects.filter(action__in=AUTH_ACTIONS).count()

    paginator = Paginator(events_qs, per_page)
    page_number = request.GET.get('page', 1)
    events = paginator.get_page(page_number)

    action_choices = (
        AuditEvent.objects.values_list('action', flat=True)
        .distinct()
        .order_by('action')
    )

    # Preserve GET parameters excluding 'page' for pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    base_query_string = query_params.urlencode()

    return render(request, 'core/admin/audit_log.html', {
        'events': events,
        'category': category,
        'action_filter': action_filter,
        'search_q': search_q,
        'date_filter': date_filter,
        'per_page': per_page_str,
        'action_choices': action_choices,
        'total_count': paginator.count,
        'count_all': count_all,
        'count_admin': count_admin,
        'count_auth': count_auth,
        'base_query_string': base_query_string,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_activity_feed_json(request):
    feed = get_activity_feed(limit=10)
    return JsonResponse({'feed': feed})


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_pending_count_json(request):
    from apps.core.models import AnomalyFlag
    count = get_pending_count()
    anomaly_count = AnomalyFlag.objects.filter(status=AnomalyFlag.STATUS_OPEN).count()
    return JsonResponse({'pending_count': count, 'open_anomaly_count': anomaly_count})


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_audit_log_export_csv(request):
    """
    // [Export Controller] Streams filtered AuditEvent records as a forensic CSV download.
    """
    category = request.GET.get('category', 'all').strip()
    action_filter = request.GET.get('action', '').strip()
    search_q = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date', '').strip()

    events_qs = AuditEvent.objects.select_related('actor').order_by('-created_at')

    if category == 'admin':
        events_qs = events_qs.exclude(action__in=AUTH_ACTIONS)
    elif category == 'auth':
        events_qs = events_qs.filter(action__in=AUTH_ACTIONS)

    if action_filter:
        events_qs = events_qs.filter(action=action_filter)

    if date_filter:
        try:
            events_qs = events_qs.filter(created_at__date=date_filter)
        except Exception:
            pass

    if search_q:
        events_qs = events_qs.filter(
            Q(action__icontains=search_q)
            | Q(actor__username__icontains=search_q)
            | Q(actor__first_name__icontains=search_q)
            | Q(actor__last_name__icontains=search_q)
            | Q(object_type__icontains=search_q)
            | Q(object_id__icontains=search_q)
            | Q(reason__icontains=search_q)
            | Q(new_value__icontains=search_q)
            | Q(old_value__icontains=search_q)
        )

    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"classstamp_audit_log_{timestamp}.csv"

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Log ID', 'Timestamp (PST)', 'Actor Username', 'Actor Full Name',
        'Action Keyword', 'Object Type', 'Object ID', 'Reason / Remarks', 'New State Snapshot'
    ])

    for ev in events_qs[:5000]:
        actor_username = ev.actor.username if ev.actor else 'SYSTEM'
        actor_fullname = ev.actor.get_full_name() if ev.actor else 'Automated Daemon'
        pst_time = timezone.localtime(ev.created_at).strftime('%Y-%m-%d %I:%M:%S %p')
        writer.writerow([
            ev.id,
            pst_time,
            actor_username,
            actor_fullname,
            ev.action,
            ev.object_type,
            ev.object_id or '—',
            ev.reason or '',
            ev.new_value or '',
        ])

    return response
