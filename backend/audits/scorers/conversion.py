from audits.models import ScrapedPage

from .claude_client import score_with_claude
from .schemas import CategoryResult

PROMPT_VERSION = 'conversion-v1'

_RUBRIC = """
Evaluate this website page on CONVERSION potential. Score each parameter 0-10:

- cta_clarity (0-10): Is the primary CTA clear, specific, and compelling? Above the fold? Benefit language?
- value_proposition (0-10): Is the value proposition clear in one sentence (who, what, why)?
- social_proof (0-10): Are testimonials, logos, reviews, or case studies present?
- pricing_transparency (0-10): Is pricing visible or is there a clear path to pricing?
- form_field_count (0-10): Are forms minimal? Score 10 for ≤3 fields, 5 for 4-6 fields, 0 for 7+ fields. Score 8 if no forms present.

Return a submit_category_result tool call with category="conversion".
"""


def score_conversion(page: ScrapedPage) -> CategoryResult:
    return score_with_claude(
        category='conversion',
        prompt=_build_prompt(page),
        prompt_version=PROMPT_VERSION,
    )


def _build_prompt(page: ScrapedPage) -> str:
    text = (page.extracted_text or '')[:3000]
    h2s = ', '.join(page.h2_tags[:5]) if page.h2_tags else '(none)'
    return (
        f"{_RUBRIC}\n\nPage data:\n"
        f"- Meta title: {page.meta_title or '(none)'}\n"
        f"- Meta description: {page.meta_description or '(none)'}\n"
        f"- H1 tags: {', '.join(page.h1_tags) if page.h1_tags else '(none)'}\n"
        f"- H2 tags: {h2s}\n"
        f"- Page text (first 3000 chars):\n{text}"
    )
