"""
# // ==============================================================================
# // KCC CLASSSTAMP - ACADEMIC YEAR & TERM MANAGEMENT CONTROLLERS
# // ==============================================================================
# // Subsystem: Institutional Academic Calendar Administration (RBAC: ADMIN ONLY)
# // Description: Administrative controllers for creating and managing academic
# //   year / semester term windows. Enforces the single-active-term invariant
# //   via atomic transactions in the service layer.
# // Security Reference: docs/02_SECURITY.md
# // ==============================================================================
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from apps.core.decorators import role_required
from apps.core.models import AcademicYear, AuditEvent, Class, GradingPeriod, Profile
from apps.core.serializers.academic_serializers import serialize_academic_year
from apps.core.services import (
    TermSwitchBlocked,
    clone_classes_academic_year,
    create_or_update_academic_year,
    delete_or_deactivate_academic_year,
    enable_join_codes_for_classes,
    rollover_academic_year,
    set_active_academic_year,
)


# // ==============================================================================
# // VIEW: Academic Year & Term Directory (/academic-years/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def academic_year_list(request):
    """
    // [Admin Controller] Academic Year & Term Management
    // Lists all academic terms ordered by date, with class section counts,
    // active status indicator, and CRUD modal controls.
    """
    academic_years_qs = (
        AcademicYear.objects.annotate(
            class_count=Count('classes', distinct=True),
        )
        .order_by('-starts_on')
    )

    paginator = Paginator(academic_years_qs, 15)
    page_number = request.GET.get('page', 1)
    academic_years = paginator.get_page(page_number)

    active_term = AcademicYear.objects.filter(is_active=True).first()
    total_count = AcademicYear.objects.count()
    active_class_count = (
        AcademicYear.objects.filter(is_active=True)
        .annotate(c=Count('classes')).first()
    )
    active_class_count = active_class_count.c if active_class_count else 0

    today = timezone.localdate()
    days_remaining = None
    if active_term and active_term.ends_on:
        delta = active_term.ends_on - today
        days_remaining = max(delta.days, 0)

    # Drives the "nothing is current" banner: either no term is active, or the
    # active one has already closed while still flagged active.
    active_term_ended = bool(
        active_term and active_term.ends_on and active_term.ends_on < today
    )

    return render(request, 'core/admin/academic_years.html', {
        'academic_years': academic_years,
        'active_term': active_term,
        'active_term_ended': active_term_ended,
        'total_count': total_count,
        'active_class_count': active_class_count,
        'days_remaining': days_remaining,
    })


# // ==============================================================================
# // AJAX: Create / Update Academic Year (/academic-years/save/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_save(request):
    """
    // [AJAX] Create or update an academic year / term.
    // POST params: name, starts_on, ends_on, is_active, ay_id (optional)
    """
    try:
        ay_id = request.POST.get('ay_id') or None
        if ay_id:
            ay_id = int(ay_id)

        result = create_or_update_academic_year(
            actor=request.user,
            name=request.POST.get('name', ''),
            starts_on=request.POST.get('starts_on', ''),
            ends_on=request.POST.get('ends_on', ''),
            is_active=request.POST.get('is_active') == '1',
            ay_id=ay_id,
        )
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'academic_year': serialize_academic_year(result['instance']),
        })
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)


# // ==============================================================================
# // AJAX: Set Active Academic Year (/academic-years/set-active/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_set_active(request, pk: int):
    """
    // [AJAX] Promote the given academic year as the current active institutional term.
    // Atomically deactivates all other terms in the same transaction.
    """
    try:
        result = set_active_academic_year(
            actor=request.user,
            pk=pk,
            force=request.POST.get('force') == '1',
            reason=request.POST.get('reason', ''),
        )
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'academic_year': serialize_academic_year(result['instance']),
        })
    except TermSwitchBlocked as blocked:
        return JsonResponse({
            'ok': False,
            'error': blocked.message,
            'blockers': blocked.blockers,
            'requires_force': True,
        }, status=409)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Delete / Deactivate Academic Year (/academic-years/delete/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_delete(request, pk: int):
    """
    // [AJAX] Delete or soft-deactivate an academic year term.
    // Protected: If classes are scheduled under this term, deactivates instead.
    """
    try:
        result = delete_or_deactivate_academic_year(actor=request.user, pk=pk)
        return JsonResponse({
            'ok': True,
            'type': result['type'],
            'message': result['message'],
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# // ==============================================================================
# // AJAX: Get Single Academic Year (/academic-years/get/<pk>/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def academic_year_get(request, pk: int):
    """
    // [AJAX] Returns serialized academic year for modal pre-population.
    """
    ay = get_object_or_404(
        AcademicYear.objects.annotate(class_count=Count('classes', distinct=True)),
        pk=pk
    )
    return JsonResponse({'ok': True, 'academic_year': serialize_academic_year(ay)})


# // ==============================================================================
# // AJAX: Term Rollover (/academic-years/rollover/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_rollover(request):
    """
    // [AJAX] Term rollover wizard finalize (A-08).
    // POST params: name, starts_on, ends_on, promote ('1' | '0')
    // Atomically creates the new active term, deactivates predecessors,
    // and optionally promotes approved students one year level.
    """
    try:
        result = rollover_academic_year(
            actor=request.user,
            name=request.POST.get('name', ''),
            starts_on=request.POST.get('starts_on', ''),
            ends_on=request.POST.get('ends_on', ''),
            promote=request.POST.get('promote') == '1',
        )
        return JsonResponse({
            'ok': True,
            'message': result['message'],
            'academic_year': serialize_academic_year(result['instance']),
            'promoted_count': result['promoted_count'],
            'previous_actives': result['previous_actives'],
        })
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)


# // ==============================================================================
# // AJAX: Clone Class Structure (/academic-years/clone-classes/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['POST'])
def academic_year_clone(request):
    """
    // [AJAX] Clone the active class/slot structure of one term into another
    // (Req 12). Distinct from rollover: this never activates a term and never
    // promotes students. POST params: source_year_id, target_year_id.
    """
    try:
        source_id = int(request.POST.get('source_year_id', ''))
        target_id = int(request.POST.get('target_year_id', ''))
    except ValueError:
        return JsonResponse(
            {'ok': False, 'error': 'Choose both a source term and a target term.'},
            status=400,
        )

    with_join_codes = request.POST.get('with_join_codes', '') in ('1', 'true', 'on', 'True')

    try:
        result = clone_classes_academic_year(
            actor=request.user,
            source_year=source_id,
            target_year=target_id,
        )
    except AcademicYear.DoesNotExist:
        return JsonResponse(
            {'ok': False, 'error': 'Source or target term was not found.'},
            status=404,
        )
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'An unexpected error occurred.'}, status=500)

    # Newly copied classes must appear in the target term checklist immediately.
    cache.delete(f'setup_checklist_{target_id}')

    join_codes = []
    join_codes_error = ''
    if with_join_codes and result['class_mapping']:
        target_ids = [item['target_class_id'] for item in result['class_mapping']]
        try:
            codes_result = enable_join_codes_for_classes(request.user, target_ids)
            join_codes = codes_result['enabled']
        except Exception:
            join_codes_error = (
                'Classes were cloned, but generating join codes failed. '
                'Use Enable Join Codes to try again.'
            )

    return JsonResponse({
        'ok': True,
        'message': result['message'],
        'copied_class_count': result['copied_class_count'],
        'copied_slot_count': result['copied_slot_count'],
        'class_mapping': result['class_mapping'],
        'errors': result['errors'],
        'join_codes': join_codes,
        'join_codes_error': join_codes_error,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def academic_year_enable_join_codes(request):
    """
    // [AJAX] Generate student join codes for every active class in a term
    // that does not already have one. Optionally limited to class_ids.
    // Plaintext codes are returned once; the database stores only digests.
    """
    ay_id = request.POST.get('academic_year_id', '').strip()
    class_ids = [value for value in request.POST.getlist('class_ids') if str(value).strip()]

    if class_ids:
        ids = class_ids
        target_ay = None
    else:
        if not ay_id.isdigit():
            return JsonResponse(
                {'ok': False, 'error': 'Choose a term or at least one class.'},
                status=400,
            )
        target_ay = AcademicYear.objects.filter(pk=int(ay_id)).first()
        if target_ay is None:
            return JsonResponse({'ok': False, 'error': 'Term not found.'}, status=404)
        ids = list(
            Class.objects.filter(academic_year=target_ay, is_active=True)
            .values_list('pk', flat=True)
        )

    try:
        result = enable_join_codes_for_classes(request.user, ids)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception:
        return JsonResponse(
            {'ok': False, 'error': 'An unexpected error occurred while generating join codes.'},
            status=500,
        )

    # The checklist cache is keyed by active term. Invalidate that key when the
    # touched term is the active one (join-code items flip from missing to done).
    if target_ay is not None and target_ay.is_active:
        cache.delete(f'setup_checklist_{target_ay.pk}')
    elif target_ay is None:
        # class_ids path: invalidate every class's AY key that we can see
        for class_obj in Class.objects.filter(pk__in=ids).select_related('academic_year'):
            cache.delete(f'setup_checklist_{class_obj.academic_year_id}')

    return JsonResponse({
        'ok': True,
        'message': result['message'],
        'enabled': result['enabled'],
        'skipped': result['skipped'],
    })


# // ==============================================================================
# // VIEW: Grading Period Dates (/academic-years/<pk>/grading-periods/)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_http_methods(['GET', 'POST'])
def grading_periods(request, pk: int):
    """
    // Admin sets the exact Prelim / Midterm / Finals date windows for one term.
    // Attendance reports filter sessions by these dates; without them, period
    // exports cannot claim to be a real prelim/midterm/finals report.
    """
    ay = get_object_or_404(AcademicYear, pk=pk)
    codes = [GradingPeriod.CODE_PRELIM, GradingPeriod.CODE_MIDTERM, GradingPeriod.CODE_FINALS]
    labels = dict(GradingPeriod.CODE_CHOICES)
    existing = {period.code: period for period in ay.grading_periods.all()}

    form_values = {
        code: {
            'start': existing[code].start_date.isoformat() if code in existing else '',
            'end': existing[code].end_date.isoformat() if code in existing else '',
        }
        for code in codes
    }
    error = ''

    if request.method == 'POST':
        parsed = {}
        for code in codes:
            start_raw = request.POST.get(f'{code.lower()}_start', '').strip()
            end_raw = request.POST.get(f'{code.lower()}_end', '').strip()
            form_values[code] = {'start': start_raw, 'end': end_raw}
            if not start_raw or not end_raw:
                error = f'Complete the start and end dates for {labels[code]}.'
                break
            try:
                parsed[code] = (date.fromisoformat(start_raw), date.fromisoformat(end_raw))
            except ValueError:
                error = f'Use valid dates for {labels[code]}.'
                break

        if not error:
            ordered = sorted(parsed.items(), key=lambda item: item[1][0])
            for index, (code, (start, end)) in enumerate(ordered):
                if start > end:
                    error = f'{labels[code]} starts after it ends.'
                    break
                if start < ay.starts_on or end > ay.ends_on:
                    error = (
                        f'{labels[code]} must fit inside {ay.name} '
                        f'({ay.starts_on:%b %d, %Y} - {ay.ends_on:%b %d, %Y}).'
                    )
                    break
                if index and start <= ordered[index - 1][1][1]:
                    error = (
                        f'{labels[code]} overlaps {labels[ordered[index - 1][0]]}. '
                        'Grading periods must not overlap.'
                    )
                    break

        if not error:
            with transaction.atomic():
                for code, (start, end) in parsed.items():
                    GradingPeriod.objects.update_or_create(
                        academic_year=ay,
                        code=code,
                        defaults={'start_date': start, 'end_date': end},
                    )
                AuditEvent.objects.create(
                    actor=request.user,
                    action='GRADING_PERIODS_UPDATED',
                    object_type='AcademicYear',
                    object_id=str(ay.pk),
                    new_value='; '.join(
                        f'{labels[code]}: {start.isoformat()}..{end.isoformat()}'
                        for code, (start, end) in sorted(parsed.items(), key=lambda item: item[1][0])
                    ),
                    reason=f'Grading period dates set for {ay.name}',
                )
            messages.success(request, f'Grading periods saved for {ay.name}.')
            return redirect('grading_periods', pk=ay.pk)

    period_rows = [
        {
            'code': code,
            'label': labels[code],
            'start': form_values[code]['start'],
            'end': form_values[code]['end'],
        }
        for code in codes
    ]
    return render(request, 'core/admin/grading_periods.html', {
        'academic_year': ay,
        'period_rows': period_rows,
        'error': error,
    })
