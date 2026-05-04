from unittest.mock import MagicMock, patch
from django.test import TestCase
from audits.models import AuditJob, Business, ScrapedPage
from audits.tasks import scrape_website

MINIMAL_HTML = '<html><head><title>Acme</title></head><body><h1>Hello</h1></body></html>'


def _make_playwright_mock(html=MINIMAL_HTML, status_code=200, goto_raises=None):
    """Return a mock sync_playwright context that yields a usable page."""
    mock_response = MagicMock()
    mock_response.status = status_code

    mock_page = MagicMock()
    mock_page.content.return_value = html
    if goto_raises:
        mock_page.goto.side_effect = goto_raises
    else:
        mock_page.goto.return_value = mock_response

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_p)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    return mock_ctx


class ScrapeWebsiteTaskTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=self.business)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_marks_job_running_then_complete(self, mock_discover, mock_playwright):
        mock_discover.return_value = []
        mock_playwright.return_value = _make_playwright_mock()

        scrape_website(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')
        self.assertIsNotNone(self.job.completed_at)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_saves_scraped_page_record(self, mock_discover, mock_playwright):
        mock_discover.return_value = []
        mock_playwright.return_value = _make_playwright_mock()

        scrape_website(self.job.id)

        pages = ScrapedPage.objects.filter(audit_job=self.job)
        self.assertEqual(pages.count(), 1)
        page = pages.first()
        self.assertEqual(page.url, 'https://acme.com')
        self.assertEqual(page.meta_title, 'Acme')
        self.assertEqual(page.h1_tags, ['Hello'])
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.https)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_uses_sitemap_urls_when_available(self, mock_discover, mock_playwright):
        mock_discover.return_value = ['https://acme.com/about', 'https://acme.com/pricing']
        mock_playwright.return_value = _make_playwright_mock()

        scrape_website(self.job.id)

        urls_scraped = list(ScrapedPage.objects.filter(audit_job=self.job).values_list('url', flat=True))
        self.assertIn('https://acme.com', urls_scraped)
        self.assertIn('https://acme.com/about', urls_scraped)
        self.assertIn('https://acme.com/pricing', urls_scraped)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_marks_failed_when_all_pages_fail(self, mock_discover, mock_playwright):
        mock_discover.return_value = []
        mock_playwright.return_value = _make_playwright_mock(goto_raises=Exception('Timeout'))

        scrape_website(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertEqual(self.job.error_message, 'No pages could be scraped')

    def test_returns_early_for_nonexistent_job(self):
        # Should not raise — just log and return
        scrape_website(99999)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_continues_after_single_page_failure(self, mock_discover, mock_playwright):
        mock_discover.return_value = ['https://acme.com/about']

        mock_response = MagicMock()
        mock_response.status = 200
        mock_page = MagicMock()
        mock_page.content.return_value = MINIMAL_HTML
        call_count = {'n': 0}

        def goto_side_effect(url, **kwargs):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise Exception('First page failed')
            return mock_response

        mock_page.goto.side_effect = goto_side_effect
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_p)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_playwright.return_value = mock_ctx

        scrape_website(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')
        self.assertEqual(ScrapedPage.objects.filter(audit_job=self.job).count(), 1)
