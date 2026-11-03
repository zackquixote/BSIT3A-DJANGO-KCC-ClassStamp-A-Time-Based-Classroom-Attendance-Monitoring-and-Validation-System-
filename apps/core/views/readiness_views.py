"""
# // ==============================================================================
# // KCC CLASSSTAMP - CURRICULUM & TERM READINESS CONTROLLERS
# // ==============================================================================
# // Subsystem: Academic Administration (RBAC: ADMIN ONLY)
# // Description: Read-only report and CSV exports used before a new semester is
# //   published. These views never mutate curriculum, term, or class data.
# // ==============================================================================
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.core.decorators import role_required
from apps.core.models import Profile, Program
from apps.core.services.readiness_service import (
    build_curriculum_readiness_report,
    export_readiness_coverage_csv,
    export_readiness_issues_csv,
)


def _selected_program_id(request):
    raw_program_id = request.GET.get('program', '').strip()
    if not raw_program_id:
        return None
    try:
        return int(raw_program_id)
    except (TypeError, ValueError):
        return None


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def curriculum_readiness_report(request):
    """Render the read-only curriculum and term readiness report."""
    program_id = _selected_program_id(request)
    report = build_curriculum_readiness_report(program_id=program_id)
    program_options = (
        Program.objects.select_related('department')
        .order_by('department__code', 'code')
    )
    selected_program = next(
        (program for program in program_options if program.pk == program_id),
        None,
    )

    return render(request, 'core/admin/readiness.html', {
        'report': report,
        'program_options': program_options,
        'selected_program_id': program_id,
        'selected_program': selected_program,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_GET
def curriculum_readiness_export(request, report_type):
    """Export the coverage or issue section of the readiness report as CSV."""
    if report_type not in {'coverage', 'issues'}:
        raise Http404('Unknown readiness report.')

    report = build_curriculum_readiness_report(
        program_id=_selected_program_id(request),
    )
    if report_type == 'coverage':
        return export_readiness_coverage_csv(report)
    return export_readiness_issues_csv(report)
