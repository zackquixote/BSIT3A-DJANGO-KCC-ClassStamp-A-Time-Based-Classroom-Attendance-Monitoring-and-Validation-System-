"""
# // ==============================================================================
# // KCC CLASSSTAMP - HOLIDAY AUTO-CANCEL SIGNALS
# // ==============================================================================
# // Subsystem: Academic Calendar -> ClassSession lifecycle (task 2.3)
# // Description: When a HOLIDAY AcademicEvent is created — or its dates,
# //   category, or status later change into an active holiday — cancel every
# //   SCHEDULED/OPEN ClassSession that falls on a date covered by the event.
# //
# //   Uses AcademicEvent.start_datetime / end_datetime (there is no event_date).
# //   Event boundaries are converted to project-local dates (Asia/Manila).
# //   The sweep is scoped to the event's academic year (or the active term when
# //   the event is not linked to one), so a November holiday cannot cancel the
# //   same calendar date in every other term.
# //   Sessions that already have attendance stamps are left untouched: live
# //   marks must not be orphaned on a CANCELED session.
# //   Deleting or canceling a holiday does NOT restore sessions (Req 3.4).
# //   Manual reopen stays in teacher_session_open (REOPEN_CLASS_SESSION).
# // ==============================================================================
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.core.models import AcademicEvent, AcademicYear, AuditEvent, ClassSession
from apps.core.services.in_app_notification_service import create_notification


def _scoped_sessions(instance):
    """
    // Holiday-candidate sessions, limited to one academic year.
    //
    // An event linked to a term only cancels inside that term. An unlinked
    // event means "institution-wide for the current term", not "every term
    // that happens to have a meeting on this date".
    """
    start_date = timezone.localtime(instance.start_datetime).date()
    end_date = timezone.localtime(instance.end_datetime).date()

    sessions = ClassSession.objects.filter(
        session_date__range=(start_date, end_date),
        status__in=(ClassSession.STATUS_SCHEDULED, ClassSession.STATUS_OPEN),
    ).select_related(
        'slot__class_obj',
        'slot__class_obj__teacher_profile__user',
    ).prefetch_related('attendance_records')

    if instance.academic_year_id:
        return sessions.filter(
            slot__class_obj__academic_year_id=instance.academic_year_id,
        )

    active_ay = AcademicYear.objects.filter(is_active=True).only('pk').first()
    if active_ay is None:
        return ClassSession.objects.none()
    return sessions.filter(slot__class_obj__academic_year=active_ay)


@receiver(post_save, sender=AcademicEvent)
def auto_cancel_sessions_on_holiday(sender, instance, created, **kwargs):
    """
    // Auto-cancel SCHEDULED/OPEN sessions on a holiday.
    //
    // Runs on create AND on update: extending a holiday, correcting a wrong
    // date, or changing an event's category to Holiday must all take effect.
    // The sweep is idempotent, so a title-only edit re-runs without
    // duplicating cancellations. Updates and deletes never restore sessions.
    """
    if instance.category != AcademicEvent.CATEGORY_HOLIDAY:
        return
    if instance.status == AcademicEvent.STATUS_CANCELED:
        return

    actor = instance.updated_by or instance.created_by
    sessions = _scoped_sessions(instance)

    cancelled_count = 0
    skipped_stamped = 0
    # One summary per teacher, not one push per section meeting.
    teacher_hits = {}

    for session in sessions:
        # Stamps already on the session stay meaningful. Cancelling an OPEN
        # session that already recorded attendance would hide live marks
        # behind a CANCELED status the reports then have to special-case.
        if session.attendance_records.exists():
            skipped_stamped += 1
            continue

        session.status = ClassSession.STATUS_CANCELED
        session.cancellation_reason = f'Auto-cancelled: {instance.title} (Holiday)'
        session.save(update_fields=['status', 'cancellation_reason', 'updated_at'])

        AuditEvent.objects.create(
            actor=actor,
            action='SESSION_AUTO_CANCELLED',
            object_type='ClassSession',
            object_id=str(session.pk),
            old_value='SCHEDULED/OPEN',
            new_value='CANCELED',
            reason=f'Holiday: {instance.title} on {session.session_date}',
        )

        teacher_profile = session.slot.class_obj.teacher_profile
        if teacher_profile is not None and teacher_profile.user_id:
            label = (
                f'{session.slot.class_obj.class_code} ({session.session_date})'
            )
            teacher_hits.setdefault(teacher_profile.user, []).append(label)

        cancelled_count += 1

    for teacher_user, labels in teacher_hits.items():
        create_notification(
            teacher_user,
            'calendar',
            'Class session(s) auto-cancelled (holiday)',
            (
                f'"{instance.title}" was declared a holiday. Cancelled: '
                f'{", ".join(labels)}.'
            ),
            '/teacher/sessions/',
        )

    if cancelled_count or skipped_stamped:
        AuditEvent.objects.create(
            actor=actor,
            action='HOLIDAY_AUTO_CANCEL_COMPLETE',
            object_type='AcademicEvent',
            object_id=str(instance.pk),
            new_value=(
                f'{cancelled_count} session(s) cancelled; '
                f'{skipped_stamped} skipped (already has attendance)'
            ),
            reason=f'Holiday: {instance.title}',
        )
