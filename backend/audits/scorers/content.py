from audits.models import ScrapedPage

from .claude_client import score_with_claude
from .schemas import CategoryResult

PROMPT_VERSION = 'content-v1'

_RUBRIC = """
Evaluate this website page on CONTENT quality. Score each parameter 0-10:

- headline_pain_point (0-10): Does the main headline address a real customer pain point?
- benefits_vs_features (0-10): Does the copy focus on benefits to the customer rather than just product features?
- reading_level (0-10): Is the reading level appropriate and accessible for the target audience?
- brand_voice (0-10): Is the brand voice consistent and distinct across headings and body copy?
- content_depth (0-10): Is there sufficient content depth — informative without being overwhelming?

Return a submit_category_result tool call with category="content".
"""


def score_content(page: ScrapedPage) -> CategoryResult:
    return score_with_claude(
        category='content',
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
