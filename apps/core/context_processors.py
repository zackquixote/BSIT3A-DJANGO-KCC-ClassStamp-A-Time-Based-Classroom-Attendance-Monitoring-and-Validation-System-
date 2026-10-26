"""
# // ==============================================================================
# // GLOBAL CONTEXT PROCESSORS
# // ==============================================================================
# // Purpose: Injects globally accessible context variables into template renderings.
# // Provides live indicators such as the pending validation queue counter for admins.
# // ==============================================================================
"""
from .models import AnomalyFlag, Profile


# // ==============================================================================
# // CONTEXT PROCESSOR: pending_approval_count
# // ==============================================================================
def pending_approval_count(request):
    """
    // Computes the total quantity of pending student registrations awaiting validation.
    //
    // Security / Performance Note:
    // Only executed for users possessing the ADMIN role or superuser status to avoid
    // unnecessary database overhead during standard student or teacher interactions.
    // Also injects the open anomaly count so the sidebar Security Alerts badge can be
    // live-updated by sidebar_pending.js on every admin page.
    """
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, 'classstamp_profile', None)
        # // [RBAC Check] Only admins need the badge counter in their navigation
        is_admin = user.is_superuser or (profile is not None and profile.role == Profile.ROLE_ADMIN)
        if is_admin:
            return {
                'pending_approval_count': Profile.objects.filter(
                    role=Profile.ROLE_STUDENT,
                    approval_status=Profile.APPROVAL_PENDING,
                ).count(),
                'open_anomaly_count': AnomalyFlag.objects.filter(
                    status=AnomalyFlag.STATUS_OPEN,
                ).count(),
            }
    return {'pending_approval_count': 0, 'open_anomaly_count': 0}
