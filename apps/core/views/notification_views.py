from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import Notification
from apps.core.services.in_app_notification_service import mark_notification_read


@login_required(login_url='login')
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)[:100]
    return render(request, 'core/notifications.html', {
        'notifications': notifications,
        'unread_notification_count': Notification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).count(),
    })


@login_required(login_url='login')
@require_POST
def notification_mark_read(request, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        user=request.user,
    )
    mark_notification_read(notification)
    return redirect(notification.link or 'notification_list')


@login_required(login_url='login')
@require_POST
def notification_mark_all_read(request):
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return redirect('notification_list')


@login_required(login_url='login')
@require_GET
def notification_unread_api(request):
    """The unread rows the bell already knows about, as JSON for desktop alerts."""
    unread = (
        Notification.objects
        .filter(user=request.user, read_at__isnull=True)
        .order_by('-created_at')[:20]
    )
    return JsonResponse({
        'count': len(unread),
        'notifications': [
            {
                'id': row.pk,
                'title': row.title,
                'message': row.message,
                'link': row.link or reverse('notification_list'),
                'created_at': row.created_at.isoformat(),
            }
            for row in unread
        ],
    }, json_dumps_params={'ensure_ascii': False})
