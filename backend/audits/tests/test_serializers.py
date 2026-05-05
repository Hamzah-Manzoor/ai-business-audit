from django.test import TestCase
from audits.models import Business, AuditJob
from audits.serializers import BusinessSerializer, AuditJobStatusSerializer


class BusinessSerializerTest(TestCase):
    def test_serializes_required_fields(self):
        business = Business.objects.create(name='Acme', url='https://acme.com', industry_type='SaaS')
        data = BusinessSerializer(business).data
        self.assertEqual(data['name'], 'Acme')
        self.assertEqual(data['url'], 'https://acme.com')
        self.assertEqual(data['industry_type'], 'SaaS')
        self.assertIn('id', data)
        self.assertIn('created_at', data)

    def test_valid_data_deserializes(self):
        serializer = BusinessSerializer(data={'name': 'Acme', 'url': 'https://acme.com'})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_url_is_invalid(self):
        serializer = BusinessSerializer(data={'name': 'Acme'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('url', serializer.errors)

    def test_missing_name_is_invalid(self):
        serializer = BusinessSerializer(data={'url': 'https://acme.com'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)


class AuditJobStatusSerializerTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=business, status='running')

    def test_serializes_status_fields(self):
        data = AuditJobStatusSerializer(self.job).data
        self.assertEqual(data['id'], self.job.id)
        self.assertEqual(data['status'], 'running')
        self.assertIn('triggered_at', data)
        self.assertIsNone(data['completed_at'])
        self.assertEqual(data['error_message'], '')
