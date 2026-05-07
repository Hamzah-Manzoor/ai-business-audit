from unittest.mock import MagicMock, patch
from django.test import TestCase
from audits.decision.claude_client import generate_recommendations_with_claude
from audits.decision.schemas import RecommendationResult

_SAMPLE_ISSUES = [
    {
        'issue_id': 1,
        'tier': 'blocker',
        'category': 'tech',
        'severity': 'critical',
        'title': 'HTTPS not enforced',
        'description': 'Site is served over HTTP.',
        'parameter_key': 'https',
        'score': 0,
        'rag_context': [
            {'title': 'HTTPS Best Practices', 'content': 'Always serve over HTTPS.'}
        ],
    }
]

_TOOL_RESPONSE = {
    'recommendations': [
        {
            'issue_id': 1,
            'title': 'Enable HTTPS across all pages',
            'effort': 'low',
            'impact': 'high',
            'priority_score': 9.5,
            'rationale': 'HTTPS is required for trust and SEO ranking.',
        }
    ]
}


def _make_mock_response(tool_input):
    tool_block = MagicMock()
    tool_block.type = 'tool_use'
    tool_block.input = tool_input
    response = MagicMock()
    response.content = [tool_block]
    response.usage.input_tokens = 200
    response.usage.output_tokens = 80
    return response


class GenerateRecommendationsWithClaudeTest(TestCase):
    def test_returns_list_of_recommendation_results(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(_TOOL_RESPONSE)
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], RecommendationResult)

    def test_result_fields_are_correct(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(_TOOL_RESPONSE)
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        r = results[0]
        self.assertEqual(r.issue_id, 1)
        self.assertEqual(r.title, 'Enable HTTPS across all pages')
        self.assertEqual(r.effort, 'low')
        self.assertEqual(r.impact, 'high')
        self.assertAlmostEqual(r.priority_score, 9.5)

    def test_retries_on_failure_then_succeeds(self):
        ok = _make_mock_response(_TOOL_RESPONSE)
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.side_effect = [Exception('timeout'), ok]
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(len(results), 1)

    def test_returns_empty_list_after_three_failures(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception('api error')
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(results, [])

    def test_raises_on_missing_tool_block(self):
        response = MagicMock()
        response.content = []
        response.usage.input_tokens = 50
        response.usage.output_tokens = 10
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = response
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(results, [])

    def test_uses_correct_model_and_tool(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _make_mock_response(_TOOL_RESPONSE)
            generate_recommendations_with_claude(_SAMPLE_ISSUES)
        call_kwargs = mock_create.call_args.kwargs
        self.assertEqual(call_kwargs['model'], 'claude-sonnet-4-6')
        self.assertEqual(call_kwargs['tool_choice'], {'type': 'tool', 'name': 'submit_recommendations'})
