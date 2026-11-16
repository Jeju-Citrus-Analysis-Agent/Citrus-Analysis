"""The live-model evaluation cases must also pass with local rules alone."""
import json
import unittest
from pathlib import Path

from citrus_freellm.agent import Agent
from citrus_freellm.guardrails import request_for

CASES = json.loads(Path(__file__).resolve().parents[1].joinpath('evaluation_cases.json').read_text(encoding='utf-8'))


class FollowupPhrasingTests(unittest.TestCase):
    def test_evaluation_cases_without_model(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                agent = Agent(local_only=True)
                seed = request_for(case['seed'])[0] if case['seed'] else None
                agent.previous_request = seed
                answer = agent.ask(case['question'])
                if case.get('blocked'):
                    self.assertNotIn('| 연도 |', answer)
                    self.assertEqual(agent.previous_request, seed)
                else:
                    self.assertIn('| 연도 |', answer)
                    self.assertEqual(agent.previous_request['years'], case['years'])
                    self.assertEqual(agent.previous_request['metrics'], case['metrics'])

    def test_previous_year_needs_a_phrase_not_a_substring(self):
        seed = request_for('2019년 천혜향 생산량')[0]
        plan, _ = request_for('천혜향 생산량 자료가 완전해?', seed)
        self.assertEqual(plan['years'], [2019])
