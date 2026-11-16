"""
# // ==============================================================================
# // GLOBAL CONTEXT PROCESSORS
# // ==============================================================================
# // Purpose: Injects globally accessible context variables into template renderings.
# // Provides live indicators such as the pending validation queue counter for admins.
# // ==============================================================================
"""
import os

from django.conf import settings
from django.core.cache import cache

from .models import AnomalyFlag, Message, Notification, Profile

# pytest never sets argv[0] to 'test', so detection must use the env var the
# runner actually exports. Without this, a cached count leaks across tests.
_IS_TESTING = 'PYTEST_CURRENT_TEST' in os.environ
_COUNT_TTL = 20
_ADMIN_COUNT_TTL = 30


def _count(cache_key, queryset, timeout):
    if _IS_TESTING:
        return queryset.count()
    value = cache.get(cache_key)
    if value is None:
        value = queryset.count()
        cache.set(cache_key, value, timeout)
    return value


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

    # Same idea for the Security / Oversight dropdowns. They used to be opened
    # from localStorage on DOMContentLoaded, so the rail painted collapsed and
    # then popped open on every navigation. Reading the cookie lets the server
    # render the final open/closed state in the first paint instead.
    sidebar_dd_security_open = request.COOKIES.get('kcc_sidebar_dd_security', '') == 'open'
    sidebar_dd_oversight_open = request.COOKIES.get('kcc_sidebar_dd_oversight', '') == 'open'

    if user is not None and user.is_authenticated:
        profile = getattr(user, 'classstamp_profile', None)
        unread_notification_count = _count(
            f'ctx_unread_notif:{user.pk}',
            Notification.objects.filter(user=user, read_at__isnull=True),
            _COUNT_TTL,
        )
        unread_message_count = _count(
            f'ctx_unread_msg:{user.pk}',
            Message.objects.filter(recipient=user, is_read=False),
            _COUNT_TTL,
        )
        # // [RBAC Check] Only admins need the badge counter in their navigation
        is_admin = user.is_superuser or (profile is not None and profile.role == Profile.ROLE_ADMIN)
        if is_admin:
            return {
                'web_push_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
                'unread_notification_count': unread_notification_count,
                'unread_message_count': unread_message_count,
                'pending_approval_count': _count(
                    'ctx_pending_approval',
                    Profile.objects.filter(
                        role=Profile.ROLE_STUDENT,
                        approval_status=Profile.APPROVAL_PENDING,
                    ),
                    _ADMIN_COUNT_TTL,
                ),
                'open_anomaly_count': _count(
                    'ctx_open_anomaly',
                    AnomalyFlag.objects.filter(status=AnomalyFlag.STATUS_OPEN),
                    _ADMIN_COUNT_TTL,
                ),
                'sidebar_collapsed': sidebar_collapsed,
                'sidebar_dd_security_open': sidebar_dd_security_open,
                'sidebar_dd_oversight_open': sidebar_dd_oversight_open,
            }
        return {
            'web_push_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
            'unread_notification_count': unread_notification_count,
            'unread_message_count': unread_message_count,
            'pending_approval_count': 0,
            'open_anomaly_count': 0,
            'sidebar_collapsed': sidebar_collapsed,
            'sidebar_dd_security_open': sidebar_dd_security_open,
            'sidebar_dd_oversight_open': sidebar_dd_oversight_open,
        }
    return {
        'web_push_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
        'unread_notification_count': 0,
        'unread_message_count': 0,
        'pending_approval_count': 0,
        'open_anomaly_count': 0,
        'sidebar_collapsed': sidebar_collapsed,
        'sidebar_dd_security_open': sidebar_dd_security_open,
        'sidebar_dd_oversight_open': sidebar_dd_oversight_open,
    }
