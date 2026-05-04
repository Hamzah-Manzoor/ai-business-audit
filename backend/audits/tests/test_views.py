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


class AuditTriggerViewTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')

    @patch('audits.views.scrape_website')
    def test_creates_audit_job_and_dispatches_task(self, mock_task):
        response = self.client.post(f'/api/businesses/{self.business.id}/audit/')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'pending')
        self.assertIn('audit_job_id', data)
        mock_task.delay.assert_called_once_with(data['audit_job_id'])

    @patch('audits.views.scrape_website')
    def test_audit_trigger_missing_business_returns_404(self, mock_task):
        response = self.client.post('/api/businesses/9999/audit/')
        self.assertEqual(response.status_code, 404)
        mock_task.delay.assert_not_called()


class AuditStatusViewTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=business, status='running')

    def test_returns_job_status(self):
        response = self.client.get(f'/api/audits/{self.job.id}/status/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'running')
        self.assertEqual(data['id'], self.job.id)

    def test_missing_job_returns_404(self):
        response = self.client.get('/api/audits/9999/status/')
        self.assertEqual(response.status_code, 404)
