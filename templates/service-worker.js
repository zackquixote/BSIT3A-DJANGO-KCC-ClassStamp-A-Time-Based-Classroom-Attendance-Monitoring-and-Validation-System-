'use strict';

const CACHE_NAME = 'classstamp-offline-v1';
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
