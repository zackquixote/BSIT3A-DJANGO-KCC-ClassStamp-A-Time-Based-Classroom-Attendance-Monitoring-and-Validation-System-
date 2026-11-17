"""
# // ==============================================================================
# // KCC CLASSSTAMP - INTERNAL MESSAGING CONTROLLERS (task 4.9)
# // ==============================================================================
# // Inbox grouped by conversation, compose, and two-user thread pages.
# // Recipient choices are limited to users the sender may contact.
# // ==============================================================================
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import Profile
from apps.core.services.message_service import (
    MAX_BODY,
    MAX_SUBJECT,
    MessageError,
    MessageService,
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
        return 'you can write to instructors of your active classes, and reply to administrators who messaged you.'
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
    recipients = MessageService.eligible_recipients(request.user)
    error = ''
    preselect = request.GET.get('to') or request.POST.get('recipient', '')
    subject = request.POST.get('subject', '') if request.method == 'POST' else ''
    body = request.POST.get('body', '') if request.method == 'POST' else ''

    if request.method == 'POST':
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
        'recipients': recipients,
        'preselect': preselect,
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

    error = ''
    if request.method == 'POST':
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

    return render(request, 'core/messages/thread.html', {
        'other': other,
        'messages': messages,
        'error': error,
        'reply_subject': reply_subject,
        'max_subject': MAX_SUBJECT,
        'max_body': MAX_BODY,
    })
