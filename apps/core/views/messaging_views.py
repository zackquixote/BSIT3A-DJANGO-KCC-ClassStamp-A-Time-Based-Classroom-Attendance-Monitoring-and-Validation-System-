"""
# // ==============================================================================
# // KCC CLASSSTAMP - INTERNAL MESSAGING CONTROLLERS (task 4.9)
# // ==============================================================================
# // Inbox grouped by conversation, compose, and two-user thread pages.
# // Recipient choices are limited to users the sender may contact.
# // ==============================================================================
"""

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.models import Profile
from apps.core.services.message_service import (
    MAX_BODY,
    MAX_SUBJECT,
    MessageError,
    MessageService,
    contact_meta,
    display_name,
    role_badge_class,
    role_key,
    role_label,
)


def _inbox_empty_hint(user) -> str:
    """
    // Role-accurate compose hint. Students cannot message administrators
    // (MessageService.can_contact), so the empty inbox must not say they can.
    """
    profile = getattr(user, 'classstamp_profile', None)
    if profile is None:
        if getattr(user, 'is_superuser', False):
            return 'you can write to any active user.'
        return 'recipients appear once your account profile is complete.'
    if profile.role == Profile.ROLE_STUDENT:
        return 'you can only write to the instructors of your active classes.'
    if profile.role == Profile.ROLE_TEACHER:
        return 'you can write to your own students or administrators.'
    return 'you can write to any active user.'


@login_required(login_url='login')
def message_inbox(request):
    conversations = MessageService.conversations(request.user)
    unread = MessageService.unread_count(request.user)
    return render(request, 'core/messages/inbox.html', {
        'conversations': conversations,
        'unread_message_total': unread,
        'empty_hint': _inbox_empty_hint(request.user),
    })


@login_required(login_url='login')
def message_compose(request):
    groups = MessageService.recipient_groups(request.user)
    # Only classes that already have students are offered as a bulk target;
    # an empty class has nothing to send to and would just clutter the picker.
    class_targets = [
        target for target in MessageService.class_targets(request.user)
        if target.recipient_count
    ]
    has_class_students = bool(class_targets)
    has_recipients = any(group['contacts'] for group in groups) or has_class_students

    error = ''
    preselect = str(
        request.GET.get('to') or request.POST.get('recipient', '') or ''
    )
    subject = request.POST.get('subject', '') if request.method == 'POST' else ''
    body = request.POST.get('body', '') if request.method == 'POST' else ''

    # With exactly one person to write to (the usual single-subject student),
    # pre-select them so "Send" needs no manual pick. Class-wide options are
    # excluded: those are a deliberate bulk action, never an accidental default.
    if not preselect:
        contacts = [contact for group in groups for contact in group['contacts']]
        if len(contacts) == 1 and not has_class_students:
            preselect = str(contacts[0]['user'].pk)

    if request.method == 'POST':
        if preselect.startswith('class:'):
            try:
                sent, class_obj = MessageService.send_to_class(
                    sender=request.user,
                    class_id=preselect.split(':', 1)[1],
                    subject=subject,
                    body=body,
                )
                django_messages.success(
                    request,
                    f'Message sent to {sent} student{"" if sent == 1 else "s"} '
                    f'in {class_obj.class_code}.',
                )
                return redirect('message_inbox')
            except MessageError as exc:
                error = str(exc)
        else:
            try:
                message = MessageService.send(
                    sender=request.user,
                    recipient_id=preselect,
                    subject=subject,
                    body=body,
                )
                return redirect('message_thread', user_id=message.recipient_id)
            except MessageError as exc:
                error = str(exc)

    return render(request, 'core/messages/compose.html', {
        'groups': groups,
        'class_targets': class_targets,
        'has_recipients': has_recipients,
        'preselect': preselect,
        'selected_class_id': (
            preselect.split(':', 1)[1] if preselect.startswith('class:') else ''
        ),
        'subject': subject,
        'body': body,
        'error': error,
        'max_subject': MAX_SUBJECT,
        'max_body': MAX_BODY,
    })


@login_required(login_url='login')
def message_thread(request, user_id):
    other, messages = MessageService.thread(request.user, user_id)
    if other is None:
        return redirect('message_inbox')

    # Opening a thread marks incoming messages read (recipient only).
    MessageService.mark_thread_as_read(messages, request.user)

    can_reply = MessageService.can_contact(request.user, other)
    reply_notice = ''
    if not can_reply:
        viewer_profile = getattr(request.user, 'classstamp_profile', None)
        if viewer_profile is not None and viewer_profile.role == Profile.ROLE_STUDENT:
            reply_notice = (
                'Students can only reply to their instructors. '
                'This conversation is read-only.'
            )
        else:
            reply_notice = 'You cannot reply in this conversation.'

    error = ''
    if request.method == 'POST' and can_reply:
        try:
            MessageService.send(
                sender=request.user,
                recipient_id=other.pk,
                subject=request.POST.get('subject', '').strip() or f"Re: {messages[-1].subject if messages else 'Message'}",
                body=request.POST.get('body', ''),
            )
            return redirect('message_thread', user_id=other.pk)
        except MessageError as exc:
            error = str(exc)

    # Prefill the reply subject from the LATEST message. `messages` is
    # oldest-first; quoting messages[0] pinned every reply to the first topic.
    reply_subject = f'Re: {messages[-1].subject}' if messages else ''

    # Sender context per bubble: a thread can mix an administrator and a
    # student, so each bubble names its sender and role instead of assuming
    # every message came from `other`.
    for message in messages:
        message.sender_name = display_name(message.sender)
        message.sender_role = role_label(message.sender)
        message.sender_badge = role_badge_class(message.sender)

    return render(request, 'core/messages/thread.html', {
        'other': other,
        'messages': messages,
        'other_name': display_name(other),
        'other_role': role_label(other),
        'other_role_key': role_key(other),
        'other_meta': contact_meta(other),
        'can_reply': can_reply,
        'reply_notice': reply_notice,
        'error': error,
        'reply_subject': reply_subject,
        'max_subject': MAX_SUBJECT,
        'max_body': MAX_BODY,
    })
