'use strict';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (error) {
    payload = { title: 'ClassStamp', body: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'ClassStamp';
  const targetUrl = payload.url || (payload.data && payload.data.url) || '/dashboard/';
  const options = {
    body: payload.body || '',
    icon: payload.icon || '/static/img/kcc_logo.png',
    badge: payload.badge || '/static/img/kcc_logo.png',
    data: { url: targetUrl },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = event.notification.data && event.notification.data.url
    ? event.notification.data.url
    : '/dashboard/';
  event.waitUntil(clients.openWindow(target));
});
