(function () {
  'use strict';

  const publicKey = document.querySelector('meta[name="web-push-public-key"]')?.content;
  const supported = Boolean(
    publicKey &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return (input && input.value) || '';
  }

  function base64UrlToUint8Array(value) {
    const padding = '='.repeat((4 - value.length % 4) % 4);
    const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = window.atob(base64);
    return Uint8Array.from([...raw].map(character => character.charCodeAt(0)));
  }

  function toggleButton() {
    return document.querySelector('[data-push-toggle]');
  }

  async function currentSubscription() {
    if (!supported) return null;
    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) return null;
    try {
      return await registration.pushManager.getSubscription();
    } catch (error) {
      return null;
    }
  }

  async function paint() {
    const button = toggleButton();
    if (!button) return;
    if (!supported) {
      button.textContent = 'Push not supported';
      button.disabled = true;
      button.dataset.pushState = 'unsupported';
      return;
    }
    if (Notification.permission === 'denied') {
      button.textContent = 'Push blocked by browser';
      button.disabled = true;
      button.dataset.pushState = 'blocked';
      return;
    }
    const subscription = await currentSubscription();
    if (subscription) {
      button.textContent = 'Push notifications: ON';
      button.dataset.pushState = 'on';
    } else {
      button.textContent = 'Enable push notifications';
      button.dataset.pushState = 'off';
    }
    button.disabled = false;
  }

  async function enablePushNotifications() {
    if (!supported) return false;
    if (Notification.permission === 'denied') {
      await paint();
      return false;
    }
    const permission = Notification.permission === 'granted'
      ? 'granted'
      : await Notification.requestPermission();
    if (permission !== 'granted') {
      await paint();
      return false;
    }
    const registration = await navigator.serviceWorker.ready;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlToUint8Array(publicKey),
      });
    }
    const response = await fetch('/api/push/subscribe/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify({ subscription: subscription.toJSON() }),
    });
    await paint();
    return response.ok;
  }

  async function disablePushNotifications() {
    const registration = await navigator.serviceWorker.getRegistration();
    const subscription = registration
      ? await registration.pushManager.getSubscription()
      : null;
    if (subscription) {
      const endpoint = subscription.endpoint;
      try {
        await subscription.unsubscribe();
      } catch (error) {
        // Still tell the server so the row is cleaned up.
      }
      await fetch('/api/push/unsubscribe/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          'X-CSRFToken': csrfToken(),
        },
        body: 'endpoint=' + encodeURIComponent(endpoint),
      });
    }
    await paint();
  }

  // Existing integration point: other UI may dispatch this event.
  document.addEventListener('classstamp:enable-push', enablePushNotifications);

  // Visible enable/status/unsubscribe control (task 4.3).
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-push-toggle]');
    if (!button) return;
    event.preventDefault();
    if (button.dataset.pushState === 'on') {
      disablePushNotifications();
    } else if (button.dataset.pushState === 'off') {
      enablePushNotifications();
    }
  });

  document.addEventListener('DOMContentLoaded', paint);
})();
