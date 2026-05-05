from django.test import TestCase
from django.urls import reverse
from audits.models import AuditJob, AuditReport, AuditIssue, Business


class AuditReportDetailViewTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job,
            overall_score=72,
            seo_score=80,
            conversion_score=70,
            content_score=75,
            tech_score=60,
            trust_score=65,
        )
        AuditIssue.objects.create(
            report=self.report,
            category='seo',
            severity='warning',
            title='Meta Title',
            description='Title is too short.',
            parameter_key='meta_title',
            score=5,
        )
        AuditIssue.objects.create(
            report=self.report,
            category='tech',
            severity='critical',
            title='Https',
            description='Not using HTTPS.',
            parameter_key='https',
            score=0,
        )

    def test_returns_200(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_returns_overall_score(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.json()['overall_score'], 72)

    def test_returns_category_scores(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        data = self.client.get(url).json()
        self.assertEqual(data['seo_score'], 80)
        self.assertEqual(data['tech_score'], 60)

    def test_returns_nested_issues(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        data = self.client.get(url).json()
        self.assertEqual(len(data['issues']), 2)

    def test_404_for_nonexistent_job(self):
        url = reverse('audit-report', kwargs={'pk': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class AuditIssueListViewTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job, overall_score=60,
            seo_score=60, conversion_score=60, content_score=60, tech_score=60, trust_score=60,
        )
        AuditIssue.objects.create(
            report=self.report, category='seo', severity='warning',
            title='Meta Title', description='Short title.', parameter_key='meta_title', score=5,
        )
        AuditIssue.objects.create(
            report=self.report, category='tech', severity='critical',
            title='Https', description='No HTTPS.', parameter_key='https', score=0,
        )
        AuditIssue.objects.create(
            report=self.report, category='seo', severity='critical',
            title='H1 Tag', description='No H1.', parameter_key='h1_tag', score=0,
        )

    def test_returns_all_issues(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)

    def test_filter_by_category(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk}) + '?category=seo'
        data = self.client.get(url).json()
        self.assertEqual(len(data), 2)
        self.assertTrue(all(i['category'] == 'seo' for i in data))

    def test_filter_by_severity(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk}) + '?severity=critical'
        data = self.client.get(url).json()
        self.assertEqual(len(data), 2)
        self.assertTrue(all(i['severity'] == 'critical' for i in data))

    def test_filter_by_category_and_severity(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk}) + '?category=seo&severity=critical'
        data = self.client.get(url).json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['parameter_key'], 'h1_tag')

    def test_404_for_nonexistent_job(self):
        url = reverse('audit-issues', kwargs={'pk': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
