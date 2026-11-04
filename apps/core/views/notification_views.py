from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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
