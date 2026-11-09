"""
# // ==============================================================================
# // GLOBAL CONTEXT PROCESSORS
# // ==============================================================================
# // Purpose: Injects globally accessible context variables into template renderings.
# // Provides live indicators such as the pending validation queue counter for admins.
# // ==============================================================================
"""
from .models import AnomalyFlag, Notification, Profile
from django.conf import settings


# // ==============================================================================
# // CONTEXT PROCESSOR: pending_approval_count
# // ==============================================================================
def pending_approval_count(request):
    """
    // Computes the total quantity of pending student registrations awaiting validation.
    //
    // Adds each user's unread notification badge. Admin-only approval and anomaly
    // counts remain restricted to admins and superusers.
    //
    // Also reads the kcc_sidebar_collapsed cookie so the server can render
    // html.sidebar-collapsed directly — eliminating the client-side
    // localStorage restore that caused a transition flash on every page load.
    """
    user = getattr(request, 'user', None)

    # Read sidebar collapsed state from cookie — server-side so the class is
    # present in the very first byte of HTML, no JS needed on load.
    sidebar_collapsed = request.COOKIES.get('kcc_sidebar_collapsed', '') == '1'

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
                'web_push_public_key': getattr(settings, 'WEB_PUSH_PUBLIC_KEY', ''),
                'unread_notification_count': unread_notification_count,
                'pending_approval_count': Profile.objects.filter(
                    role=Profile.ROLE_STUDENT,
                    approval_status=Profile.APPROVAL_PENDING,
                ).count(),
                'open_anomaly_count': AnomalyFlag.objects.filter(
                    status=AnomalyFlag.STATUS_OPEN,
                ).count(),
                'sidebar_collapsed': sidebar_collapsed,
            }
        return {
            'web_push_public_key': getattr(settings, 'WEB_PUSH_PUBLIC_KEY', ''),
            'unread_notification_count': unread_notification_count,
            'pending_approval_count': 0,
            'open_anomaly_count': 0,
            'sidebar_collapsed': sidebar_collapsed,
        }
    return {
        'web_push_public_key': getattr(settings, 'WEB_PUSH_PUBLIC_KEY', ''),
        'unread_notification_count': 0,
        'pending_approval_count': 0,
        'open_anomaly_count': 0,
        'sidebar_collapsed': sidebar_collapsed,
    }
