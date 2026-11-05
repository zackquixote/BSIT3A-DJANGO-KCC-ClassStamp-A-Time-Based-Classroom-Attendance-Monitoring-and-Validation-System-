"""
# // ==============================================================================
# // KCC CLASSSTAMP - SYSTEM POLICY CONTROLLER (ADMIN ONLY)
# // ==============================================================================
# // Subsystem: Administrative Policy
# // Description:
# //   Exposes the institution-level thresholds that used to be hardcoded:
# //     - scan close tolerance  -> upper bound of the attendance window
# //     - absence threshold     -> CHED failure-risk band (radar + student sentinel)
# //   Blank fields mean "use the documented default", so an institution that never
# //   opens this page behaves exactly as before.
# // References: apps/core/services/attendance_policy.py
# // ==============================================================================
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.decorators import role_required
from apps.core.models import AuditEvent, Profile, SystemPolicy
from apps.core.services.attendance_policy import DEFAULT_ABSENCE_THRESHOLD
from apps.core.views.session_views import SCAN_CLOSE_TOLERANCE_MINUTES

SCAN_TOLERANCE_MIN, SCAN_TOLERANCE_MAX = 0, 180
ABSENCE_THRESHOLD_MIN, ABSENCE_THRESHOLD_MAX = 1.0, 100.0


def _parse_optional_int(raw, label, minimum, maximum, errors):
    raw = (raw or '').strip()
    if raw == '':
        return None
    try:
        value = int(raw)
    except ValueError:
        errors[label] = 'Enter a whole number of minutes.'
        return None
    if not (minimum <= value <= maximum):
        errors[label] = f'Must be between {minimum} and {maximum}.'
        return None
    return value


def _parse_optional_float(raw, label, minimum, maximum, errors):
    raw = (raw or '').strip()
    if raw == '':
        return None
    try:
        value = float(raw)
    except ValueError:
        errors[label] = 'Enter a number.'
        return None
    if not (minimum <= value <= maximum):
        errors[label] = f'Must be between {minimum:g} and {maximum:g}.'
        return None
    return value


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['GET', 'POST'])
def admin_policy(request):
    """Render and update the singleton policy overrides."""
    policy = SystemPolicy.get_solo()

    if request.method == 'POST':
        errors = {}

        tolerance = _parse_optional_int(
            request.POST.get('scan_close_tolerance_minutes'),
            'tolerance', SCAN_TOLERANCE_MIN, SCAN_TOLERANCE_MAX, errors,
        )
        threshold = _parse_optional_float(
            request.POST.get('absence_threshold_percent'),
            'threshold', ABSENCE_THRESHOLD_MIN, ABSENCE_THRESHOLD_MAX, errors,
        )

        if errors:
            for message in errors.values():
                messages.error(request, message)
            return render(request, 'core/admin/policy.html', {
                'policy': policy,
                'defaults': _defaults(),
                'submitted': {
                    'scan_close_tolerance_minutes': request.POST.get('scan_close_tolerance_minutes', ''),
                    'absence_threshold_percent': request.POST.get('absence_threshold_percent', ''),
                },
            })

        before = _snapshot(policy)
        if policy is None:
            policy = SystemPolicy()
        policy.scan_close_tolerance_minutes = tolerance
        policy.absence_threshold_percent = threshold
        policy.updated_by = request.user
        policy.save()

        after = _snapshot(policy)
        AuditEvent.objects.create(
            actor=request.user,
            action='UPDATE_SYSTEM_POLICY',
            object_type='SystemPolicy',
            object_id=str(policy.pk),
            old_value=before,
            new_value=after,
            reason='Attendance policy updated from the admin console',
        )
        messages.success(request, 'Attendance policy updated.')
        return redirect('admin_policy')

    return render(request, 'core/admin/policy.html', {
        'policy': policy,
        'defaults': _defaults(),
        'submitted': {},
    })


def _defaults():
    return {
        'scan_close_tolerance_minutes': SCAN_CLOSE_TOLERANCE_MINUTES,
        'absence_threshold_percent': DEFAULT_ABSENCE_THRESHOLD,
    }


def _snapshot(policy):
    if policy is None:
        return 'defaults'
    return (
        f'tolerance={policy.scan_close_tolerance_minutes} '
        f'threshold={policy.absence_threshold_percent}'
    )
