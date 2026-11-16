"""모델 없이도 원자료 검증·후속 조건·조회 제한을 유지한다."""
import unittest
from unittest.mock import Mock

from citrus_freellm.agent import Agent


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.complete.side_effect = AssertionError("로컬 질문을 외부로 전송함")
        self.agent = Agent(self.client, local_only=True)

    def test_verified_lookup_and_followup(self):
        answer = self.agent.ask("2019년과 2020년 천혜향 생산량 비교")
        self.assertIn("18,044", answer)
        self.assertIn("+3.16%", answer)
        self.assertIn("https://jejudatahub.net", answer)
        self.assertEqual(self.agent.results[-1]['sources'][0]['path'], 'data/raw/public/fruit_production.csv')
        followup = self.agent.ask("그러면 2018년은?")
        self.assertIn("2018", followup)
        self.assertEqual(self.agent.previous_request["variety"], "천혜향")
        self.assertEqual(len(self.agent.results), 2)
        self.client.complete.assert_not_called()

    def test_ambiguous_question_stays_local(self):
        answer = self.agent.ask("추천해줘")
        self.assertIn("품종", answer)
        self.assertEqual(self.agent.results, [])
        self.client.complete.assert_not_called()

    def test_unsupported_forecast_is_not_calculated(self):
        answer = self.agent.ask("2027년 천혜향 생산량 예측")
        self.assertIn("지원하지 않습니다", answer)
        self.assertEqual(self.agent.results, [])
        self.client.complete.assert_not_called()
