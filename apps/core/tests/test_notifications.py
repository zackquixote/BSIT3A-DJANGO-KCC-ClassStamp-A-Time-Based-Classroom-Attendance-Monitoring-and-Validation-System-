"""
# // ==============================================================================
# // KCC CLASSSTAMP - NOTIFICATION SERVICE TESTS
# // ==============================================================================
# // Delivery, skip paths, audit trail, and the at-risk mailer command.
# // The test runner swaps in the locmem email backend, so mail.outbox is the
# // assertion surface.
# ==============================================================================
"""

from datetime import date, time
from io import StringIO
import json
import sys
import types
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AcademicYear,
    AttendanceRecord,
    AuditEvent,
    Class,
    ClassSession,
    ClassSlot,
    Department,
    Enrollment,
    ExcuseSlip,
    Profile,
    Notification,
    Program,
    Subject,
)
from apps.core.services.notification_service import (
    notify_at_risk,
    notify_excuse_decision,
    notify_user,
)
from apps.core.services.in_app_notification_service import (
    create_notification,
    notify_absent_students,
)

User = get_user_model()


class FakeWebPushException(Exception):
    """Stand-in for pywebpush.WebPushException carrying an HTTP-style response."""

    def __init__(self, message='', response=None):
        super().__init__(message)
        self.response = response


def make_fake_pywebpush(webpush_mock):
    """
    Build an importable fake ``pywebpush`` module backed by ``webpush_mock``.

    PushNotificationService imports ``webpush`` and ``WebPushException`` inside
    its delivery method, so tests inject this module through ``sys.modules``
    (patch.dict) instead of patching a module-level attribute on the service.
    This works whether or not the real library is installed.
    """
    module = types.ModuleType('pywebpush')
    module.WebPushException = FakeWebPushException
    module.webpush = webpush_mock
    return module


class NotifyUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='notify_user', email='student@example.com', first_name='Ana',
        )

    def test_sends_and_audits(self):
        delivered = notify_user(self.user, 'Subject line', 'Body text')

        self.assertTrue(delivered)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student@example.com'])
        self.assertTrue(AuditEvent.objects.filter(action='NOTIFICATION_SENT').exists())

    def test_missing_address_is_skipped_and_recorded(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])

        delivered = notify_user(self.user, 'Subject line', 'Body text')

        self.assertFalse(delivered)
        self.assertEqual(len(mail.outbox), 0)
        event = AuditEvent.objects.get(action='NOTIFICATION_SENT')
        self.assertIn('no email address', event.reason)

    @override_settings(NOTIFICATIONS_ENABLED=False)
    def test_disabled_switch_sends_nothing(self):
        delivered = notify_user(self.user, 'Subject line', 'Body text')

        self.assertFalse(delivered)
        self.assertEqual(len(mail.outbox), 0)

    def test_none_user_is_a_noop(self):
        self.assertFalse(notify_user(None, 'Subject', 'Body'))


class ExcuseDecisionNotificationTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='exc_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.student_user = User.objects.create_user(
            username='exc_student', email='ana@example.com', first_name='Ana',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-6001',
            program=self.program,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        self.session = ClassSession.objects.create(
            slot=slot, session_date=today, status=ClassSession.STATUS_CLOSED,
        )
        AttendanceRecord.objects.create(
            session=self.session, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_ABSENT,
            method=AttendanceRecord.METHOD_SYSTEM,
        )
        self.slip = ExcuseSlip.objects.create(
            student_profile=self.student_profile,
            session=self.session,
            reason='Medical appointment',
        )

    def test_approval_notifies_the_student(self):
        notify_excuse_decision(self.slip, approved=True)

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('BSIT-1A', body)
        self.assertIn('APPROVED', body)

    def test_rejection_includes_the_reviewer_note(self):
        notify_excuse_decision(self.slip, approved=False, note='No supporting document')

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('REJECTED', mail.outbox[0].body)
        self.assertIn('No supporting document', mail.outbox[0].body)

    def test_auto_absence_creates_student_notification(self):
        notify_absent_students(
            [self.student_profile],
            self.class_obj,
            self.session.session_date,
        )

        notification = Notification.objects.get(user=self.student_user)
        self.assertEqual(notification.category, 'attendance')
        self.assertIn('marked absent', notification.message)


class AtRiskMailerTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(code='CCS', name='College of Computer Studies')
        self.program = Program.objects.create(
            department=self.department, code='BSIT', name='BS Information Technology',
        )
        self.subject = Subject.objects.create(code='IT101', name='Introduction to Computing')
        self.year = AcademicYear.objects.create(
            name='2025-2026', starts_on=date(2025, 6, 1), ends_on=date(2026, 3, 31),
            is_active=True,
        )
        self.teacher_user = User.objects.create_user(username='risk_teacher')
        self.teacher_profile = Profile.objects.create(
            user=self.teacher_user, role=Profile.ROLE_TEACHER, department=self.department,
        )
        self.student_user = User.objects.create_user(
            username='risk_student', email='risk@example.com', first_name='Ben',
        )
        self.student_profile = Profile.objects.create(
            user=self.student_user,
            role=Profile.ROLE_STUDENT,
            student_number='2026-7001',
            program=self.program,
            approval_status=Profile.APPROVAL_APPROVED,
        )
        self.class_obj = Class.objects.create(
            academic_year=self.year, class_code='BSIT-1A',
            subject=self.subject, teacher_profile=self.teacher_profile,
        )
        today = timezone.localdate()
        slot = ClassSlot.objects.create(
            class_obj=self.class_obj, weekday=today.weekday(),
            starts_at=time(8, 0), ends_at=time(9, 0), room='Room 1',
        )
        session = ClassSession.objects.create(
            slot=slot, session_date=today, status=ClassSession.STATUS_CLOSED,
        )
        Enrollment.objects.create(
            student_profile=self.student_profile, class_obj=self.class_obj,
            status=Enrollment.STATUS_ACTIVE,
        )
        AttendanceRecord.objects.create(
            session=session, student_profile=self.student_profile,
            status=AttendanceRecord.STATUS_ABSENT,
            method=AttendanceRecord.METHOD_SYSTEM,
        )

    def test_dry_run_sends_nothing(self):
        out = StringIO()
        call_command('notify_at_risk', '--dry-run', stdout=out)

        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('DRY-RUN', out.getvalue())

    def test_real_run_mails_at_risk_students(self):
        out = StringIO()
        call_command('notify_at_risk', stdout=out)

        # The fixture teacher has no email address, so only the student mails.
        # Teacher delivery is covered in test_at_risk_workflow.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('BSIT-1A', mail.outbox[0].body)
        self.assertIn('Emailed 1', out.getvalue())

    def test_student_below_threshold_is_not_mailed(self):
        call_command('notify_at_risk', '--threshold', '150', stdout=StringIO())

        self.assertEqual(len(mail.outbox), 0)

    def test_direct_notify_helper(self):
        delivered = notify_at_risk(self.student_profile, self.class_obj, 100.0, 20)

        self.assertTrue(delivered)
        self.assertIn('100.0%', mail.outbox[0].body)


class InAppNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student-notify', password='test-pass')
        self.other_user = User.objects.create_user(username='other-notify', password='test-pass')
        self.client.force_login(self.user)

    def test_notification_list_is_scoped_to_logged_in_user(self):
        own = Notification.objects.create(
            user=self.user,
            category='attendance',
            title='Attendance recorded',
            message='Your attendance was recorded.',
        )
        Notification.objects.create(
            user=self.other_user,
            category='attendance',
            title='Private update',
            message='This belongs to another user.',
        )

        response = self.client.get(reverse('notification_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own.title)
        self.assertNotContains(response, 'Private update')
        # Used to assert that no 'href="/notifications/"' appears in the page, as a
        # stand-in for "a row with no link must not become an anchor". The sidebar
        # bell is now a real link to that same URL, so the string check is no longer
        # about scoping. Assert the scoping directly instead.
        self.assertEqual({row.pk for row in response.context['notifications']}, {own.pk})

    def test_mark_read_requires_ownership_and_redirects_to_internal_link(self):
        notification = Notification.objects.create(
            user=self.user,
            category='enrollment',
            title='Class approved',
            message='You are enrolled.',
            link='/student/dashboard/',
        )
        other_notification = Notification.objects.create(
            user=self.other_user,
            category='enrollment',
            title='Other user',
            message='Private.',
        )

        response = self.client.post(
            reverse('notification_mark_read', args=[notification.pk]),
        )
        self.assertRedirects(response, '/student/dashboard/', fetch_redirect_response=False)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

        denied = self.client.post(
            reverse('notification_mark_read', args=[other_notification.pk]),
        )
        self.assertEqual(denied.status_code, 404)

    def test_mark_all_read_only_updates_current_user_notifications(self):
        own = Notification.objects.create(
            user=self.user,
            category='attendance',
            title='Own',
            message='Own notification.',
        )
        other = Notification.objects.create(
            user=self.other_user,
            category='attendance',
            title='Other',
            message='Other notification.',
        )

        response = self.client.post(reverse('notification_mark_all_read'))

        self.assertRedirects(response, reverse('notification_list'), fetch_redirect_response=False)
        own.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(own.read_at)
        self.assertIsNone(other.read_at)

    def test_notification_service_rejects_external_redirect_links(self):
        notification = create_notification(
            self.user,
            'class_assignment',
            'Class assigned',
            'A section was assigned.',
            'https://example.com/',
        )

        self.assertEqual(notification.link, '')

    def test_create_notification_queues_web_push_after_commit(self):
        """Task 4.2: in-app creation must also queue Web Push delivery."""
        from unittest.mock import patch

        with patch(
            'apps.core.services.push_notification_service.'
            'PushNotificationService.send_push_notification'
        ) as send_mock:
            with self.captureOnCommitCallbacks(execute=True):
                notification = create_notification(
                    self.user,
                    'class_assignment',
                    'Class assigned',
                    'A section was assigned.',
                    '/student/dashboard/',
                )

        self.assertIsNotNone(notification)
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(send_mock.call_args[0][0].pk, notification.pk)

    def test_create_notification_push_failure_does_not_raise(self):
        from unittest.mock import patch

        with patch(
            'apps.core.services.push_notification_service.'
            'PushNotificationService.send_push_notification',
            side_effect=RuntimeError('boom'),
        ):
            # on_commit runs immediately outside a transaction; a dead push
            # path must not break notification creation.
            notification = create_notification(
                self.user,
                'class_assignment',
                'Class assigned',
                'A section was assigned.',
            )
        self.assertIsNotNone(notification)



class PushNotificationServiceTests(TestCase):
    """
    Test suite for PushNotificationService.
    Tests subscription creation, push delivery, error handling, and expired subscription cleanup.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='push_user',
            email='push@example.com',
            first_name='Push',
            last_name='User'
        )
        self.notification = Notification.objects.create(
            user=self.user,
            category='attendance',
            title='Test Notification',
            message='This is a test push notification',
            link='/student/dashboard/'
        )

    def test_subscription_creation_with_endpoint_hashing(self):
        """Test that subscriptions are created with hashed endpoints to prevent duplicates"""
        from apps.core.services.push_notification_service import PushNotificationService

        endpoint = 'https://fcm.googleapis.com/fcm/send/test123'
        p256dh = 'BKj3lMPnZQ1F7s4f5g6h7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4='
        auth = 'A1B2C3D4E5F6G7H8I9J0K1L2='
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

        subscription = PushNotificationService.create_subscription(
            self.user,
            endpoint,
            p256dh,
            auth,
            user_agent
        )

        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.endpoint, endpoint)
        self.assertEqual(subscription.p256dh, p256dh)
        self.assertEqual(subscription.auth, auth)
        self.assertEqual(subscription.user_agent, user_agent)
        self.assertTrue(len(subscription.endpoint_hash) == 64)  # SHA256 hash is 64 chars

        # Verify audit event was created
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_SUBSCRIPTION_CREATED',
                object_type='PushSubscription'
            ).exists()
        )

    def test_subscription_update_when_endpoint_exists(self):
        """Test that creating a subscription with same endpoint updates existing one"""
        from apps.core.services.push_notification_service import PushNotificationService
        from apps.core.models import PushSubscription

        endpoint = 'https://fcm.googleapis.com/fcm/send/test456'
        p256dh_old = 'OLD_KEY_123='
        p256dh_new = 'NEW_KEY_456='
        auth = 'AUTH_SECRET='

        # Create first subscription
        sub1 = PushNotificationService.create_subscription(
            self.user,
            endpoint,
            p256dh_old,
            auth
        )

        # Create second subscription with same endpoint but different keys
        sub2 = PushNotificationService.create_subscription(
            self.user,
            endpoint,
            p256dh_new,
            auth
        )

        # Should be same subscription, just updated
        self.assertEqual(sub1.pk, sub2.pk)
        self.assertEqual(sub2.p256dh, p256dh_new)

        # Should only have one subscription for this endpoint
        self.assertEqual(PushSubscription.objects.filter(endpoint=endpoint).count(), 1)

        # Verify update audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_SUBSCRIPTION_UPDATED',
                object_type='PushSubscription'
            ).exists()
        )

    def test_subscription_deletion(self):
        """Test that subscriptions can be deleted by endpoint"""
        from apps.core.services.push_notification_service import PushNotificationService
        from apps.core.models import PushSubscription

        endpoint = 'https://fcm.googleapis.com/fcm/send/delete_test'
        p256dh = 'DELETE_KEY='
        auth = 'AUTH='

        # Create subscription
        subscription = PushNotificationService.create_subscription(
            self.user,
            endpoint,
            p256dh,
            auth
        )
        sub_pk = subscription.pk

        # Delete subscription
        result = PushNotificationService.delete_subscription(self.user, endpoint)

        self.assertTrue(result)
        self.assertFalse(PushSubscription.objects.filter(pk=sub_pk).exists())

        # Verify deletion audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_SUBSCRIPTION_DELETED',
                object_type='PushSubscription',
                object_id=str(sub_pk)
            ).exists()
        )

    def test_subscription_deletion_returns_false_when_not_found(self):
        """Test that deleting non-existent subscription returns False"""
        from apps.core.services.push_notification_service import PushNotificationService

        result = PushNotificationService.delete_subscription(
            self.user,
            'https://fcm.googleapis.com/fcm/send/nonexistent'
        )

        self.assertFalse(result)

    @override_settings(NOTIFICATIONS_ENABLED=False)
    def test_push_sending_skipped_when_disabled(self):
        """Test that push notifications are skipped when NOTIFICATIONS_ENABLED is False"""
        from apps.core.services.push_notification_service import PushNotificationService

        successful, failed = PushNotificationService.send_push_notification(self.notification)

        self.assertEqual(successful, 0)
        self.assertEqual(failed, 0)

        # Verify skip audit event
        event = AuditEvent.objects.filter(
            action='PUSH_NOTIFICATION_SKIPPED',
            object_type='Notification',
            object_id=str(self.notification.pk)
        ).first()
        self.assertIsNotNone(event)
        self.assertIn('disabled', event.reason.lower())

    @override_settings(VAPID_PRIVATE_KEY='', VAPID_PUBLIC_KEY='')
    def test_push_sending_skipped_when_vapid_not_configured(self):
        """Test that push notifications are skipped when VAPID keys are not configured"""
        from apps.core.services.push_notification_service import PushNotificationService

        successful, failed = PushNotificationService.send_push_notification(self.notification)

        self.assertEqual(successful, 0)
        self.assertEqual(failed, 0)

        # Verify skip audit event
        event = AuditEvent.objects.filter(
            action='PUSH_NOTIFICATION_SKIPPED',
            object_type='Notification',
            object_id=str(self.notification.pk)
        ).first()
        self.assertIsNotNone(event)
        self.assertIn('VAPID', event.reason)

    def test_push_sending_returns_zero_when_no_subscriptions(self):
        """Test that push sending returns (0, 0) when user has no subscriptions"""
        from apps.core.services.push_notification_service import PushNotificationService

        # Ensure no subscriptions exist
        successful, failed = PushNotificationService.send_push_notification(self.notification)

        self.assertEqual(successful, 0)
        self.assertEqual(failed, 0)

    @override_settings(
        VAPID_PRIVATE_KEY='test_private_key',
        VAPID_PUBLIC_KEY='test_public_key',
        VAPID_ADMIN_EMAIL='admin@test.local'
    )
    def test_push_sending_with_mock_success(self):
        """Test successful push notification delivery (mocked)"""
        from apps.core.services.push_notification_service import PushNotificationService
        from apps.core.models import PushSubscription
        from unittest.mock import patch, MagicMock

        # Create subscription
        subscription = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/mock_success',
            endpoint_hash='mock_hash_123',
            p256dh='MOCK_P256DH=',
            auth='MOCK_AUTH='
        )

        # Mock pywebpush by injecting a fake module into sys.modules: the
        # service imports webpush/WebPushException inside its delivery method.
        mock_webpush = MagicMock()
        fake_pywebpush = make_fake_pywebpush(mock_webpush)

        with patch.dict(sys.modules, {'pywebpush': fake_pywebpush}):
            successful, failed = PushNotificationService.send_push_notification(self.notification)

            self.assertEqual(successful, 1)
            self.assertEqual(failed, 0)

            # Verify webpush was called with correct parameters
            mock_webpush.assert_called_once()
            call_args = mock_webpush.call_args
            self.assertEqual(call_args[1]['subscription_info']['endpoint'], subscription.endpoint)
            self.assertIn('title', call_args[1]['data'])
            self.assertEqual(call_args[1]['vapid_private_key'], 'test_private_key')

        # Verify success audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_NOTIFICATION_SENT',
                object_type='Notification',
                object_id=str(self.notification.pk)
            ).exists()
        )

    @override_settings(
        VAPID_PRIVATE_KEY='test_private_key',
        VAPID_PUBLIC_KEY='test_public_key'
    )
    def test_push_sending_handles_410_gone_by_deleting_subscription(self):
        """Test that 410 Gone responses delete expired subscriptions"""
        from apps.core.services.push_notification_service import PushNotificationService
        from apps.core.models import PushSubscription
        from unittest.mock import patch, MagicMock

        # Create subscription
        subscription = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/expired',
            endpoint_hash='expired_hash_456',
            p256dh='EXPIRED_P256DH=',
            auth='EXPIRED_AUTH='
        )
        sub_pk = subscription.pk

        # Mock pywebpush to raise a 410 Gone WebPushException
        mock_webpush = MagicMock()
        gone_response = MagicMock()
        gone_response.status_code = 410
        mock_webpush.side_effect = FakeWebPushException('410 Gone', response=gone_response)
        fake_pywebpush = make_fake_pywebpush(mock_webpush)

        with patch.dict(sys.modules, {'pywebpush': fake_pywebpush}):
            successful, failed = PushNotificationService.send_push_notification(self.notification)

            self.assertEqual(successful, 0)
            self.assertEqual(failed, 1)

        # Verify subscription was deleted
        self.assertFalse(PushSubscription.objects.filter(pk=sub_pk).exists())

        # Verify expired subscription audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_SUBSCRIPTION_EXPIRED',
                object_type='PushSubscription',
                object_id=str(sub_pk)
            ).exists()
        )

    @override_settings(
        VAPID_PRIVATE_KEY='test_private_key',
        VAPID_PUBLIC_KEY='test_public_key'
    )
    def test_push_sending_logs_retryable_errors_without_raising(self):
        """Test that retryable errors are logged but don't raise exceptions"""
        from apps.core.services.push_notification_service import PushNotificationService
        from apps.core.models import PushSubscription
        from unittest.mock import patch, MagicMock

        # Create subscription
        subscription = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/error',
            endpoint_hash='error_hash_789',
            p256dh='ERROR_P256DH=',
            auth='ERROR_AUTH='
        )

        # Mock pywebpush to raise a retryable (non-410) WebPushException
        mock_webpush = MagicMock()
        error_response = MagicMock()
        error_response.status_code = 500
        mock_webpush.side_effect = FakeWebPushException('500 Internal Server Error', response=error_response)
        fake_pywebpush = make_fake_pywebpush(mock_webpush)

        with patch.dict(sys.modules, {'pywebpush': fake_pywebpush}):
            # Should not raise exception
            successful, failed = PushNotificationService.send_push_notification(self.notification)

            self.assertEqual(successful, 0)
            self.assertEqual(failed, 1)

        # Verify subscription still exists (not deleted on non-410 errors)
        self.assertTrue(PushSubscription.objects.filter(pk=subscription.pk).exists())

        # Verify failure audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_NOTIFICATION_FAILED',
                object_type='PushSubscription',
                object_id=str(subscription.pk)
            ).exists()
        )

    def test_get_user_subscriptions(self):
        """Test retrieving all subscriptions for a user"""
        from apps.core.services.push_notification_service import PushNotificationService
        from apps.core.models import PushSubscription

        # Create multiple subscriptions
        other_user = User.objects.create_user(username='other_push_user')

        sub1 = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/sub1',
            endpoint_hash='hash1',
            p256dh='KEY1=',
            auth='AUTH1='
        )
        sub2 = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/sub2',
            endpoint_hash='hash2',
            p256dh='KEY2=',
            auth='AUTH2='
        )
        PushSubscription.objects.create(
            user=other_user,
            endpoint='https://fcm.googleapis.com/fcm/send/other',
            endpoint_hash='other_hash',
            p256dh='OTHER_KEY=',
            auth='OTHER_AUTH='
        )

        # Get subscriptions for self.user
        subscriptions = PushNotificationService.get_user_subscriptions(self.user)

        self.assertEqual(subscriptions.count(), 2)
        self.assertIn(sub1, subscriptions)
        self.assertIn(sub2, subscriptions)

    def test_push_payload_structure(self):
        """Test that push notification payload has correct structure"""
        from apps.core.services.push_notification_service import PushNotificationService
        from apps.core.models import PushSubscription
        from unittest.mock import patch
        import json

        # Create subscription
        PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/payload_test',
            endpoint_hash='payload_hash',
            p256dh='PAYLOAD_P256DH=',
            auth='PAYLOAD_AUTH='
        )

        mock_webpush = MagicMock()
        fake_pywebpush = make_fake_pywebpush(mock_webpush)

        with patch.dict(sys.modules, {'pywebpush': fake_pywebpush}):
            with override_settings(
                VAPID_PRIVATE_KEY='key',
                VAPID_PUBLIC_KEY='key'
            ):
                PushNotificationService.send_push_notification(self.notification)

        # Extract payload from call
        mock_webpush.assert_called_once()
        call_args = mock_webpush.call_args
        payload_str = call_args[1]['data']
        payload = json.loads(payload_str)

        # Verify payload structure
        self.assertEqual(payload['title'], 'Test Notification')
        self.assertIn('This is a test', payload['body'])
        self.assertEqual(payload['tag'], 'attendance')
        # Task 4.2: URL is top-level for the worker click handler, and also
        # nested under data for older clients.
        self.assertEqual(payload['url'], '/student/dashboard/')
        self.assertEqual(payload['data']['url'], '/student/dashboard/')
        self.assertEqual(payload['data']['notification_id'], str(self.notification.pk))
        self.assertEqual(payload['icon'], '/static/img/kcc_logo.png')
        self.assertEqual(payload['badge'], '/static/img/kcc_logo.png')


