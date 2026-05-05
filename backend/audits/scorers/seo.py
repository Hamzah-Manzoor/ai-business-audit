from statistics import mean

from audits.models import ScrapedPage

from .schemas import CategoryResult, ParameterResult


def score_seo(page: ScrapedPage) -> CategoryResult:
    params = [
        _score_meta_title(page),
        _score_meta_description(page),
        _score_h1(page),
        _score_image_alts(page),
        _score_internal_links(page),
        _score_canonical(page),
    ]
    score = round(mean(p.score for p in params) * 10)
    top_issues = [p.key for p in params if p.score <= 5]
    return CategoryResult(
        category='seo',
        score=score,
        parameters=params,
        top_issues=top_issues,
        summary=_summary(score),
    )


def _score_meta_title(page: ScrapedPage) -> ParameterResult:
    title = page.meta_title or ''
    if not title:
        return ParameterResult(key='meta_title', score=0, rationale='Meta title is missing.')
    length = len(title)
    if 50 <= length <= 60:
        return ParameterResult(key='meta_title', score=10, rationale=f'Meta title is {length} chars (optimal 50–60).')
    return ParameterResult(key='meta_title', score=5, rationale=f'Meta title is {length} chars; optimal is 50–60.')


def _score_meta_description(page: ScrapedPage) -> ParameterResult:
    desc = page.meta_description or ''
    if not desc:
        return ParameterResult(key='meta_description', score=0, rationale='Meta description is missing.')
    length = len(desc)
    if 150 <= length <= 160:
        return ParameterResult(key='meta_description', score=10, rationale=f'Meta description is {length} chars (optimal 150–160).')
    return ParameterResult(key='meta_description', score=5, rationale=f'Meta description is {length} chars; optimal is 150–160.')


def _score_h1(page: ScrapedPage) -> ParameterResult:
    count = len(page.h1_tags or [])
    if count == 1:
        return ParameterResult(key='h1_tag', score=10, rationale='Page has exactly one H1 tag.')
    if count > 1:
        return ParameterResult(key='h1_tag', score=5, rationale=f'Page has {count} H1 tags; should have exactly one.')
    return ParameterResult(key='h1_tag', score=0, rationale='No H1 tag found on the page.')


def _score_image_alts(page: ScrapedPage) -> ParameterResult:
    alts = page.image_alts or []
    total = len(alts)
    if total == 0:
        return ParameterResult(key='image_alts', score=10, rationale='No images found; no alt text issues.')
    present = sum(1 for alt in alts if alt.strip())
    ratio_score = round(10 * present / total)
    if ratio_score == 10:
        return ParameterResult(key='image_alts', score=10, rationale=f'All {total} images have alt text.')
    missing = total - present
    return ParameterResult(key='image_alts', score=ratio_score, rationale=f'{missing} of {total} images are missing alt text.')


def _score_internal_links(page: ScrapedPage) -> ParameterResult:
    count = len(page.internal_links or [])
    if count >= 3:
        return ParameterResult(key='internal_links', score=10, rationale=f'{count} internal links found (3+ is optimal).')
    if count >= 1:
        return ParameterResult(key='internal_links', score=5, rationale=f'Only {count} internal link(s) found; aim for 3+.')
    return ParameterResult(key='internal_links', score=0, rationale='No internal links found.')


def _score_canonical(page: ScrapedPage) -> ParameterResult:
    html = page.html_content or ''
    if 'rel="canonical"' in html or "rel='canonical'" in html:
        return ParameterResult(key='canonical_tag', score=10, rationale='Canonical tag is present.')
    return ParameterResult(key='canonical_tag', score=0, rationale='No canonical tag found.')


def _summary(score: int) -> str:
    if score >= 80:
        return 'SEO fundamentals are in good shape.'
    if score >= 50:
        return 'Several SEO basics need attention.'
    return 'Critical SEO issues require immediate fixes.'
