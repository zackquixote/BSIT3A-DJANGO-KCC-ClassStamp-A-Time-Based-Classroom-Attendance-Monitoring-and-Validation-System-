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

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render

from apps.core.decorators import role_required
from apps.core.models import AuditEvent, Profile
from apps.core.views.helpers.dashboard_helpers import (
    get_activity_feed,
    get_pending_count,
)


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_audit_log(request):
    action_filter = request.GET.get('action', '').strip()
    events_qs = AuditEvent.objects.select_related('actor').order_by('-created_at')

    if action_filter:
        events_qs = events_qs.filter(action__icontains=action_filter)

    paginator = Paginator(events_qs, 25)
    page_number = request.GET.get('page', 1)
    events = paginator.get_page(page_number)

    action_choices = (
        AuditEvent.objects.values_list('action', flat=True)
        .distinct()
        .order_by('action')
    )

    return render(request, 'core/admin/audit_log.html', {
        'events': events,
        'action_filter': action_filter,
        'action_choices': action_choices,
        'total_count': paginator.count,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_activity_feed_json(request):
    feed = get_activity_feed(limit=10)
    return JsonResponse({'feed': feed})


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def admin_pending_count_json(request):
    count = get_pending_count()
    return JsonResponse({'pending_count': count})
