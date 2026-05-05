from unittest.mock import MagicMock
from django.test import SimpleTestCase
from audits.scorers.tech import score_tech
from audits.models import ScrapedPage


def make_page(**kwargs):
    page = MagicMock(spec=ScrapedPage)
    page.https = kwargs.get('https', True)
    page.load_time_ms = kwargs.get('load_time_ms', 800)
    page.html_content = kwargs.get('html_content', (
        '<head><meta name="viewport" content="width=device-width"></head>'
        '<body>cookiebot</body>'
    ))
    return page


def make_pages(statuses):
    pages = []
    for code in statuses:
        p = MagicMock(spec=ScrapedPage)
        p.status_code = code
        pages.append(p)
    return pages


class TechScorerTest(SimpleTestCase):
    def test_returns_six_parameters(self):
        result = score_tech(make_page(), make_pages([200]))
        self.assertEqual(len(result.parameters), 6)

    def test_category_is_tech(self):
        result = score_tech(make_page(), make_pages([200]))
        self.assertEqual(result.category, 'tech')

    def test_https_true_scores_ten(self):
        result = score_tech(make_page(https=True), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'https')
        self.assertEqual(param.score, 10)

    def test_https_false_scores_zero(self):
        result = score_tech(make_page(https=False), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'https')
        self.assertEqual(param.score, 0)

    def test_load_time_fast_scores_ten(self):
        result = score_tech(make_page(load_time_ms=500), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 10)

    def test_load_time_medium_scores_five(self):
        result = score_tech(make_page(load_time_ms=3000), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 5)

    def test_load_time_slow_scores_zero(self):
        result = score_tech(make_page(load_time_ms=5000), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 0)

    def test_load_time_none_scores_five(self):
        result = score_tech(make_page(load_time_ms=None), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 5)

    def test_viewport_present_scores_ten(self):
        html = '<head><meta name="viewport" content="width=device-width"></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'mobile_viewport')
        self.assertEqual(param.score, 10)

    def test_viewport_absent_scores_zero(self):
        result = score_tech(make_page(html_content='<head></head>'), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'mobile_viewport')
        self.assertEqual(param.score, 0)

    def test_no_blocking_scripts_scores_ten(self):
        html = '<head><script defer src="a.js"></script></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'render_blocking_js')
        self.assertEqual(param.score, 10)

    def test_two_blocking_scripts_scores_five(self):
        html = '<head><script src="a.js"></script><script src="b.js"></script></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'render_blocking_js')
        self.assertEqual(param.score, 5)

    def test_three_blocking_scripts_scores_zero(self):
        html = '<head><script src="a.js"></script><script src="b.js"></script><script src="c.js"></script></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'render_blocking_js')
        self.assertEqual(param.score, 0)

    def test_no_broken_links_scores_ten(self):
        result = score_tech(make_page(), make_pages([200, 200, 200]))
        param = next(p for p in result.parameters if p.key == 'broken_links')
        self.assertEqual(param.score, 10)

    def test_one_broken_link_scores_five(self):
        result = score_tech(make_page(), make_pages([200, 404]))
        param = next(p for p in result.parameters if p.key == 'broken_links')
        self.assertEqual(param.score, 5)

    def test_two_broken_links_scores_zero(self):
        result = score_tech(make_page(), make_pages([404, 500]))
        param = next(p for p in result.parameters if p.key == 'broken_links')
        self.assertEqual(param.score, 0)

    def test_cookie_consent_present_scores_ten(self):
        result = score_tech(make_page(html_content='<div class="cookiebot">accept</div>'), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'cookie_consent')
        self.assertEqual(param.score, 10)

    def test_cookie_consent_absent_scores_five(self):
        result = score_tech(make_page(html_content='<html></html>'), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'cookie_consent')
        self.assertEqual(param.score, 5)
