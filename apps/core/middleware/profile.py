"""
# // ==============================================================================
# // KCC CLASSSTAMP - PROFILE ATTACHMENT MIDDLEWARE
# // ==============================================================================
# // Subsystem: Request Pipeline Context Enrichment
# // Description: Attaches the authenticated user's `Profile` instance to `request.profile`,
# //   providing fast, consistent profile access across view controllers and eliminating
# //   repetitive `getattr(request.user, 'classstamp_profile', None)` boilerplate.
# // ==============================================================================
"""


class AttachProfileMiddleware:
    """
    // Attaches `request.profile` to authenticated HTTP requests.
    // If the user is anonymous or has no profile assigned, sets `request.profile = None`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, 'user', None) and request.user.is_authenticated:
            request.profile = getattr(request.user, 'classstamp_profile', None)
            if request.profile is None and request.user.is_superuser:
                from apps.core.models import Profile

                request.profile, _ = Profile.objects.get_or_create(
                    user=request.user,
                    defaults={'role': Profile.ROLE_ADMIN},
                )
            if request.profile is None:
                from django.contrib import messages
                from django.urls import reverse

                if request.path not in {
                    reverse('dashboard'),
                    reverse('logout'),
                }:
                    messages.error(
                        request,
                        'Your account profile is incomplete. Contact an administrator.',
                    )
        else:
            request.profile = None

        return self.get_response(request)
