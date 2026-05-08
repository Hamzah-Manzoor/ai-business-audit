_BLOCKER_KEYS = {'https', 'broken_links'}

_CATEGORY_SCORE_ATTR = {
    'seo': 'seo_score',
    'conversion': 'conversion_score',
    'content': 'content_score',
    'tech': 'tech_score',
    'trust': 'trust_score',
}

_TIER_ORDER = {'blocker': 0, 'warning': 1, 'info': 2}


def apply_priority_rules(issues, report):
    """
    Returns list of (AuditIssue, tier_label) tuples sorted by priority.
    Tier order: blocker → warning → info. Within each tier: score ascending (worst first).
    """
    def _tier(issue):
        score_attr = _CATEGORY_SCORE_ATTR.get(issue.category)
        category_score = getattr(report, score_attr, 100) if score_attr else 100
        if (
            issue.severity == 'critical'
            or issue.parameter_key in _BLOCKER_KEYS
            or category_score < 40
        ):
            return 'blocker'
        if issue.severity == 'warning':
            return 'warning'
        return 'info'

    tagged = [(issue, _tier(issue)) for issue in issues]
    tagged.sort(key=lambda x: (_TIER_ORDER[x[1]], x[0].score))
    return tagged
