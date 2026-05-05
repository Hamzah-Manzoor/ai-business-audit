from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from audits.models import AuditJob, AuditReport, AuditIssue, Business, ScrapedPage
from audits.scorers.schemas import CategoryResult, ParameterResult


def make_category_result(category, score, params):
    return CategoryResult(
        category=category,
        score=score,
        parameters=[ParameterResult(key=k, score=s, rationale='test') for k, s in params],
        top_issues=[k for k, s in params if s <= 5],
        summary='Test summary.',
    )


MOCK_RESULTS = {
    'seo': make_category_result('seo', 80, [('meta_title', 10), ('h1_tag', 0)]),
    'tech': make_category_result('tech', 60, [('https', 10), ('load_time', 2)]),
    'conversion': make_category_result('conversion', 70, [('cta_clarity', 8)]),
    'content': make_category_result('content', 75, [('headline_pain_point', 7)]),
    'trust': make_category_result('trust', 50, [('testimonials', 3)]),
}


class RunAuditTaskTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=self.business, status='running')
        ScrapedPage.objects.create(
            business=self.business,
            audit_job=self.job,
            url='https://example.com',
            html_content='<html></html>',
            extracted_text='Test content',
            meta_title='Test',
            meta_description='Desc',
            h1_tags=['Heading'],
            h2_tags=[],
            image_alts=[],
            internal_links=[],
            https=True,
            status_code=200,
            load_time_ms=800,
        )

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_creates_audit_report(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        mock_seo.return_value = MOCK_RESULTS['seo']
        mock_tech.return_value = MOCK_RESULTS['tech']
        mock_conv.return_value = MOCK_RESULTS['conversion']
        mock_content.return_value = MOCK_RESULTS['content']
        mock_trust.return_value = MOCK_RESULTS['trust']

        from audits.tasks import run_audit
        run_audit(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')
        self.assertIsNotNone(self.job.completed_at)
        report = AuditReport.objects.get(audit_job=self.job)
        self.assertEqual(report.seo_score, 80)
        self.assertEqual(report.tech_score, 60)

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_overall_score_is_weighted_average(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        mock_seo.return_value = MOCK_RESULTS['seo']
        mock_tech.return_value = MOCK_RESULTS['tech']
        mock_conv.return_value = MOCK_RESULTS['conversion']
        mock_content.return_value = MOCK_RESULTS['content']
        mock_trust.return_value = MOCK_RESULTS['trust']

        from audits.tasks import run_audit
        run_audit(self.job.id)

        report = AuditReport.objects.get(audit_job=self.job)
        expected = round(80*0.20 + 60*0.20 + 70*0.25 + 75*0.20 + 50*0.15)
        self.assertEqual(report.overall_score, expected)

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_creates_issues_for_low_scoring_params(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        mock_seo.return_value = MOCK_RESULTS['seo']
        mock_tech.return_value = MOCK_RESULTS['tech']
        mock_conv.return_value = MOCK_RESULTS['conversion']
        mock_content.return_value = MOCK_RESULTS['content']
        mock_trust.return_value = MOCK_RESULTS['trust']

        from audits.tasks import run_audit
        run_audit(self.job.id)

        report = AuditReport.objects.get(audit_job=self.job)
        issues = AuditIssue.objects.filter(report=report)
        # h1_tag=0 (critical), load_time=2 (critical), testimonials=3 (critical)
        self.assertGreaterEqual(issues.count(), 3)
        critical = issues.filter(severity='critical')
        self.assertGreaterEqual(critical.count(), 3)

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_no_issues_for_high_scoring_params(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        all_good = make_category_result('seo', 100, [('meta_title', 10), ('h1_tag', 10)])
        mock_seo.return_value = all_good
        mock_tech.return_value = make_category_result('tech', 100, [('https', 10)])
        mock_conv.return_value = make_category_result('conversion', 100, [('cta_clarity', 10)])
        mock_content.return_value = make_category_result('content', 100, [('headline_pain_point', 10)])
        mock_trust.return_value = make_category_result('trust', 100, [('testimonials', 10)])

        from audits.tasks import run_audit
        run_audit(self.job.id)

        report = AuditReport.objects.get(audit_job=self.job)
        self.assertEqual(AuditIssue.objects.filter(report=report).count(), 0)

    def test_sets_failed_status_when_no_pages(self):
        ScrapedPage.objects.filter(audit_job=self.job).delete()
        from audits.tasks import run_audit
        run_audit(self.job.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')

    @patch('audits.tasks.score_seo', side_effect=RuntimeError('scorer blew up'))
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_sets_failed_status_on_exception(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        from audits.tasks import run_audit
        run_audit(self.job.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertIn('scorer blew up', self.job.error_message)


class ScrapeWebsiteChainTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=self.business, status='pending')

    @patch('audits.tasks.run_audit')
    @patch('audits.tasks._playwright_scrape')
    def test_chains_run_audit_on_success(self, mock_scrape, mock_run_audit):
        mock_scrape.return_value = [{
            'url': 'https://example.com',
            'html_content': '<html></html>',
            'extracted_text': 'text',
            'meta_title': 'Title',
            'meta_description': 'Desc',
            'h1_tags': [],
            'h2_tags': [],
            'image_alts': [],
            'internal_links': [],
            'https': True,
            'status_code': 200,
            'load_time_ms': 500,
        }]
        from audits.tasks import scrape_website
        scrape_website(self.job.id)
        mock_run_audit.delay.assert_called_once_with(self.job.id)

    @patch('audits.tasks.run_audit')
    @patch('audits.tasks._playwright_scrape')
    def test_does_not_set_complete_status_after_scrape(self, mock_scrape, mock_run_audit):
        mock_scrape.return_value = [{
            'url': 'https://example.com',
            'html_content': '<html></html>',
            'extracted_text': 'text',
            'meta_title': 'Title',
            'meta_description': 'Desc',
            'h1_tags': [],
            'h2_tags': [],
            'image_alts': [],
            'internal_links': [],
            'https': True,
            'status_code': 200,
            'load_time_ms': 500,
        }]
        from audits.tasks import scrape_website
        scrape_website(self.job.id)
        self.job.refresh_from_db()
        self.assertNotEqual(self.job.status, 'complete')
