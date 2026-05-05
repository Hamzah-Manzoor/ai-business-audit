from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from audits.models import ScrapedPage
from audits.scorers.schemas import CategoryResult, ParameterResult


def make_page():
    page = MagicMock(spec=ScrapedPage)
    page.meta_title = 'Example Site'
    page.meta_description = 'We help you grow.'
    page.h1_tags = ['Grow Your Business']
    page.h2_tags = ['Features', 'Pricing']
    page.extracted_text = 'We help businesses grow with AI tools.'
    return page


def make_category_result(category):
    return CategoryResult(
        category=category,
        score=65,
        parameters=[ParameterResult(key='cta_clarity', score=6, rationale='CTA is weak.')],
        top_issues=['cta_clarity'],
        summary='Needs improvement.',
    )


class ConversionScorerTest(SimpleTestCase):
    @patch('audits.scorers.conversion.score_with_claude')
    def test_calls_score_with_claude(self, mock_claude):
        from audits.scorers.conversion import score_conversion
        mock_claude.return_value = make_category_result('conversion')
        result = score_conversion(make_page())
        mock_claude.assert_called_once()
        call_kwargs = mock_claude.call_args
        self.assertEqual(call_kwargs[1]['category'], 'conversion')
        self.assertEqual(call_kwargs[1]['prompt_version'], 'conversion-v1')

    @patch('audits.scorers.conversion.score_with_claude')
    def test_returns_category_result(self, mock_claude):
        from audits.scorers.conversion import score_conversion
        mock_claude.return_value = make_category_result('conversion')
        result = score_conversion(make_page())
        self.assertIsInstance(result, CategoryResult)
        self.assertEqual(result.score, 65)

    @patch('audits.scorers.conversion.score_with_claude')
    def test_prompt_includes_page_text(self, mock_claude):
        from audits.scorers.conversion import score_conversion
        mock_claude.return_value = make_category_result('conversion')
        page = make_page()
        page.extracted_text = 'unique-sentinel-text-xyz'
        score_conversion(page)
        prompt_arg = mock_claude.call_args[1]['prompt']
        self.assertIn('unique-sentinel-text-xyz', prompt_arg)


class ContentScorerTest(SimpleTestCase):
    @patch('audits.scorers.content.score_with_claude')
    def test_calls_score_with_claude_content_version(self, mock_claude):
        from audits.scorers.content import score_content
        mock_claude.return_value = make_category_result('content')
        score_content(make_page())
        call_kwargs = mock_claude.call_args
        self.assertEqual(call_kwargs[1]['category'], 'content')
        self.assertEqual(call_kwargs[1]['prompt_version'], 'content-v1')

    @patch('audits.scorers.content.score_with_claude')
    def test_returns_category_result(self, mock_claude):
        from audits.scorers.content import score_content
        mock_claude.return_value = make_category_result('content')
        result = score_content(make_page())
        self.assertIsInstance(result, CategoryResult)


class TrustScorerTest(SimpleTestCase):
    @patch('audits.scorers.trust.score_with_claude')
    def test_calls_score_with_claude_trust_version(self, mock_claude):
        from audits.scorers.trust import score_trust
        mock_claude.return_value = make_category_result('trust')
        score_trust(make_page())
        call_kwargs = mock_claude.call_args
        self.assertEqual(call_kwargs[1]['category'], 'trust')
        self.assertEqual(call_kwargs[1]['prompt_version'], 'trust-v1')

    @patch('audits.scorers.trust.score_with_claude')
    def test_returns_category_result(self, mock_claude):
        from audits.scorers.trust import score_trust
        mock_claude.return_value = make_category_result('trust')
        result = score_trust(make_page())
        self.assertIsInstance(result, CategoryResult)
