"""
# // ==============================================================================
# // KCC CLASSSTAMP - SECURITY ANOMALY & FRAUD INVESTIGATION CONTROLLERS
# // ==============================================================================
# // Subsystem: Security Intelligence & Fraud Adjudication (RBAC: ADMIN ONLY)
# // Description: Provides an administrative interface to inspect, investigate,
# //   and adjudicate flagged attendance anomalies (rapid scan proxies, token replays,
# //   impossible travel, out-of-schedule stamping).
# // References: docs/02_SECURITY.md § Fraud Detection | apps/core/models/audit.py
# // ==============================================================================
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import role_required
from apps.core.models import AnomalyFlag, AuditEvent, Profile, ReviewAction


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
def anomaly_list(request):
    """
    // [Admin Controller] Security Anomaly Review Panel
    // Displays all flagged attendance events with risk score ratings and forensic reasons.
    """
    status_filter = request.GET.get('status', 'OPEN').strip()
    search_q = request.GET.get('q', '').strip()
    per_page_str = request.GET.get('per_page', '20').strip()

    try:
        per_page = int(per_page_str)
        if per_page not in [10, 20, 50]:
            per_page = 20
    except (ValueError, TypeError):
        per_page = 20

    flags_qs = (
        AnomalyFlag.objects
        .select_related(
            'attendance_record__student_profile__user',
            'attendance_record__student_profile__program',
            'attendance_record__session__slot__class_obj__subject',
            'attendance_record__session__slot__class_obj__teacher_profile__user',
        )
        .prefetch_related('review_actions__reviewer')
        .order_by('-created_at')
    )

    if status_filter != 'ALL':
        flags_qs = flags_qs.filter(status=status_filter)

    if search_q:
        flags_qs = flags_qs.filter(
            Q(rule_code__icontains=search_q)
            | Q(reason__icontains=search_q)
            | Q(attendance_record__student_profile__student_number__icontains=search_q)
            | Q(attendance_record__student_profile__user__first_name__icontains=search_q)
            | Q(attendance_record__student_profile__user__last_name__icontains=search_q)
            | Q(attendance_record__session__slot__class_obj__class_code__icontains=search_q)
        )

    # Counter badges
    count_open = AnomalyFlag.objects.filter(status=AnomalyFlag.STATUS_OPEN).count()
    count_confirmed = AnomalyFlag.objects.filter(status=AnomalyFlag.STATUS_CONFIRMED).count()
    count_dismissed = AnomalyFlag.objects.filter(status=AnomalyFlag.STATUS_DISMISSED).count()
    count_excused = AnomalyFlag.objects.filter(status=AnomalyFlag.STATUS_EXCUSED).count()
    count_all = AnomalyFlag.objects.count()

    paginator = Paginator(flags_qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/admin/anomalies.html', {
        'flags': page_obj,
        'status_filter': status_filter,
        'search_q': search_q,
        'per_page': str(per_page),
        'count_open': count_open,
        'count_confirmed': count_confirmed,
        'count_dismissed': count_dismissed,
        'count_excused': count_excused,
        'count_all': count_all,
        'decision_choices': ReviewAction.DECISION_CHOICES,
    })


@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def anomaly_adjudicate(request, pk):
    """
    // [Action Controller] Submits forensic adjudication for an AnomalyFlag.
    // Creates an append-only ReviewAction and updates flag status.
    """
    flag = get_object_or_404(AnomalyFlag, pk=pk)
    decision = request.POST.get('decision', '').strip()
    reason = request.POST.get('reason', '').strip()

    valid_decisions = [c[0] for c in ReviewAction.DECISION_CHOICES]
    if decision not in valid_decisions:
        messages.error(request, 'Invalid adjudication decision selected.')
        return redirect('anomaly_list')

    if not reason:
        messages.error(request, 'An investigation reason / justification is required.')
        return redirect('anomaly_list')

    old_status = flag.status

    # Map review decision to AnomalyFlag status
    if decision == ReviewAction.DECISION_DISMISS:
        new_status = AnomalyFlag.STATUS_DISMISSED
    elif decision == ReviewAction.DECISION_CONFIRM_PROXY:
        new_status = AnomalyFlag.STATUS_CONFIRMED
    elif decision == ReviewAction.DECISION_EXCUSE:
        new_status = AnomalyFlag.STATUS_EXCUSED
    else:
        new_status = AnomalyFlag.STATUS_DISMISSED

    now = timezone.now()
    flag.status = new_status
    flag.resolved_at = now
    flag.save(update_fields=['status', 'resolved_at'])

    # Append immutable ReviewAction
    ReviewAction.objects.create(
        anomaly_flag=flag,
        reviewer=request.user,
        decision=decision,
        reason=reason,
    )

    # Append global AuditEvent
    AuditEvent.objects.create(
        actor=request.user,
        action='ADJUDICATE_ANOMALY',
        object_type='AnomalyFlag',
        object_id=str(flag.id),
        old_value=old_status,
        new_value=new_status,
        reason=f"Decision: {decision} | Justification: {reason}",
    )

    messages.success(request, f"Security Flag #{flag.id} successfully updated to {new_status}.")
    return redirect('anomaly_list')


# // ==============================================================================
# // VIEW: Bulk Dismiss / Confirm Anomaly Flags (#11)
# // ==============================================================================
@login_required(login_url='login')
@role_required(Profile.ROLE_ADMIN)
@require_POST
def anomaly_bulk_action(request):
    """
    // [Batch Action] Bulk adjudicate multiple AnomalyFlag records.
    // POST: decision=DISMISS|CONFIRM_PROXY, ids[]=pk, reason=<str>
    // Returns JSON: {updated: N, skipped: N}
    """
    from django.http import JsonResponse as _JR
    decision = request.POST.get('decision', '').strip()
    reason = request.POST.get('reason', 'Bulk administrative adjudication').strip()
    raw_ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')

    valid_decisions = [c[0] for c in ReviewAction.DECISION_CHOICES]
    if decision not in valid_decisions:
        return _JR({'error': 'Invalid decision.'}, status=400)

    pks = []
    for raw in raw_ids:
        try:
            pks.append(int(raw))
        except (ValueError, TypeError):
            pass

    if not pks:
        return _JR({'error': 'No flags selected.'}, status=400)

    flags = AnomalyFlag.objects.filter(pk__in=pks, status=AnomalyFlag.STATUS_OPEN)

    if decision == ReviewAction.DECISION_DISMISS:
        new_status = AnomalyFlag.STATUS_DISMISSED
    elif decision == ReviewAction.DECISION_CONFIRM_PROXY:
        new_status = AnomalyFlag.STATUS_CONFIRMED
    else:
        new_status = AnomalyFlag.STATUS_DISMISSED

    updated = 0
    now = timezone.now()
    review_actions = []
    audit_events = []

    for flag in flags:
        flag.status = new_status
        flag.resolved_at = now
        review_actions.append(ReviewAction(
            anomaly_flag=flag,
            reviewer=request.user,
            decision=decision,
            reason=reason,
        ))
        audit_events.append(AuditEvent(
            actor=request.user,
            action='ADJUDICATE_ANOMALY',
            object_type='AnomalyFlag',
            object_id=str(flag.id),
            old_value=AnomalyFlag.STATUS_OPEN,
            new_value=new_status,
            reason=f"Bulk: {decision} | {reason}",
        ))
        updated += 1

    AnomalyFlag.objects.bulk_update(flags, ['status', 'resolved_at'])
    ReviewAction.objects.bulk_create(review_actions)
    AuditEvent.objects.bulk_create(audit_events)

    return _JR({'updated': updated, 'new_status': new_status})

