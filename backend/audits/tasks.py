import logging
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from celery import shared_task
from django.utils import timezone
from playwright.sync_api import sync_playwright

from .scraper import discover_urls_from_sitemap, extract_page_data, extract_same_domain_links

logger = logging.getLogger(__name__)


def _playwright_scrape(homepage: str) -> list[dict]:
    """
    Run Playwright in a thread to avoid event-loop conflicts.
    Returns a list of page-data dicts (no ORM calls inside this function —
    Django's SynchronousOnlyOperation fires when sync ORM is used while
    Playwright's internal asyncio loop is running).
    """
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        playwright_page = browser.new_page()

        sitemap_urls = discover_urls_from_sitemap(homepage)
        if sitemap_urls:
            urls = list(dict.fromkeys([homepage] + sitemap_urls))[:5]
        else:
            try:
                playwright_page.goto(homepage, timeout=30000, wait_until='networkidle')
                homepage_html = playwright_page.content()
                fallback_links = extract_same_domain_links(homepage_html, homepage, limit=4)
            except Exception as e:
                logger.warning(f"Failed to load homepage for link discovery {homepage}: {e}")
                fallback_links = []
            urls = list(dict.fromkeys([homepage] + fallback_links))[:5]

        for url in urls:
            try:
                t_start = time.monotonic()
                response = playwright_page.goto(url, timeout=30000, wait_until='networkidle')
                load_time_ms = int((time.monotonic() - t_start) * 1000)
                html = playwright_page.content()
                data = extract_page_data(html, url)
                results.append({
                    'url': url,
                    'html_content': html,
                    'status_code': response.status if response else None,
                    'load_time_ms': load_time_ms,
                    'https': url.startswith('https://'),
                    **data,
                })
                logger.info(f"Scraped {url}")
            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}")

    return results


@shared_task
def scrape_website(audit_job_id: int):
    from .models import AuditJob, ScrapedPage

    try:
        job = AuditJob.objects.get(pk=audit_job_id)
    except AuditJob.DoesNotExist:
        logger.error(f"AuditJob {audit_job_id} not found — skipping")
        return

    job.status = 'running'
    job.save(update_fields=['status'])

    business = job.business
    root_parsed = urlparse(business.url)
    homepage = f"{root_parsed.scheme}://{root_parsed.netloc}"

    last_error = None
    scraped_pages: list[dict] = []

    try:
        # Run Playwright in a dedicated thread; no ORM calls happen inside.
        # This avoids Django's SynchronousOnlyOperation check, which fires
        # when sync ORM is invoked while Playwright's internal asyncio loop
        # is active on the current thread.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_playwright_scrape, homepage)
            scraped_pages = future.result(timeout=180)
    except Exception as e:
        last_error = str(e)
        logger.error(f"Fatal scrape error for job {audit_job_id}: {e}")

    # All ORM writes happen here, outside the Playwright/asyncio context.
    saved_count = 0
    for page_data in scraped_pages:
        try:
            ScrapedPage.objects.create(
                business=business,
                audit_job=job,
                **page_data,
            )
            saved_count += 1
        except Exception as e:
            last_error = str(e)
            logger.warning(f"DB save failed for {page_data.get('url')} (job={audit_job_id}): {e}")

    if saved_count > 0:
        job.status = 'complete'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
    else:
        job.status = 'failed'
        job.error_message = last_error or 'No pages could be scraped'
        job.save(update_fields=['status', 'error_message'])
