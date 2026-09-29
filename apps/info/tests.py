from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.info.models import Info


class InfoViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='secret123')
        self.client.force_login(self.user)
        self.record = Info.objects.create(
            name='Jane Doe',
            age=21,
            address='123 Main St',
            email='jane@example.com',
            user=self.user,
        )

    def test_info_list_requires_login(self):
        self.client.logout()
        response = self.client.get('/info/')
        self.assertEqual(response.status_code, 302)

    def test_info_list_renders(self):
        response = self.client.get('/info/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jane Doe')

    def test_info_list_search_filters_records(self):
        response = self.client.get('/info/', {'q': 'Main St'})
        self.assertContains(response, 'Jane Doe')

        response = self.client.get('/info/', {'q': 'nobody-here'})
        self.assertNotContains(response, 'Jane Doe')

    def test_info_list_hides_records_from_other_users(self):
        other = get_user_model().objects.create_user(username='other', password='secret123')
        Info.objects.create(name='Hidden Person', age=30, address='Elsewhere', user=other)

        response = self.client.get('/info/')
        self.assertNotContains(response, 'Hidden Person')

    def test_info_list_ajax_returns_pagination_envelope(self):
        response = self.client.get('/info/ajax/list/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['page'], 1)
        self.assertEqual(payload['data'][0]['name'], 'Jane Doe')

    def test_info_get_ajax_returns_record(self):
        response = self.client.get(reverse('info:info_get_ajax', args=[self.record.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['address'], '123 Main St')

    def test_info_get_ajax_404s_for_other_users(self):
        other = get_user_model().objects.create_user(username='other', password='secret123')
        foreign = Info.objects.create(name='Hidden Person', age=30, address='Elsewhere', user=other)

        response = self.client.get(reverse('info:info_get_ajax', args=[foreign.id]))
        self.assertEqual(response.status_code, 404)

    def test_save_requires_login(self):
        self.client.logout()
        response = self.client.post('/info/ajax/save/', {'name': 'Anon', 'age': '20', 'address': 'Nowhere'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Info.objects.filter(name='Anon').count(), 0)

    def test_save_creates_record_owned_by_request_user(self):
        response = self.client.post('/info/ajax/save/', {
            'name': 'John Doe',
            'age': '25',
            'address': '456 Side St',
            'email': 'john@example.com',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        created = Info.objects.get(name='John Doe')
        self.assertEqual(created.age, 25)
        self.assertEqual(created.user, self.user)

    def test_save_updates_existing_record(self):
        response = self.client.post('/info/ajax/save/', {
            'id': str(self.record.id),
            'name': 'Jane Smith',
            'age': '22',
            'address': '789 New St',
            'email': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Info.objects.filter(pk=self.record.pk).count(), 1)

        self.record.refresh_from_db()
        self.assertEqual(self.record.name, 'Jane Smith')
        self.assertEqual(self.record.age, 22)
        self.assertEqual(self.record.email, '')

    def test_save_rejects_missing_fields(self):
        response = self.client.post('/info/ajax/save/', {'age': '20', 'address': 'Nowhere'})
        self.assertEqual(response.status_code, 400)

        response = self.client.post('/info/ajax/save/', {'name': 'No Age', 'address': 'Nowhere'})
        self.assertEqual(response.status_code, 400)

        response = self.client.post('/info/ajax/save/', {'name': 'No Address', 'age': '20'})
        self.assertEqual(response.status_code, 400)

    def test_save_rejects_invalid_age(self):
        response = self.client.post('/info/ajax/save/', {'name': 'Bad Age', 'age': 'abc', 'address': 'Nowhere'})
        self.assertEqual(response.status_code, 400)

        response = self.client.post('/info/ajax/save/', {'name': 'Old', 'age': '500', 'address': 'Nowhere'})
        self.assertEqual(response.status_code, 400)

    def test_save_rejects_invalid_email(self):
        response = self.client.post('/info/ajax/save/', {
            'name': 'Bad Email',
            'age': '20',
            'address': 'Nowhere',
            'email': 'not-an-email',
        })
        self.assertEqual(response.status_code, 400)

    def test_delete_removes_record(self):
        response = self.client.post(reverse('info:info_delete_ajax', args=[self.record.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'deleted')
        self.assertEqual(Info.objects.filter(pk=self.record.pk).count(), 0)

    def test_delete_404s_for_other_users(self):
        other = get_user_model().objects.create_user(username='other', password='secret123')
        foreign = Info.objects.create(name='Hidden Person', age=30, address='Elsewhere', user=other)

        response = self.client.post(reverse('info:info_delete_ajax', args=[foreign.id]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Info.objects.filter(pk=foreign.pk).count(), 1)
