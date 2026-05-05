from unittest.mock import MagicMock
from django.test import SimpleTestCase
from audits.scorers.seo import score_seo
from audits.models import ScrapedPage


def make_page(**kwargs):
    page = MagicMock(spec=ScrapedPage)
    page.meta_title = kwargs.get('meta_title', 'A Good Title That Is Fifty Five Characters')
    page.meta_description = kwargs.get('meta_description', 'A' * 155)
    page.h1_tags = kwargs.get('h1_tags', ['Main Heading'])
    page.h2_tags = kwargs.get('h2_tags', [])
    page.image_alts = kwargs.get('image_alts', ['alt text', 'another alt'])
    page.internal_links = kwargs.get('internal_links', ['/a', '/b', '/c'])
    page.html_content = kwargs.get('html_content', '<link rel="canonical" href="/">')
    return page


class SEOScorerTest(SimpleTestCase):
    def test_perfect_page_scores_high(self):
        result = score_seo(make_page())
        self.assertEqual(result.category, 'seo')
        self.assertGreaterEqual(result.score, 90)

    def test_meta_title_missing_scores_zero_for_that_param(self):
        result = score_seo(make_page(meta_title=''))
        param = next(p for p in result.parameters if p.key == 'meta_title')
        self.assertEqual(param.score, 0)

    def test_meta_title_wrong_length_scores_five(self):
        result = score_seo(make_page(meta_title='Short'))
        param = next(p for p in result.parameters if p.key == 'meta_title')
        self.assertEqual(param.score, 5)

    def test_meta_title_optimal_length_scores_ten(self):
        result = score_seo(make_page(meta_title='A' * 55))
        param = next(p for p in result.parameters if p.key == 'meta_title')
        self.assertEqual(param.score, 10)

    def test_meta_description_missing_scores_zero(self):
        result = score_seo(make_page(meta_description=''))
        param = next(p for p in result.parameters if p.key == 'meta_description')
        self.assertEqual(param.score, 0)

    def test_h1_exactly_one_scores_ten(self):
        result = score_seo(make_page(h1_tags=['Only Heading']))
        param = next(p for p in result.parameters if p.key == 'h1_tag')
        self.assertEqual(param.score, 10)

    def test_h1_multiple_scores_five(self):
        result = score_seo(make_page(h1_tags=['H1', 'H1 Again']))
        param = next(p for p in result.parameters if p.key == 'h1_tag')
        self.assertEqual(param.score, 5)

    def test_h1_missing_scores_zero(self):
        result = score_seo(make_page(h1_tags=[]))
        param = next(p for p in result.parameters if p.key == 'h1_tag')
        self.assertEqual(param.score, 0)

    def test_image_alts_all_present_scores_ten(self):
        result = score_seo(make_page(image_alts=['alt1', 'alt2']))
        param = next(p for p in result.parameters if p.key == 'image_alts')
        self.assertEqual(param.score, 10)

    def test_image_alts_some_missing_scales_score(self):
        result = score_seo(make_page(image_alts=['alt', '', '']))
        param = next(p for p in result.parameters if p.key == 'image_alts')
        self.assertEqual(param.score, 3)

    def test_no_images_scores_ten(self):
        result = score_seo(make_page(image_alts=[]))
        param = next(p for p in result.parameters if p.key == 'image_alts')
        self.assertEqual(param.score, 10)

    def test_three_internal_links_scores_ten(self):
        result = score_seo(make_page(internal_links=['/a', '/b', '/c']))
        param = next(p for p in result.parameters if p.key == 'internal_links')
        self.assertEqual(param.score, 10)

    def test_one_internal_link_scores_five(self):
        result = score_seo(make_page(internal_links=['/a']))
        param = next(p for p in result.parameters if p.key == 'internal_links')
        self.assertEqual(param.score, 5)

    def test_no_internal_links_scores_zero(self):
        result = score_seo(make_page(internal_links=[]))
        param = next(p for p in result.parameters if p.key == 'internal_links')
        self.assertEqual(param.score, 0)

    def test_canonical_present_scores_ten(self):
        result = score_seo(make_page(html_content='<link rel="canonical" href="/">'))
        param = next(p for p in result.parameters if p.key == 'canonical_tag')
        self.assertEqual(param.score, 10)

    def test_canonical_absent_scores_zero(self):
        result = score_seo(make_page(html_content='<html></html>'))
        param = next(p for p in result.parameters if p.key == 'canonical_tag')
        self.assertEqual(param.score, 0)

    def test_returns_six_parameters(self):
        result = score_seo(make_page())
        self.assertEqual(len(result.parameters), 6)

    def test_top_issues_contains_low_scoring_params(self):
        result = score_seo(make_page(meta_title='', h1_tags=[]))
        self.assertIn('meta_title', result.top_issues)
        self.assertIn('h1_tag', result.top_issues)
