"""
# // ==============================================================================
# // GLOBAL CONTEXT PROCESSORS
# // ==============================================================================
# // Purpose: Injects globally accessible context variables into template renderings.
# // Provides live indicators such as the pending validation queue counter for admins.
# // ==============================================================================
"""
from .models import AnomalyFlag, Notification, Profile


# // ==============================================================================
# // CONTEXT PROCESSOR: pending_approval_count
# // ==============================================================================
def pending_approval_count(request):
    """
    // Computes the total quantity of pending student registrations awaiting validation.
    //
    // Adds each user's unread notification badge. Admin-only approval and anomaly
    // counts remain restricted to admins and superusers.
    """
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, 'classstamp_profile', None)
        unread_notification_count = Notification.objects.filter(
            user=user,
            read_at__isnull=True,
        ).count()
        # // [RBAC Check] Only admins need the badge counter in their navigation
        is_admin = user.is_superuser or (profile is not None and profile.role == Profile.ROLE_ADMIN)
        if is_admin:
            return {
                'unread_notification_count': unread_notification_count,
                'pending_approval_count': Profile.objects.filter(
                    role=Profile.ROLE_STUDENT,
                    approval_status=Profile.APPROVAL_PENDING,
                ).count(),
                'open_anomaly_count': AnomalyFlag.objects.filter(
                    status=AnomalyFlag.STATUS_OPEN,
                ).count(),
            }
        return {
            'unread_notification_count': unread_notification_count,
            'pending_approval_count': 0,
            'open_anomaly_count': 0,
        }
    return {
        'unread_notification_count': 0,
        'pending_approval_count': 0,
        'open_anomaly_count': 0,
    }
