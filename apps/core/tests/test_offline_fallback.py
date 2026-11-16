from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class OfflineFallbackTests(TestCase):
    def test_service_worker_handles_fetch_for_installability(self):
        # Chrome only offers "Install app" — and only fires beforeinstallprompt —
        # when a service worker listens for fetch. The handler is a plain network
        # passthrough, so it adds no caching and no stale pages; without it the
        # install prompt never appeared on phones.
        response = self.client.get(reverse('service_worker'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/javascript')
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        content = response.content.decode()
        self.assertIn("addEventListener('fetch'", content)
        self.assertIn('respondWith(fetch(event.request))', content)
        self.assertIn("addEventListener('push'", content)

    def test_offline_page_is_a_self_contained_static_asset(self):
        offline_page = finders.find('offline.html')

        self.assertIsNotNone(offline_page)
        content = Path(offline_page).read_text(encoding='utf-8')
        self.assertIn('ClassStamp is temporarily unavailable', content)
        self.assertIn('Attendance and other changes cannot be confirmed', content)

    def test_shared_layout_registers_offline_fallback(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js/core/service_worker.js')
