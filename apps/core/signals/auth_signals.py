"""
# // ==============================================================================
# // KCC CLASSSTAMP - AUTHENTICATION AUDIT SIGNALS
# // ==============================================================================
# // Subsystem: Security Audit Logging
# // Description: Hooks into Django authentication lifecycle signals to record immutable
# //   audit events for sign-in, sign-out, and failed login attempts.
# // ==============================================================================
"""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from apps.core.models import AuditEvent


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    // [Signal] Records user sign-in events into immutable AuditEvent trail.
    """
    client_ip = None
    if request:
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

    AuditEvent.objects.create(
        actor=user,
        action='USER_LOGIN',
        object_type='User',
        object_id=str(user.pk),
        new_value=f"User {user.username} authenticated successfully (IP: {client_ip or 'unknown'})",
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    // [Signal] Records session termination and logout events.
    """
    if user:
        AuditEvent.objects.create(
            actor=user,
            action='USER_LOGOUT',
            object_type='User',
            object_id=str(user.pk),
            new_value=f"User {user.username} signed out",
        )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """
    // [Signal] Records failed authentication attempts for brute-force tracking.
    """
    identifier = credentials.get('username', 'unknown') if credentials else 'unknown'
    client_ip = None
    if request:
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

    AuditEvent.objects.create(
        actor=None,
        action='LOGIN_FAILED',
        object_type='User',
        new_value=f"Failed login attempt for identifier '{identifier}' (IP: {client_ip or 'unknown'})",
        reason='Invalid credentials or locked account threshold',
    )
