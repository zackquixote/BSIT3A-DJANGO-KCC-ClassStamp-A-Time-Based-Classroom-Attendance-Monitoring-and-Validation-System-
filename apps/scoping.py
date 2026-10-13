"""
// ==============================================================================
// KCC CLASSSTAMP - SCOPING UTILITY
// ==============================================================================
// Description: Multi-tenant object scoping helpers to guarantee querysets are
// bound exclusively to the authenticated user.
// ==============================================================================
"""

from django.shortcuts import get_object_or_404
from apps.info.models import Info


# // ==============================================================================
# // HELPER: Filter Info objects scoped to specific user
# // ==============================================================================
def scoped_infos(user):
    """
    // Returns QuerySet of Info records filtered exclusively to the given user.
    """
    return Info.objects.filter(user=user)


# // ==============================================================================
# // HELPER: Retrieve single Info object with guaranteed user scoping
# // ==============================================================================
def scoped_info(user, pk):
    """
    // Retrieves a single Info instance by primary key belonging to the given user.
    // Automatically triggers Http404 if the primary key exists but belongs to someone else.
    """
    return get_object_or_404(scoped_infos(user), pk=pk)
