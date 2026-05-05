from unittest.mock import MagicMock, patch
from django.test import TestCase
from audits.scraper import discover_urls_from_sitemap, extract_same_domain_links, extract_page_data

SAMPLE_HTML = """
<html>
<head>
    <title>  Acme Corp  </title>
    <meta name="description" content="We make great products">
</head>
<body>
    <h1>Welcome to Acme</h1>
    <h2>Our Products</h2>
    <h2>Our Team</h2>
    <img src="logo.png" alt="Acme Logo">
    <img src="hero.png">
    <a href="https://acme.com/about">About</a>
    <a href="https://acme.com/pricing">Pricing</a>
    <a href="https://other.com/page">External</a>
    <a href="/contact">Contact</a>
    <p>We make great products for businesses.</p>
    <script>var x = 1; console.log("hidden");</script>
    <style>.hidden { display: none; }</style>
</body>
</html>
"""

SAMPLE_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://acme.com/</loc></url>
    <url><loc>https://acme.com/about</loc></url>
    <url><loc>https://acme.com/pricing</loc></url>
    <url><loc>https://acme.com/contact</loc></url>
    <url><loc>https://acme.com/blog</loc></url>
    <url><loc>https://other.com/external</loc></url>
</urlset>
"""


class ExtractPageDataTest(TestCase):
    def test_extracts_title_stripped(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['meta_title'], 'Acme Corp')

    def test_extracts_meta_description(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['meta_description'], 'We make great products')

    def test_extracts_all_h1_tags(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['h1_tags'], ['Welcome to Acme'])

    def test_extracts_all_h2_tags(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['h2_tags'], ['Our Products', 'Our Team'])

    def test_extracts_image_alts_including_empty_string(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['image_alts'], ['Acme Logo', ''])

    def test_internal_links_excludes_external(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/about', data['internal_links'])
        self.assertIn('https://acme.com/pricing', data['internal_links'])
        self.assertNotIn('https://other.com/page', data['internal_links'])

    def test_relative_links_resolved_to_absolute(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/contact', data['internal_links'])

    def test_extracted_text_excludes_script_content(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertNotIn('var x = 1', data['extracted_text'])
        self.assertNotIn('console.log', data['extracted_text'])

    def test_extracted_text_excludes_style_content(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertNotIn('.hidden', data['extracted_text'])

    def test_extracted_text_includes_body_text(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('We make great products for businesses', data['extracted_text'])

    def test_missing_title_returns_empty_string(self):
        html = '<html><body><p>No title</p></body></html>'
        data = extract_page_data(html, 'https://acme.com')
        self.assertEqual(data['meta_title'], '')

    def test_missing_description_returns_empty_string(self):
        html = '<html><head><title>T</title></head><body></body></html>'
        data = extract_page_data(html, 'https://acme.com')
        self.assertEqual(data['meta_description'], '')


class DiscoverUrlsFromSitemapTest(TestCase):
    @patch('audits.scraper.requests.get')
    def test_returns_same_domain_urls_excluding_homepage(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=SAMPLE_SITEMAP)
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertIn('https://acme.com/about', result)
        self.assertIn('https://acme.com/pricing', result)
        self.assertNotIn('https://other.com/external', result)

    @patch('audits.scraper.requests.get')
    def test_excludes_homepage_from_results(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=SAMPLE_SITEMAP)
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertNotIn('https://acme.com/', result)
        self.assertNotIn('https://acme.com', result)

    @patch('audits.scraper.requests.get')
    def test_caps_results_at_four(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=SAMPLE_SITEMAP)
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertLessEqual(len(result), 4)

    @patch('audits.scraper.requests.get')
    def test_returns_empty_on_404(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404, text='')
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertEqual(result, [])

    @patch('audits.scraper.requests.get')
    def test_returns_empty_on_connection_error(self, mock_get):
        mock_get.side_effect = Exception('Connection refused')
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertEqual(result, [])


class ExtractSameDomainLinksTest(TestCase):
    def test_returns_same_domain_links(self):
        result = extract_same_domain_links(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/about', result)
        self.assertNotIn('https://other.com/page', result)

    def test_resolves_relative_links(self):
        result = extract_same_domain_links(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/contact', result)

    def test_respects_limit(self):
        result = extract_same_domain_links(SAMPLE_HTML, 'https://acme.com', limit=1)
        self.assertEqual(len(result), 1)

    def test_deduplicates_links(self):
        html = '<html><body><a href="/about">A</a><a href="/about">A again</a></body></html>'
        result = extract_same_domain_links(html, 'https://acme.com')
        self.assertEqual(result.count('https://acme.com/about'), 1)
