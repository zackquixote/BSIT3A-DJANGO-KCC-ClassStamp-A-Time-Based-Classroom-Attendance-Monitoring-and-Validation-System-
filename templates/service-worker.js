'use strict';

const CACHE_NAME = 'classstamp-offline-v2';
const OFFLINE_URL = '/static/offline.html';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.add(OFFLINE_URL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith('classstamp-offline-') && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate') return;

  const requestUrl = new URL(request.url);
  if (requestUrl.origin !== self.location.origin) return;

  event.respondWith(
    fetch(request).then((response) => {
      if (response.status >= 500) {
        return caches.match(OFFLINE_URL).then((offlinePage) => offlinePage || response);
      }
      return response;
    }).catch(() => caches.match(OFFLINE_URL))
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
  const options = {
    body: payload.body || '',
    icon: payload.icon || '/static/img/kcc_logo.png',
    badge: payload.badge || '/static/img/kcc_logo.png',
    data: { url: payload.url || '/dashboard/' },
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
