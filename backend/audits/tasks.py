import logging
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from celery import shared_task
from django.utils import timezone
from playwright.sync_api import sync_playwright

from .scraper import discover_urls_from_sitemap, extract_page_data, extract_same_domain_links
from .scorers.seo import score_seo
from .scorers.tech import score_tech
from .scorers.conversion import score_conversion
from .scorers.content import score_content
from .scorers.trust import score_trust
from .decision.rules import apply_priority_rules
from .decision.claude_client import generate_recommendations_with_claude
from .rag.retrieval import retrieve_similar_docs

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
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_playwright_scrape, homepage)
            scraped_pages = future.result(timeout=180)
    except Exception as e:
        last_error = str(e)
        logger.error(f"Fatal scrape error for job {audit_job_id}: {e}")

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
        run_audit.delay(audit_job_id)
    else:
        job.status = 'failed'
        job.error_message = last_error or 'No pages could be scraped'
        job.save(update_fields=['status', 'error_message'])


@shared_task
def run_audit(audit_job_id: int):
    from .models import AuditJob, AuditReport, AuditIssue, ScrapedPage

    try:
        job = AuditJob.objects.get(pk=audit_job_id)
    except AuditJob.DoesNotExist:
        logger.error(f"AuditJob {audit_job_id} not found — skipping")
        return

    try:
        all_pages = list(ScrapedPage.objects.filter(audit_job=job))
        if not all_pages:
            job.status = 'failed'
            job.error_message = 'No scraped pages found for audit'
            job.save(update_fields=['status', 'error_message'])
            return

        root_parsed = urlparse(job.business.url)
        homepage_url = f"{root_parsed.scheme}://{root_parsed.netloc}"
        page = next(
            (p for p in all_pages if p.url.rstrip('/') == homepage_url.rstrip('/')),
            all_pages[0],
        )

        seo_result = score_seo(page)
        tech_result = score_tech(page, all_pages)
        conv_result = score_conversion(page)
        content_result = score_content(page)
        trust_result = score_trust(page)

        overall = round(
            seo_result.score * 0.20
            + tech_result.score * 0.20
            + conv_result.score * 0.25
            + content_result.score * 0.20
            + trust_result.score * 0.15
        )

        report = AuditReport.objects.create(
            audit_job=job,
            overall_score=overall,
            seo_score=seo_result.score,
            conversion_score=conv_result.score,
            content_score=content_result.score,
            tech_score=tech_result.score,
            trust_score=trust_result.score,
            raw_llm_response={
                'conversion': conv_result.model_dump(),
                'content': content_result.model_dump(),
                'trust': trust_result.model_dump(),
            },
        )

        for result in [seo_result, tech_result, conv_result, content_result, trust_result]:
            for param in result.parameters:
                if param.score <= 6:
                    AuditIssue.objects.create(
                        report=report,
                        category=result.category,
                        severity='critical' if param.score <= 3 else 'warning',
                        title=param.key.replace('_', ' ').title(),
                        description=param.rationale,
                        parameter_key=param.key,
                        score=param.score,
                    )

        job.status = 'complete'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
        logger.info(f"run_audit completed for job {audit_job_id}: overall_score={overall}")
        generate_recommendations.delay(audit_job_id)

    except Exception as exc:
        logger.error(f"run_audit failed for job {audit_job_id}: {exc}")
        try:
            job.status = 'failed'
            job.error_message = str(exc)
            job.save(update_fields=['status', 'error_message'])
        except Exception:
            pass


@shared_task
def generate_recommendations(audit_job_id: int):
    from .models import AuditJob, AuditReport, AuditIssue, Recommendation

    try:
        job = AuditJob.objects.get(pk=audit_job_id)
        report = AuditReport.objects.get(audit_job=job)
        issues = list(AuditIssue.objects.filter(report=report))

        if not issues:
            logger.info(f'generate_recommendations: no issues for job {audit_job_id}')
            return

        ranked = apply_priority_rules(issues, report)

        ranked_issues_with_context = []
        for issue, tier in ranked:
            try:
                docs = retrieve_similar_docs(issue.description, top_k=3)
            except Exception as e:
                logger.warning(f'RAG retrieval failed for issue {issue.id}: {e}')
                docs = []
            ranked_issues_with_context.append({
                'issue_id': issue.id,
                'tier': tier,
                'category': issue.category,
                'severity': issue.severity,
                'title': issue.title,
                'description': issue.description,
                'parameter_key': issue.parameter_key,
                'score': issue.score,
                'rag_context': [
                    {'title': d.title, 'content': d.content[:300]}
                    for d in docs
                ],
            })

        results = generate_recommendations_with_claude(ranked_issues_with_context)

        issue_map = {issue.id: issue for issue, _ in ranked}
        Recommendation.objects.bulk_create([
            Recommendation(
                report=report,
                issue=issue_map.get(r.issue_id),
                priority_score=r.priority_score,
                effort=r.effort,
                impact=r.impact,
                title=r.title,
                rationale=r.rationale,
            )
            for r in results
        ])
        logger.info(
            f'generate_recommendations: created {len(results)} recommendations for job {audit_job_id}'
        )

    except Exception as exc:
        logger.error(f'generate_recommendations failed for job {audit_job_id}: {exc}')
