import re
from statistics import mean

from audits.models import ScrapedPage

from .schemas import CategoryResult, ParameterResult


def score_tech(page: ScrapedPage, all_pages: list) -> CategoryResult:
    params = [
        _score_https(page),
        _score_load_time(page),
        _score_mobile_viewport(page),
        _score_render_blocking_js(page),
        _score_broken_links(all_pages),
        _score_cookie_consent(page),
    ]
    score = round(mean(p.score for p in params) * 10)
    top_issues = [p.key for p in params if p.score <= 5]
    return CategoryResult(
        category='tech',
        score=score,
        parameters=params,
        top_issues=top_issues,
        summary=_summary(score),
    )


def _score_https(page: ScrapedPage) -> ParameterResult:
    if page.https:
        return ParameterResult(key='https', score=10, rationale='Site is served over HTTPS.')
    return ParameterResult(key='https', score=0, rationale='Site is not served over HTTPS — a critical security issue.')


def _score_load_time(page: ScrapedPage) -> ParameterResult:
    ms = page.load_time_ms
    if ms is None:
        return ParameterResult(key='load_time', score=5, rationale='Load time could not be measured.')
    if ms < 2000:
        return ParameterResult(key='load_time', score=10, rationale=f'Page loaded in {ms}ms (under 2s is optimal).')
    if ms < 4000:
        return ParameterResult(key='load_time', score=5, rationale=f'Page loaded in {ms}ms; aim for under 2s.')
    return ParameterResult(key='load_time', score=0, rationale=f'Page loaded in {ms}ms — very slow, over 4s.')


def _score_mobile_viewport(page: ScrapedPage) -> ParameterResult:
    html = page.html_content or ''
    if 'name="viewport"' in html or "name='viewport'" in html:
        return ParameterResult(key='mobile_viewport', score=10, rationale='Mobile viewport meta tag is present.')
    return ParameterResult(key='mobile_viewport', score=0, rationale='No mobile viewport meta tag found.')


def _score_render_blocking_js(page: ScrapedPage) -> ParameterResult:
    html = page.html_content or ''
    head_match = re.search(r'<head[^>]*>(.*?)</head>', html, re.DOTALL | re.IGNORECASE)
    if not head_match:
        return ParameterResult(key='render_blocking_js', score=10, rationale='No <head> section found to inspect.')
    head_html = head_match.group(1)
    scripts = re.findall(r'<script[^>]*>', head_html, re.IGNORECASE)
    blocking = [s for s in scripts if 'defer' not in s and 'async' not in s and 'type="module"' not in s]
    count = len(blocking)
    if count == 0:
        return ParameterResult(key='render_blocking_js', score=10, rationale='No render-blocking scripts in <head>.')
    if count <= 2:
        return ParameterResult(key='render_blocking_js', score=5, rationale=f'{count} render-blocking script(s) in <head>.')
    return ParameterResult(key='render_blocking_js', score=0, rationale=f'{count} render-blocking scripts in <head>.')


def _score_broken_links(all_pages: list) -> ParameterResult:
    broken = [p for p in all_pages if p.status_code is not None and p.status_code >= 400]
    count = len(broken)
    if count == 0:
        return ParameterResult(key='broken_links', score=10, rationale='No broken links detected across scraped pages.')
    if count == 1:
        return ParameterResult(key='broken_links', score=5, rationale=f'1 broken link detected (HTTP {broken[0].status_code}).')
    return ParameterResult(key='broken_links', score=0, rationale=f'{count} broken links detected across scraped pages.')


def _score_cookie_consent(page: ScrapedPage) -> ParameterResult:
    html = (page.html_content or '').lower()
    patterns = ['cookiebot', 'cookie-consent', 'gdpr', 'cookie-law', 'cookie_notice', 'cookiebanner']
    if any(pat in html for pat in patterns):
        return ParameterResult(key='cookie_consent', score=10, rationale='Cookie consent banner detected.')
    return ParameterResult(key='cookie_consent', score=5, rationale='No cookie consent banner detected.')


def _summary(score: int) -> str:
    if score >= 80:
        return 'Technical foundations are solid.'
    if score >= 50:
        return 'Some technical improvements would benefit performance and compliance.'
    return 'Significant technical issues are impacting the site.'
