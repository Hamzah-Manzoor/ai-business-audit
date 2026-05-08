from django.test import TestCase
from django.urls import reverse
from audits.models import AuditJob, AuditReport, AuditIssue, Recommendation, Business


class RecommendationListViewTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='API Co', url='https://api.com')
        self.job = AuditJob.objects.create(business=self.business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job,
            overall_score=70,
            seo_score=60,
            conversion_score=75,
            content_score=70,
            tech_score=80,
            trust_score=65,
        )
        self.issue = AuditIssue.objects.create(
            report=self.report,
            category='seo',
            severity='warning',
            title='Missing meta description',
            description='No meta description found.',
            parameter_key='meta_description',
            score=5,
        )
        self.rec = Recommendation.objects.create(
            report=self.report,
            issue=self.issue,
            priority_score=7.5,
            effort='low',
            impact='high',
            title='Add a compelling meta description',
            rationale='Meta descriptions improve CTR by setting user expectations.',
        )

    def test_returns_200(self):
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_returns_recommendation_fields(self):
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(len(data), 1)
        rec = data[0]
        self.assertEqual(rec['title'], 'Add a compelling meta description')
        self.assertEqual(rec['effort'], 'low')
        self.assertEqual(rec['impact'], 'high')
        self.assertAlmostEqual(rec['priority_score'], 7.5)
        self.assertEqual(rec['issue_id'], self.issue.id)
        self.assertIn('rationale', rec)
        self.assertIn('created_at', rec)

    def test_returns_empty_list_when_no_recommendations(self):
        Recommendation.objects.filter(report=self.report).delete()
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        self.assertEqual(response.json(), [])

    def test_returns_404_for_nonexistent_job(self):
        url = reverse('audit-recommendations', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_ordered_by_priority_score_descending(self):
        Recommendation.objects.create(
            report=self.report,
            priority_score=9.0,
            effort='high',
            impact='high',
            title='High priority rec',
            rationale='Very urgent.',
        )
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertGreater(data[0]['priority_score'], data[1]['priority_score'])
