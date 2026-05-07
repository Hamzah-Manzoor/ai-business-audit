from unittest.mock import MagicMock
from django.test import TestCase
from audits.decision.rules import apply_priority_rules


def _issue(id, severity, parameter_key, score, category='seo'):
    issue = MagicMock()
    issue.id = id
    issue.severity = severity
    issue.parameter_key = parameter_key
    issue.score = score
    issue.category = category
    return issue


def _report(seo=80, conversion=80, content=80, tech=80, trust=80):
    report = MagicMock()
    report.seo_score = seo
    report.conversion_score = conversion
    report.content_score = content
    report.tech_score = tech
    report.trust_score = trust
    return report


class ApplyPriorityRulesTest(TestCase):
    def test_critical_severity_is_blocker(self):
        issue = _issue(1, 'critical', 'meta_title', 3)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'blocker')

    def test_https_parameter_key_is_blocker(self):
        issue = _issue(1, 'warning', 'https', 5)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'blocker')

    def test_broken_links_parameter_key_is_blocker(self):
        issue = _issue(1, 'warning', 'broken_links', 5)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'blocker')

    def test_category_score_below_40_is_blocker(self):
        issue = _issue(1, 'warning', 'cta_clarity', 5, category='conversion')
        result = apply_priority_rules([issue], _report(conversion=35))
        self.assertEqual(result[0][1], 'blocker')

    def test_category_score_exactly_40_is_not_blocker(self):
        issue = _issue(1, 'warning', 'cta_clarity', 5, category='conversion')
        result = apply_priority_rules([issue], _report(conversion=40))
        self.assertEqual(result[0][1], 'warning')

    def test_warning_severity_is_warning_tier(self):
        issue = _issue(1, 'warning', 'meta_description', 5)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'warning')

    def test_info_severity_is_info_tier(self):
        issue = _issue(1, 'info', 'canonical', 7)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'info')

    def test_blocker_before_warning_before_info(self):
        blocker = _issue(1, 'critical', 'https', 2, 'tech')
        warning = _issue(2, 'warning', 'meta_title', 5, 'seo')
        info = _issue(3, 'info', 'canonical', 7, 'seo')
        result = apply_priority_rules([info, warning, blocker], _report())
        self.assertEqual([t for _, t in result], ['blocker', 'warning', 'info'])

    def test_within_tier_sorted_by_score_ascending(self):
        high_score = _issue(1, 'warning', 'meta_title', 6)
        low_score = _issue(2, 'warning', 'meta_description', 4)
        result = apply_priority_rules([high_score, low_score], _report())
        self.assertEqual(result[0][0].id, 2)
        self.assertEqual(result[1][0].id, 1)

    def test_returns_list_of_tuples(self):
        issue = _issue(1, 'warning', 'meta_title', 5)
        result = apply_priority_rules([issue], _report())
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], tuple)
        self.assertEqual(len(result[0]), 2)

    def test_empty_issues_returns_empty_list(self):
        result = apply_priority_rules([], _report())
        self.assertEqual(result, [])
