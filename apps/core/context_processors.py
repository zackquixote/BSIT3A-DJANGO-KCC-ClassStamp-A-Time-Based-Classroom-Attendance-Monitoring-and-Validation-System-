"""
# // ==============================================================================
# // GLOBAL CONTEXT PROCESSORS
# // ==============================================================================
# // Purpose: Injects globally accessible context variables into template renderings.
# // Provides live indicators such as the pending validation queue counter for admins.
# // ==============================================================================
"""
from .models import Profile


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
            }
    return {'pending_approval_count': 0}
