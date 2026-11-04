from django.utils import timezone

from apps.core.models import Enrollment, Notification


def create_notification(user, category, title, message, link=''):
    if user is None or not getattr(user, 'is_active', False):
        return None
    safe_link = link if link.startswith('/') and not link.startswith('//') else ''
    return Notification.objects.create(
        user=user,
        category=category[:32],
        title=title[:180],
        message=message,
        link=safe_link[:300],
    )


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
    return Notification.objects.bulk_create(notifications)


def notify_absent_students(student_profiles, class_obj, session_date):
    class_label = f'{class_obj.class_code} ({class_obj.subject.code})'
    return Notification.objects.bulk_create([
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


def mark_notification_read(notification):
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    return notification
