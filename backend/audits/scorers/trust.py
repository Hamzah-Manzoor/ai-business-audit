from audits.models import ScrapedPage

from .claude_client import score_with_claude
from .schemas import CategoryResult

PROMPT_VERSION = 'trust-v1'

_RUBRIC = """
Evaluate this website page on TRUST signals. Score each parameter 0-10:

- testimonials (0-10): Are testimonials, case studies, or customer reviews present?
- about_page (0-10): Is there an About page or team information visible or linked?
- contact_info (0-10): Is contact information (email, phone, address) clearly visible?
- privacy_policy (0-10): Are privacy policy and/or terms of service links present?
- trust_badges (0-10): Are there certifications, security badges, accreditations, or partner logos?

Return a submit_category_result tool call with category="trust".
"""


def score_trust(page: ScrapedPage) -> CategoryResult:
    return score_with_claude(
        category='trust',
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