class PushSubscriptionEndpointTests(TestCase):
    """
    Task 4.3: subscribe/unsubscribe HTTP endpoints must reuse
    PushNotificationService so auditing stays consistent.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='push_view_user')
        self.client.force_login(self.user)

    def _subscribe(self, endpoint='https://fcm.googleapis.com/fcm/send/abc'):
        return self.client.post(
            reverse('push_subscription_save'),
            data=json.dumps({
                'subscription': {
                    'endpoint': endpoint,
                    'keys': {'p256dh': 'P256DH=', 'auth': 'AUTH='},
                }
            }),
            content_type='application/json',
        )

    def test_subscribe_creates_subscription_and_audits(self):
        response = self._subscribe()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_SUBSCRIPTION_CREATED',
                actor=self.user,
            ).exists()
        )
        from apps.core.models import PushSubscription
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 1)

    def test_duplicate_subscribe_updates_not_duplicates(self):
        self._subscribe()
        response = self._subscribe()
        self.assertEqual(response.status_code, 200)
        from apps.core.models import PushSubscription
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_SUBSCRIPTION_UPDATED',
                actor=self.user,
            ).exists()
        )

    def test_unsubscribe_deletes_and_audits(self):
        self._subscribe()
        response = self.client.post(
            reverse('push_subscription_delete'),
            {'endpoint': 'https://fcm.googleapis.com/fcm/send/abc'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['deleted'])
        self.assertTrue(
            AuditEvent.objects.filter(
                action='PUSH_SUBSCRIPTION_DELETED',
                actor=self.user,
            ).exists()
        )
        from apps.core.models import PushSubscription
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 0)

    def test_unsubscribe_missing_endpoint_is_400(self):
        response = self.client.post(reverse('push_subscription_delete'), {'endpoint': ''})
        self.assertEqual(response.status_code, 400)

    def test_subscribe_requires_login(self):
        self.client.logout()
        response = self._subscribe()
        self.assertEqual(response.status_code, 302)
