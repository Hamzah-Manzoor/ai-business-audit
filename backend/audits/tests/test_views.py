import json
from unittest.mock import patch
from django.test import TestCase
from audits.models import Business, AuditJob


class BusinessListCreateViewTest(TestCase):
    def test_create_business_returns_201(self):
        response = self.client.post(
            '/api/businesses/',
            data=json.dumps({'name': 'Acme', 'url': 'https://acme.com', 'industry_type': 'SaaS'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Acme')
        self.assertIn('id', response.json())

    def test_create_business_missing_url_returns_400(self):
        response = self.client.post(
            '/api/businesses/',
            data=json.dumps({'name': 'Acme'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_list_businesses_returns_200(self):
        Business.objects.create(name='Acme', url='https://acme.com')
        Business.objects.create(name='Beta', url='https://beta.com')
        response = self.client.get('/api/businesses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_list_businesses_empty_returns_200(self):
        response = self.client.get('/api/businesses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class BusinessDetailViewTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')

    def test_get_existing_business_returns_200(self):
        response = self.client.get(f'/api/businesses/{self.business.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Acme')

    def test_get_missing_business_returns_404(self):
        response = self.client.get('/api/businesses/9999/')
        self.assertEqual(response.status_code, 404)
