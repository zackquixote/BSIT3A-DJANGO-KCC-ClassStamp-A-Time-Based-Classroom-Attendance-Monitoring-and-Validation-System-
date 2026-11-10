from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class OfflineFallbackTests(TestCase):
    def test_service_worker_is_served_without_noop_fetch_handler(self):
        response = self.client.get(reverse('service_worker'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/javascript')
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        content = response.content.decode()
        self.assertNotIn("addEventListener('fetch'", content)
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
