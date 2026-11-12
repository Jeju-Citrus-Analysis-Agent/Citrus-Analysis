"""Regression: model answers 'both' in prose instead of requesting a tool."""
import json
import unittest
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.guardrails import request_for


def tool_call(year):
    return {"role": "assistant", "tool_calls": [{"id": "p", "type": "function", "function": {
        "name": "production", "arguments": json.dumps({"variety": "한라봉", "start_year": year, "end_year": year})}}]}


class MissingToolCallTests(unittest.TestCase):
    def test_user_sequence_with_plain_text_on_both(self):
        client = Mock()
        client.complete.side_effect = [tool_call(2016), tool_call(2018), tool_call(2018),
                                       {"role": "assistant", "content": "둘 다 999999입니다."}]
        agent = Agent(client)
        agent.ask("2016년 한라봉 생산면적")
        agent.ask("2018년은?")
        agent.ask("생산량은?")
        answer = agent.ask("둘 다 알려줘")
        self.assertIn("생산량 (톤)", answer)
        self.assertIn("생산면적 (ha)", answer)
        self.assertIn("| 2018 | 43,822 | 1,597 |", answer)
        self.assertNotIn("999999", answer)
        self.assertEqual(agent.previous_request["metrics"], ["생산량_톤", "생산면적_ha"])
        agent.reset()
        self.assertIn("명시", agent.ask("둘 다 알려줘"))
        self.assertEqual(client.complete.call_count, 4)

    def test_no_calls_for_every_turn_still_uses_fresh_evidence(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "과거 답변을 참고하세요."}
        agent = Agent(client)
        from citrus_freellm.tools import execute
        with patch("citrus_freellm.agent.execute", wraps=execute) as dispatch:
            agent.ask("2016년 한라봉 생산면적")
            agent.ask("2018년은?")
            agent.ask("생산량은?")
            answer = agent.ask("둘 다 알려줘")
        self.assertEqual(dispatch.call_count, 4)
        self.assertIn("| 2018 | 43,822 | 1,597 |", answer)

    def test_fallback_cannot_bypass_source_checks(self):
        from citrus_freellm.tools import production
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "OK"}
        data = production("한라봉", 2018, 2018)
        data["rows"][0]["생산량_톤"] = 99999
        agent = Agent(client)
        with patch("citrus_freellm.agent.execute", return_value=data):
            answer = agent.ask("2018년 한라봉 생산량과 면적")
        self.assertIn("보류", answer)
        self.assertNotIn("99,999", answer)
        self.assertIsNone(agent.previous_request)

    def test_fallback_tool_failure_is_not_success(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "OK"}
        agent = Agent(client)
        with patch("citrus_freellm.agent.execute", return_value={"error": "자료 없음"}):
            self.assertIn("보류", agent.ask("2018년 한라봉 생산량"))
        self.assertIsNone(agent.previous_request)

    def test_ambiguous_followup_does_not_dispatch(self):
        client = Mock()
        agent = Agent(client)
        with patch("citrus_freellm.agent.execute") as dispatch:
            self.assertIn("명시", agent.ask("둘 다 알려줘"))
            dispatch.assert_not_called()
        client.complete.assert_not_called()

    def test_harvest_area_is_not_production_area(self):
        for question in ("2016년 한라봉 수확 면적", "2018년 한라봉 재배면적"):
            plan, blocked = request_for(question)
            self.assertIsNone(blocked)
            self.assertEqual(plan["metrics"], ["생산면적_ha"])
            client = Mock()
            client.complete.return_value = {"role": "assistant", "content": "이미 답변했습니다."}
            answer = Agent(client).ask(question)
            self.assertIn("해당 구분의 통계는 현재 조회 자료에서 확인할 수 없습니다", answer)
            self.assertIn("참고용", answer)
            self.assertIn("생산면적 (ha)", answer)
            self.assertIn("정의가 같은지 확인되지 않았", answer)

    def test_area_definition_notice_survives_year_followup(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "OK"}
        agent = Agent(client)
        agent.ask("2016년 한라봉 수확 면적")
        answer = agent.ask("2018년은?")
        self.assertIn("요청 지표: 수확면적", answer)
        self.assertIn("1,597", answer)
        self.assertIn("참고용", answer)
        answer = agent.ask("생산면적으로 알려줘")
        self.assertNotIn("요청 지표: 수확면적", answer)
        self.assertIn("생산면적 (ha)", answer)

    def test_production_only_does_not_inherit_area_notice(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "OK"}
        agent = Agent(client)
        agent.ask("2018년 한라봉 재배면적")
        answer = agent.ask("생산량은?")
        self.assertNotIn("참고용", answer)
        self.assertNotIn("requested_area_terms", agent.previous_request)

    def test_yield_per_harvest_area_is_still_out_of_scope(self):
        client = Mock()
        answer = Agent(client).ask("2018년 한라봉 수확면적당 생산량")
        self.assertIn("지원하지 않", answer)
        client.complete.assert_not_called()
