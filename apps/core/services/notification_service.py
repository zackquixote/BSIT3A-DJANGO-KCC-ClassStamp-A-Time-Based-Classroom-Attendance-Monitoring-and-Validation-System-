"""
# // ==============================================================================
# // KCC CLASSSTAMP - NOTIFICATION SERVICE
# // ==============================================================================
# // Subsystem: Outbound messaging (email today, SMS later)
# // Description:
# //   One funnel for every transactional message so the institution can see what
# //   was sent and switch delivery off in one place.
# //
# //   Delivery rules:
# //     - no address  -> skipped, no error
# //     - no backend  -> console in development (see settings/dev.py)
# //     - backend down-> logged and swallowed: a dead SMTP server must never roll
# //                      back an attendance or approval transaction
# //   Every attempt writes an AuditEvent, sent or not, so "did the student get
# //   told?" is answerable after the fact.
# // References: apps/core/services/approval_service.py (existing pattern)
# // ==============================================================================
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.core.models import AuditEvent

logger = logging.getLogger(__name__)


def notifications_enabled():
    return bool(getattr(settings, 'NOTIFICATIONS_ENABLED', True))


def notify_user(user, subject, message, *, action='NOTIFICATION_SENT', object_type='Profile', object_id=''):
    """
    // Send one message to one user. Returns True when it left the building.
    // Never raises: notifications are side effects, not part of the transaction.
    """
    if user is None:
        return False

    address = (getattr(user, 'email', '') or '').strip()
    display = user.get_full_name() or user.get_username()

    if not address or not notifications_enabled():
        AuditEvent.objects.create(
            actor=None,
            action=action,
            object_type=object_type,
            object_id=str(object_id or getattr(user, 'pk', '') or ''),
            reason=f'Skipped: {"no email address" if not address else "notifications disabled"}',
            new_value=subject[:250],
        )
        return False

    delivered = False
    try:
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@classstamp.local'),
            [address],
            fail_silently=False,
        )
        delivered = True
    except Exception as exc:
        logger.warning('Notification to %s failed: %s', address, exc)

    AuditEvent.objects.create(
        actor=None,
        action=action,
        object_type=object_type,
        object_id=str(object_id or getattr(user, 'pk', '') or ''),
        reason=(
            f'Emailed {address}' if delivered
            else f'Delivery failed for {address}'
        ),
        new_value=f'{subject[:120]} -> {display}',
    )
    return delivered


def notify_excuse_decision(slip, approved, note=''):
    """
    // Tell a student their excuse slip was adjudicated.
    // Silence here is what makes students walk to the registrar's office.
    """
    student = slip.student_profile
    class_code = slip.session.slot.class_obj.class_code
    meeting = slip.session.session_date.strftime('%b %d, %Y')

    if approved:
        subject = f'[KCC ClassStamp] Excuse slip approved — {class_code}'
        body = (
            f'Hello {student.user.get_full_name() or student.user.get_username()},\n\n'
            f'Your excuse slip for {class_code} on {meeting} has been APPROVED. '
            f'The absence is now recorded as EXCUSED and no longer counts against your '
            f'attendance percentage.\n\n'
            f'Your reason on file: {slip.reason}\n\n'
            f'— KCC ClassStamp Registrar & Attendance Office'
        )
    else:
        subject = f'[KCC ClassStamp] Excuse slip rejected — {class_code}'
        body = (
            f'Hello {student.user.get_full_name() or student.user.get_username()},\n\n'
            f'Your excuse slip for {class_code} on {meeting} has been REJECTED. '
            f'The absence remains recorded as unexcused.\n\n'
            f'Reviewer note: {note or "(none provided)"}\n\n'
            f'If you believe this is wrong, contact your instructor or the Registrar\'s Office.\n\n'
            f'— KCC ClassStamp Registrar & Attendance Office'
        )

    return notify_user(
        student.user,
        subject,
        body,
        action='NOTIFY_EXCUSE_DECISION',
        object_type='ExcuseSlip',
        object_id=slip.pk,
    )


def notify_session_auto_closed(session, absent_count):
    """Tell the instructor their session was finalised by the scheduler."""
    class_obj = session.slot.class_obj
    teacher = getattr(class_obj.teacher_profile, 'user', None)

    subject = f'[KCC ClassStamp] Session auto-closed — {class_obj.class_code}'
    body = (
        f'Hello {teacher.get_full_name() if teacher else "Instructor"},\n\n'
        f'The attendance session for {class_obj.class_code} '
        f'({class_obj.subject.code}) on {session.session_date.strftime("%b %d, %Y")} '
        f'passed its scheduled end time and was closed automatically.\n\n'
        f'{absent_count} enrolled student(s) were marked ABSENT because no stamp was '
        f'recorded. You can still correct any of them from the session roll.\n\n'
        f'— KCC ClassStamp Attendance Engine'
    )
    return notify_user(
        teacher,
        subject,
        body,
        action='NOTIFY_SESSION_CLOSED',
        object_type='ClassSession',
        object_id=session.pk,
    )


def notify_at_risk(student_profile, class_obj, absence_rate, threshold):
    """Warn a student that they are at or past the institutional absence limit."""
    subject = f'[KCC ClassStamp] Attendance warning — {class_obj.class_code}'
    body = (
        f'Hello {student_profile.user.get_full_name() or student_profile.user.get_username()},\n\n'
        f'Your unexcused absence rate in {class_obj.class_code} '
        f'({class_obj.subject.code}) is {absence_rate}%, which is at or above the '
        f'institutional limit of {threshold}%.\n\n'
        f'Please coordinate with your instructor. Under CHED policy a student may be '
        f'barred from taking the final examination once this limit is exceeded.\n\n'
        f'— KCC ClassStamp Registrar & Attendance Office'
    )
    return notify_user(
        student_profile.user,
        subject,
        body,
        action='NOTIFY_AT_RISK',
        object_type='Enrollment',
        object_id=class_obj.pk,
    )
