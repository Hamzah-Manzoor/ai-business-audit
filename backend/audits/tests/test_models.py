from django.test import TestCase
from audits.models import (
    Business, AuditJob, AuditReport, AuditIssue,
    Recommendation, KnowledgeDoc, ScrapedPage,
)


class BusinessModelTest(TestCase):
    def test_create_business(self):
        b = Business.objects.create(name='Acme', url='https://acme.com', industry_type='SaaS')
        self.assertEqual(str(b), 'Acme')
        self.assertIsNotNone(b.created_at)


class AuditJobModelTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')

    def test_default_status_is_pending(self):
        job = AuditJob.objects.create(business=self.business)
        self.assertEqual(job.status, 'pending')

    def test_str_includes_status(self):
        job = AuditJob.objects.create(business=self.business)
        self.assertIn('pending', str(job))


class AuditReportModelTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=business)

    def test_create_report(self):
        report = AuditReport.objects.create(
            audit_job=self.job, overall_score=75,
            seo_score=80, conversion_score=70,
            content_score=75, tech_score=85, trust_score=60,
        )
        self.assertEqual(report.overall_score, 75)


class AuditIssueModelTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        job = AuditJob.objects.create(business=business)
        self.report = AuditReport.objects.create(audit_job=job, overall_score=50)

    def test_create_issue(self):
        issue = AuditIssue.objects.create(
            report=self.report, category='seo', severity='critical',
            title='Missing H1', description='No H1 tag found.',
            parameter_key='h1_exists', score=0,
        )
        self.assertIn('CRITICAL', str(issue))


class RecommendationModelTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        job = AuditJob.objects.create(business=business)
        self.report = AuditReport.objects.create(audit_job=job, overall_score=50)

    def test_create_recommendation(self):
        rec = Recommendation.objects.create(
            report=self.report, priority_score=9.5,
            effort='low', impact='high',
            title='Add H1 tag', rationale='H1 improves SEO.',
        )
        self.assertEqual(rec.effort, 'low')


class KnowledgeDocModelTest(TestCase):
    def test_create_knowledge_doc(self):
        doc = KnowledgeDoc.objects.create(
            title='CTA Best Practices', category='conversion',
            content='Use action verbs in CTAs.', source='internal',
        )
        self.assertEqual(str(doc), 'CTA Best Practices')
        self.assertIsNone(doc.embedding)


class ScrapedPageModelTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=self.business)

    def test_create_scraped_page(self):
        page = ScrapedPage.objects.create(
            business=self.business, audit_job=self.job,
            url='https://acme.com', https=True, status_code=200,
        )
        self.assertIn('acme.com', str(page))
