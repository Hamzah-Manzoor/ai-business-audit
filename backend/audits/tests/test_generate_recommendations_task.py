from unittest.mock import patch
from django.test import TestCase
from audits.models import AuditJob, AuditReport, AuditIssue, Recommendation, Business
from audits.decision.schemas import RecommendationResult


def _make_recommendation_result(issue_id):
    return RecommendationResult(
        issue_id=issue_id,
        title='Fix the issue',
        effort='low',
        impact='medium',
        priority_score=6.0,
        rationale='Grounded in best-practice context.',
    )


class GenerateRecommendationsTaskTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=self.business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job,
            overall_score=65,
            seo_score=55,
            conversion_score=70,
            content_score=65,
            tech_score=80,
            trust_score=50,
        )
        self.issue = AuditIssue.objects.create(
            report=self.report,
            category='seo',
            severity='warning',
            title='Missing meta description',
            description='No meta description found on the homepage.',
            parameter_key='meta_description',
            score=5,
        )

    def test_creates_recommendation_records(self):
        mock_rec = _make_recommendation_result(self.issue.id)
        with patch('audits.tasks.retrieve_similar_docs', return_value=[]):
            with patch('audits.tasks.generate_recommendations_with_claude', return_value=[mock_rec]):
                from audits.tasks import generate_recommendations
                generate_recommendations(self.job.id)

        self.assertEqual(Recommendation.objects.filter(report=self.report).count(), 1)
        rec = Recommendation.objects.get(report=self.report)
        self.assertEqual(rec.title, 'Fix the issue')
        self.assertEqual(rec.effort, 'low')
        self.assertEqual(rec.impact, 'medium')
        self.assertAlmostEqual(rec.priority_score, 6.0)
        self.assertEqual(rec.issue, self.issue)

    def test_does_not_change_job_status_on_llm_failure(self):
        with patch('audits.tasks.retrieve_similar_docs', return_value=[]):
            with patch('audits.tasks.generate_recommendations_with_claude', return_value=[]):
                from audits.tasks import generate_recommendations
                generate_recommendations(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')

    def test_handles_missing_report_gracefully(self):
        business2 = Business.objects.create(name='Other Co', url='https://other.com')
        job2 = AuditJob.objects.create(business=business2, status='complete')
        # No AuditReport for job2 — task should not raise
        from audits.tasks import generate_recommendations
        generate_recommendations(job2.id)
        job2.refresh_from_db()
        self.assertEqual(job2.status, 'complete')

    def test_rag_retrieval_failure_does_not_crash_task(self):
        mock_rec = _make_recommendation_result(self.issue.id)
        with patch('audits.tasks.retrieve_similar_docs', side_effect=Exception('vector DB down')):
            with patch('audits.tasks.generate_recommendations_with_claude', return_value=[mock_rec]):
                from audits.tasks import generate_recommendations
                generate_recommendations(self.job.id)

        # Task survives; recommendation still created with empty rag context
        self.assertEqual(Recommendation.objects.filter(report=self.report).count(), 1)

    def test_creates_no_records_when_no_issues(self):
        AuditIssue.objects.filter(report=self.report).delete()
        from audits.tasks import generate_recommendations
        generate_recommendations(self.job.id)
        self.assertEqual(Recommendation.objects.filter(report=self.report).count(), 0)
