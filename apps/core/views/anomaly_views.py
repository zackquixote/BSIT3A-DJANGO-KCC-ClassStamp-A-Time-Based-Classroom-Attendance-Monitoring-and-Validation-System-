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
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import role_required
from apps.core.models import AnomalyFlag, AttendanceRecord, AuditEvent, Profile, ReviewAction


def _decision_to_status(decision):
    """
    // [Helper] Single source of truth mapping ReviewAction decisions to the
    // resulting AnomalyFlag status. Shared by single and bulk adjudication so
    // the two paths can never drift apart.
    """
    return {
        ReviewAction.DECISION_DISMISS: AnomalyFlag.STATUS_DISMISSED,
        ReviewAction.DECISION_CONFIRM_PROXY: AnomalyFlag.STATUS_CONFIRMED,
        ReviewAction.DECISION_EXCUSE: AnomalyFlag.STATUS_EXCUSED,
        ReviewAction.DECISION_OTHER: AnomalyFlag.STATUS_DISMISSED,
    }.get(decision, AnomalyFlag.STATUS_DISMISSED)


def _record_side_effect(record, decision, reason, actor):
    """
    // [Helper] Adjudication consequences on the underlying AttendanceRecord:
    // CONFIRM_PROXY demotes the fraudulent check-in to ABSENT; EXCUSE converts
    // the record to EXCUSED (mitigating circumstances). Emits an AuditEvent.
    // Returns the previous record status, or None when no side effect applies.
    """
    if decision == ReviewAction.DECISION_CONFIRM_PROXY:
        new_status = AttendanceRecord.STATUS_ABSENT
    elif decision == ReviewAction.DECISION_EXCUSE:
        new_status = AttendanceRecord.STATUS_EXCUSED
    else:
        return None

    old_status = record.status
    record.status = new_status
    record.correction_reason = f'Anomaly adjudication ({decision}): {reason}'
    record.save(update_fields=['status', 'correction_reason'])
    AuditEvent.objects.create(
        actor=actor,
        action='ADJUDICATION_RECORD_UPDATE',
        object_type='AttendanceRecord',
        object_id=str(record.id),
        old_value=old_status,
        new_value=new_status,
        reason=f'Anomaly adjudication {decision}: {reason}',
    )
    return old_status


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

    valid_statuses = {c[0] for c in AnomalyFlag.STATUS_CHOICES} | {'ALL'}
    if status_filter not in valid_statuses:
        status_filter = 'OPEN'

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

    # Counter badges (single aggregate pass)
    status_counts = dict(
        AnomalyFlag.objects.values('status')
        .annotate(total=Count('id'))
        .values_list('status', 'total')
    )
    count_open = status_counts.get(AnomalyFlag.STATUS_OPEN, 0)
    count_confirmed = status_counts.get(AnomalyFlag.STATUS_CONFIRMED, 0)
    count_dismissed = status_counts.get(AnomalyFlag.STATUS_DISMISSED, 0)
    count_excused = status_counts.get(AnomalyFlag.STATUS_EXCUSED, 0)
    count_all = sum(status_counts.values())

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

    if flag.status != AnomalyFlag.STATUS_OPEN:
        messages.error(request, f'Security Flag #{flag.id} has already been adjudicated.')
        return redirect('anomaly_list')

    old_status = flag.status
    new_status = _decision_to_status(decision)
    now = timezone.now()

    with transaction.atomic():
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

        # Apply consequences to the underlying attendance record
        if flag.attendance_record_id:
            _record_side_effect(flag.attendance_record, decision, reason, request.user)

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

    flags = (
        AnomalyFlag.objects
        .filter(pk__in=pks, status=AnomalyFlag.STATUS_OPEN)
        .select_related('attendance_record')
    )

    new_status = _decision_to_status(decision)

    updated = 0
    now = timezone.now()
    review_actions = []
    audit_events = []
    side_effect_records = []

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
        if flag.attendance_record_id:
            side_effect_records.append(flag.attendance_record)
        updated += 1

    with transaction.atomic():
        AnomalyFlag.objects.bulk_update(flags, ['status', 'resolved_at'])
        ReviewAction.objects.bulk_create(review_actions)
        AuditEvent.objects.bulk_create(audit_events)
        for record in side_effect_records:
            _record_side_effect(record, decision, reason, request.user)

    return _JR({'updated': updated, 'new_status': new_status})

