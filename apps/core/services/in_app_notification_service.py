import logging

from django.db import transaction
from django.utils import timezone

from apps.core.models import Enrollment, Notification
from apps.core.services.push_notification_service import PushNotificationService

logger = logging.getLogger(__name__)


def _queue_push(notification):
    """
    // Task 4.2: after the in-app row is saved, deliver it as a Web Push.
    // Delivery runs after the current transaction commits so a rollback never
    // notifies anyone, and a dead push endpoint never breaks the caller's
    // work. Disabled/missing-key behavior stays audited and non-raising.
    """
    if notification is None:
        return

    def _deliver():
        try:
            PushNotificationService.send_push_notification(notification)
        except Exception as exc:
            logger.warning(
                'Push delivery for notification %s failed: %s',
                getattr(notification, 'pk', '?'), exc,
            )

    try:
        transaction.on_commit(_deliver)
    except Exception as exc:
        logger.warning('Could not queue push for notification: %s', exc)


def create_notification(user, category, title, message, link=''):
    if user is None or not getattr(user, 'is_active', False):
        return None
    safe_link = link if link.startswith('/') and not link.startswith('//') else ''
    notification = Notification.objects.create(
        user=user,
        category=category[:32],
        title=title[:180],
        message=message,
        link=safe_link[:300],
    )
    _queue_push(notification)
    return notification


def notify_class_students(class_obj, category, title, message, link=''):
    user_ids = (
        Enrollment.objects.filter(
            class_obj=class_obj,
            status=Enrollment.STATUS_ACTIVE,
            student_profile__user__is_active=True,
        )
        .values_list('student_profile__user_id', flat=True)
        .distinct()
    )
    notifications = [
        Notification(
            user_id=user_id,
            category=category[:32],
            title=title[:180],
            message=message,
            link=link if link.startswith('/') and not link.startswith('//') else '',
        )
        for user_id in user_ids
    ]
    notifications = Notification.objects.bulk_create(notifications)
    # Queue a push for every created row; missing PKs on some backends still
    # deliver using the in-memory fields.
    for notification in notifications:
        _queue_push(notification)
    return notifications


def notify_absent_students(student_profiles, class_obj, session_date):
    class_label = f'{class_obj.class_code} ({class_obj.subject.code})'
    notifications = Notification.objects.bulk_create([
        Notification(
            user_id=profile.user_id,
            category='attendance',
            title='Attendance marked absent',
            message=(
                f'You were marked absent for {class_label} on {session_date}. '
                'Review your attendance log or contact your instructor if this is incorrect.'
            ),
            link='/student/attendance/',
        )
        for profile in student_profiles
        if profile.user_id
    ])
    for notification in notifications:
        _queue_push(notification)
    return notifications


def mark_notification_read(notification):
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    return notification
