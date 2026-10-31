"""
# // ==============================================================================
# // KCC CLASSSTAMP - PROTECTED DOCUMENT DELIVERY CONTROLLERS
# // ==============================================================================
# // Subsystem: Identity Document Privacy (registration proofs & excuse attachments)
# // Description: Serves uploaded student documents through permission-checked
# //   views instead of exposing MEDIA_URL directly. Access rules:
# //     - Registration proof: owning student or ADMIN only.
# //     - Excuse attachment: owning student, assigned TEACHER, or ADMIN.
# //   Responses are marked private/no-store so browsers and proxies do not cache
# //   sensitive identity documents.
# // ==============================================================================
"""

import mimetypes
import os

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from apps.core.models import ExcuseSlip, Profile


def _is_admin(user) -> bool:
    """Return True for superusers and profiles carrying the ADMIN role."""
    if user.is_superuser:
        return True
    profile = getattr(user, 'classstamp_profile', None)
    return bool(profile and profile.role == Profile.ROLE_ADMIN)


def _serve_private_file(field_file):
    """Stream a FileField through Django with private, non-cacheable headers."""
    if not field_file:
        raise Http404('Document not found.')

    try:
        path = field_file.path
    except (NotImplementedError, OSError, ValueError):
        raise Http404('Document is unavailable.')

    if not os.path.isfile(path):
        raise Http404('Document is unavailable.')

    content_type = mimetypes.guess_type(field_file.name)[0] or 'application/octet-stream'
    try:
        response = FileResponse(
            open(path, 'rb'),
            content_type=content_type,
            as_attachment=False,
            filename=os.path.basename(field_file.name),
        )
    except OSError:
        raise Http404('Document is unavailable.')

    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store, max-age=0'
    return response


@login_required(login_url='login')
def registration_proof_document(request, profile_id):
    """
    // [Protected File] Registration proof / COR image or PDF.
    // Visible to the owning student and administrators only.
    """
    profile = get_object_or_404(
        Profile.objects.select_related('user'),
        pk=profile_id,
        role=Profile.ROLE_STUDENT,
    )

    if profile.user_id != request.user.pk and not _is_admin(request.user):
        return HttpResponseForbidden('You are not authorized to view this document.')

    return _serve_private_file(profile.registration_proof)


@login_required(login_url='login')
def excuse_slip_attachment_document(request, slip_id):
    """
    // [Protected File] Supporting document attached to an excuse slip.
    // Visible to the owning student, the assigned instructor, and administrators.
    """
    slip = get_object_or_404(
        ExcuseSlip.objects.select_related(
            'student_profile__user',
            'session__slot__class_obj',
        ),
        pk=slip_id,
    )

    allowed = slip.student_profile.user_id == request.user.pk or _is_admin(request.user)
    if not allowed:
        profile = getattr(request.user, 'classstamp_profile', None)
        allowed = bool(
            profile
            and profile.role == Profile.ROLE_TEACHER
            and slip.session.slot.class_obj.teacher_profile_id == profile.id
        )

    if not allowed:
        return HttpResponseForbidden('You are not authorized to view this document.')

    return _serve_private_file(slip.attachment)
