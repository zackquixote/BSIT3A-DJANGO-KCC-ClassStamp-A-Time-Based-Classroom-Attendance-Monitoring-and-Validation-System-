"""
# // ==============================================================================
# // KCC CLASSSTAMP - HOLIDAY AUTO-CANCEL SIGNALS
# // ==============================================================================
# // Subsystem: Academic Calendar -> ClassSession lifecycle (task 2.3)
# // Description: When a HOLIDAY AcademicEvent is created, cancel every
# //   SCHEDULED/OPEN ClassSession that falls on a date covered by the event.
# //
# //   Uses AcademicEvent.start_datetime / end_datetime (there is no event_date).
# //   Event boundaries are converted to project-local dates (Asia/Manila).
# //   Deleting or canceling a holiday does NOT restore sessions (Req 3.4).
# //   Manual reopen stays in teacher_session_open (REOPEN_CLASS_SESSION).
# // ==============================================================================
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.core.models import AcademicEvent, AuditEvent, ClassSession


@receiver(post_save, sender=AcademicEvent)
def auto_cancel_sessions_on_holiday(sender, instance, created, **kwargs):
    """
    // Auto-cancel SCHEDULED/OPEN sessions on a newly created holiday.
    // Only creation is processed; updates/deletes never restore sessions.
    """
    if not created:
        return
    if instance.category != AcademicEvent.CATEGORY_HOLIDAY:
        return
    if instance.status == AcademicEvent.STATUS_CANCELED:
        return

    start_date = timezone.localtime(instance.start_datetime).date()
    end_date = timezone.localtime(instance.end_datetime).date()

    sessions = ClassSession.objects.filter(
        session_date__range=(start_date, end_date),
        status__in=(ClassSession.STATUS_SCHEDULED, ClassSession.STATUS_OPEN),
    ).select_related('slot__class_obj')

    cancelled_count = 0
    for session in sessions:
        session.status = ClassSession.STATUS_CANCELED
        session.cancellation_reason = f'Auto-cancelled: {instance.title} (Holiday)'
        session.save(update_fields=['status', 'cancellation_reason', 'updated_at'])

        AuditEvent.objects.create(
            actor=None,
            action='SESSION_AUTO_CANCELLED',
            object_type='ClassSession',
            object_id=str(session.pk),
            old_value='SCHEDULED/OPEN',
            new_value='CANCELED',
            reason=f'Holiday: {instance.title} on {session.session_date}',
        )
        cancelled_count += 1

    if cancelled_count:
        AuditEvent.objects.create(
            actor=None,
            action='HOLIDAY_AUTO_CANCEL_COMPLETE',
            object_type='AcademicEvent',
            object_id=str(instance.pk),
            new_value=f'{cancelled_count} sessions cancelled',
            reason=f'Holiday: {instance.title}',
        )
