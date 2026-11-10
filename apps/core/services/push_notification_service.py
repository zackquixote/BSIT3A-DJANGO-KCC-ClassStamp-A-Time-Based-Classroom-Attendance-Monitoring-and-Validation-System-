"""
# // ==============================================================================
# // KCC CLASSSTAMP - PUSH NOTIFICATION SERVICE
# // ==============================================================================
# // Subsystem: Web Push notification delivery
# // Description:
# //   Handles Web Push notification delivery using the pywebpush library.
# //   Manages subscription lifecycle, sends push notifications to user endpoints,
# //   and handles expired subscriptions automatically.
# //
# //   Delivery rules:
# //     - NOTIFICATIONS_ENABLED=False -> skip all push delivery, log action
# //     - Missing VAPID keys -> skip push, log warning
# //     - 410 Gone response -> delete expired subscription automatically
# //     - Retryable errors -> log in AuditEvent, continue without raising
# //
# //   Every push attempt writes an AuditEvent for auditability.
# // References: apps/core/services/notification_service.py (existing pattern)
# // ==============================================================================
"""

import hashlib
import json
import logging
from typing import Optional, Tuple

from django.conf import settings

from apps.core.models import AuditEvent, PushSubscription

logger = logging.getLogger(__name__)


class PushNotificationService:
    """
    Web Push notification delivery service.
    Handles push notification sending, subscription management, and error handling.
    """
    
    @staticmethod
    def send_push_notification(notification) -> Tuple[int, int]:
        """
        Send push notification to all active subscriptions for the notification's user.
        
        Args:
            notification: Notification model instance with user, title, message, category, link
        
        Returns:
            tuple: (successful_sends: int, failed_sends: int)
        """
        # Check if notifications are enabled
        if not getattr(settings, 'NOTIFICATIONS_ENABLED', True):
            AuditEvent.objects.create(
                actor=None,
                action='PUSH_NOTIFICATION_SKIPPED',
                object_type='Notification',
                object_id=str(notification.pk),
                reason='Notifications disabled in settings'
            )
            return 0, 0
        
        # Get VAPID keys
        vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', '')
        vapid_public_key = getattr(settings, 'VAPID_PUBLIC_KEY', '')
        vapid_admin_email = getattr(settings, 'VAPID_ADMIN_EMAIL', 'admin@classstamp.local')
        
        if not vapid_private_key or not vapid_public_key:
            logger.warning('VAPID keys not configured, skipping push notification')
            AuditEvent.objects.create(
                actor=None,
                action='PUSH_NOTIFICATION_SKIPPED',
                object_type='Notification',
                object_id=str(notification.pk),
                reason='VAPID keys not configured'
            )
            return 0, 0
        
        # Import pywebpush here to make the import optional if not installed
        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            logger.warning('pywebpush not installed, skipping push notification')
            AuditEvent.objects.create(
                actor=None,
                action='PUSH_NOTIFICATION_SKIPPED',
                object_type='Notification',
                object_id=str(notification.pk),
                reason='pywebpush library not installed'
            )
            return 0, 0
        
        # Get all active subscriptions for user
        subscriptions = PushSubscription.objects.filter(user=notification.user)
        
        if not subscriptions.exists():
            return 0, 0
        
        successful = 0
        failed = 0
        
        # Prepare push payload. `url` is top-level so the service worker's
        # click handler can use it directly; it also remains under `data` for
        # older clients (task 4.2 alignment).
        payload = json.dumps({
            'title': notification.title,
            'body': notification.message[:100],
            'icon': '/static/img/kcc_logo.png',
            'badge': '/static/img/kcc_logo.png',
            'tag': notification.category,
            'url': notification.link or '/dashboard/',
            'data': {
                'url': notification.link or '/dashboard/',
                'notification_id': str(notification.pk)
            }
        })
        
        # Send to each subscription
        for subscription in subscriptions:
            try:
                webpush(
                    subscription_info={
                        'endpoint': subscription.endpoint,
                        'keys': {
                            'p256dh': subscription.p256dh,
                            'auth': subscription.auth
                        }
                    },
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={
                        'sub': f'mailto:{vapid_admin_email}'
                    }
                )
                successful += 1
                
            except WebPushException as e:
                failed += 1
                
                # Handle 410 Gone (subscription expired)
                if e.response and e.response.status_code == 410:
                    # Capture the pk before delete() nulls it, so the audit
                    # event still identifies which subscription expired.
                    expired_pk = subscription.pk
                    subscription.delete()
                    logger.info(f'Deleted expired push subscription {expired_pk}')
                    AuditEvent.objects.create(
                        actor=None,
                        action='PUSH_SUBSCRIPTION_EXPIRED',
                        object_type='PushSubscription',
                        object_id=str(expired_pk),
                        reason='Subscription endpoint returned 410 Gone'
                    )
                else:
                    # Log other errors
                    AuditEvent.objects.create(
                        actor=None,
                        action='PUSH_NOTIFICATION_FAILED',
                        object_type='PushSubscription',
                        object_id=str(subscription.pk),
                        reason=f'WebPush error: {str(e)}'
                    )
            
            except Exception as e:
                failed += 1
                logger.error(f'Unexpected push notification error: {e}')
                AuditEvent.objects.create(
                    actor=None,
                    action='PUSH_NOTIFICATION_FAILED',
                    object_type='PushSubscription',
                    object_id=str(subscription.pk),
                    reason=f'Unexpected error: {str(e)}'
                )
        
        # Log overall result
        if successful > 0:
            AuditEvent.objects.create(
                actor=None,
                action='PUSH_NOTIFICATION_SENT',
                object_type='Notification',
                object_id=str(notification.pk),
                reason=f'Sent to {successful} subscription(s), {failed} failed'
            )
        
        return successful, failed
    
    @staticmethod
    def create_subscription(user, endpoint: str, p256dh: str, auth: str, user_agent: str = '') -> PushSubscription:
        """
        Create or update a push subscription for a user.
        Uses endpoint hash to prevent duplicates.
        
        Args:
            user: User model instance
            endpoint: Push subscription endpoint URL
            p256dh: Public key for encryption (base64)
            auth: Auth secret for encryption (base64)
            user_agent: Optional browser user agent string
        
        Returns:
            PushSubscription: Created or updated subscription instance
        """
        # Hash endpoint to create unique identifier
        endpoint_hash = hashlib.sha256(endpoint.encode('utf-8')).hexdigest()
        
        # Create or update subscription
        subscription, created = PushSubscription.objects.update_or_create(
            endpoint_hash=endpoint_hash,
            defaults={
                'user': user,
                'endpoint': endpoint,
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': user_agent[:500]
            }
        )
        
        # Log subscription action
        action = 'PUSH_SUBSCRIPTION_CREATED' if created else 'PUSH_SUBSCRIPTION_UPDATED'
        AuditEvent.objects.create(
            actor=user,
            action=action,
            object_type='PushSubscription',
            object_id=str(subscription.pk),
            reason=f'User agent: {user_agent[:100]}'
        )
        
        return subscription
    
    @staticmethod
    def delete_subscription(user, endpoint: str) -> bool:
        """
        Delete a push subscription for a user.
        
        Args:
            user: User model instance
            endpoint: Push subscription endpoint URL to delete
        
        Returns:
            bool: True if subscription was deleted, False if not found
        """
        # Hash endpoint to find subscription
        endpoint_hash = hashlib.sha256(endpoint.encode('utf-8')).hexdigest()
        
        try:
            subscription = PushSubscription.objects.get(user=user, endpoint_hash=endpoint_hash)
            subscription_pk = subscription.pk
            subscription.delete()
            
            # Log deletion
            AuditEvent.objects.create(
                actor=user,
                action='PUSH_SUBSCRIPTION_DELETED',
                object_type='PushSubscription',
                object_id=str(subscription_pk),
                reason='User requested unsubscribe'
            )
            
            return True
        except PushSubscription.DoesNotExist:
            return False
    
    @staticmethod
    def get_user_subscriptions(user) -> 'models.QuerySet':
        """
        Get all active push subscriptions for a user.
        
        Args:
            user: User model instance
        
        Returns:
            QuerySet: PushSubscription queryset for the user
        """
        return PushSubscription.objects.filter(user=user)
    
    @staticmethod
    def cleanup_expired_subscriptions() -> int:
        """
        Manual cleanup of expired subscriptions (can be called from management command).
        This is a fallback - most expired subscriptions are cleaned up automatically
        when they return 410 Gone during push delivery.
        
        Returns:
            int: Number of subscriptions cleaned up
        """
        # For now, this is a placeholder since cleanup happens automatically on 410 responses
        # In the future, this could implement additional cleanup logic like:
        # - Remove subscriptions older than X months with no successful delivery
        # - Remove subscriptions for inactive users
        return 0
