import json
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from audits.scorers.claude_client import score_with_claude
from audits.scorers.schemas import CategoryResult


def _make_mock_response(tool_input: dict):
    block = MagicMock()
    block.type = 'tool_use'
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    return response


VALID_TOOL_INPUT = {
    'category': 'conversion',
    'score': 72,
    'parameters': [{'key': 'cta_clarity', 'score': 8, 'rationale': 'CTA is clear.'}],
    'top_issues': [],
    'summary': 'Good conversion signals.',
}


class ClaudeClientTest(SimpleTestCase):
    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_success_returns_category_result(self, MockClient):
        MockClient.return_value.messages.create.return_value = _make_mock_response(VALID_TOOL_INPUT)
        result = score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertIsInstance(result, CategoryResult)
        self.assertEqual(result.category, 'conversion')
        self.assertEqual(result.score, 72)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_success_calls_api_once(self, MockClient):
        MockClient.return_value.messages.create.return_value = _make_mock_response(VALID_TOOL_INPUT)
        score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(MockClient.return_value.messages.create.call_count, 1)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_retries_three_times_on_failure(self, MockClient):
        MockClient.return_value.messages.create.side_effect = Exception('API error')
        score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(MockClient.return_value.messages.create.call_count, 3)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_fallback_score_on_all_failures(self, MockClient):
        MockClient.return_value.messages.create.side_effect = Exception('API error')
        result = score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(result.score, 50)
        self.assertEqual(result.parameters, [])
        self.assertEqual(result.category, 'conversion')

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_succeeds_on_second_attempt(self, MockClient):
        MockClient.return_value.messages.create.side_effect = [
            Exception('first fail'),
            _make_mock_response(VALID_TOOL_INPUT),
        ]
        result = score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(result.score, 72)
        self.assertEqual(MockClient.return_value.messages.create.call_count, 2)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_logs_json_on_success(self, MockClient):
        MockClient.return_value.messages.create.return_value = _make_mock_response(VALID_TOOL_INPUT)
        with self.assertLogs('audits.scorers.claude_client', level='INFO') as cm:
            score_with_claude('conversion', 'test prompt', 'conversion-v1')
        log_line = [line for line in cm.output if 'INFO' in line][0]
        log_record = json.loads(log_line.split('INFO:audits.scorers.claude_client:')[1])
        self.assertEqual(log_record['event'], 'llm_call')
        self.assertTrue(log_record['success'])
        self.assertEqual(log_record['prompt_version'], 'conversion-v1')
