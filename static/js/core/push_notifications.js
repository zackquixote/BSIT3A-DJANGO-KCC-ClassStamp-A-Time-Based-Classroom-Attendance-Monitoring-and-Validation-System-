(function () {
  'use strict';

  const publicKey = document.querySelector('meta[name="web-push-public-key"]')?.content;
  if (!publicKey || !('serviceWorker' in navigator) || !('PushManager' in window)) return;

  function base64UrlToUint8Array(value) {
    const padding = '='.repeat((4 - value.length % 4) % 4);
    const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = window.atob(base64);
    return Uint8Array.from([...raw].map(character => character.charCodeAt(0)));
  }

  async function enablePushNotifications() {
    if (Notification.permission === 'denied') return false;
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return false;
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
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
      body: JSON.stringify({subscription: subscription.toJSON()}),
    });
    return response.ok;
  }

  document.addEventListener('classstamp:enable-push', enablePushNotifications);
})();
