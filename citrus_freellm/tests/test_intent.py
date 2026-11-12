import json
import unittest
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.guardrails import request_for
from citrus_freellm.intent import decode, interpret, resolve


def proposal(year="inherit", metric="inherit", yq="", mq="", action="lookup"):
    return dict(action=action, year_operation=year, metric_operation=metric,
                year_quote=yq, metric_quote=mq)


def model_reply(value):
    return {"role": "assistant", "tool_calls": [{"id": "i", "type": "function", "function": {
        "name": "interpret_intent", "arguments": json.dumps(value, ensure_ascii=False)}}]}


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.single = request_for("2019년 천혜향 생산면적")[0]
        self.pair = request_for("2019년과 2020년 천혜향 생산량과 면적 비교")[0]

    def test_previous_year_computed_locally(self):
        plan, blocked = resolve("그 전해는?", self.single,
                                proposal("previous_year", yq="그 전해"))
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2018])
        self.assertEqual(plan["metrics"], ["생산면적_ha"])

    def test_how_much_grew_means_production(self):
        plan, blocked = resolve("천혜향은 그 전해에 얼마나 났어?", self.single,
                                proposal("previous_year", "production", "그 전해", "얼마나 났어"))
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2018])
        self.assertEqual(plan["metrics"], ["생산량_톤"])

    def test_excluding_metric(self):
        for question, op, quote, expected in (
            ("면적만 빼고 보여줘", "exclude_area", "면적만 빼고", ["생산량_톤"]),
            ("생산량은 제외하고", "exclude_production", "생산량은 제외하고", ["생산면적_ha"]),
        ):
            plan, blocked = resolve(question, self.pair, proposal(metric=op, mq=quote))
            self.assertIsNone(blocked)
            self.assertEqual(plan["metrics"], expected)
            self.assertEqual(plan["years"], [2019, 2020])

    def test_two_year_difference_uses_exact_previous_pair(self):
        plan, blocked = resolve("두 해 차이는?", self.pair, proposal(action="compare"))
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2019, 2020])
        self.assertEqual(plan["metrics"], ["생산량_톤", "생산면적_ha"])

    def test_previous_year_compare(self):
        plan, blocked = resolve("그 전해와 비교하면?", self.single,
                                proposal("compare_previous_year", yq="그 전해", action="compare"))
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2018, 2019])

    def test_ambiguous_relative_anchor(self):
        for previous in (None, self.pair):
            plan, blocked = resolve("그 전해는?", previous, proposal("previous_year", yq="그 전해"))
            self.assertIsNone(plan)
            self.assertIn("기준", blocked)

    def test_compare_requires_pair(self):
        self.assertIsNotNone(resolve("두 해 차이는?", self.single, proposal(action="compare"))[1])

    def test_cannot_exclude_last_remaining_metric(self):
        plan, blocked = resolve("면적만 빼고", self.single, proposal(metric="exclude_area", mq="면적만 빼고"))
        self.assertIsNone(plan)
        self.assertIn("남는 지표", blocked)

    def test_provenance_and_enum_injection_rejected(self):
        value = proposal("previous_year", yq="없는 문구")
        self.assertIsNone(resolve("이전 조건으로 알려줘", self.single, value)[0])
        for bad in (dict(value, year_operation="execute_python"), dict(value, sql="DELETE"), dict(value, action=True)):
            with self.assertRaises(ValueError):
                decode(model_reply(bad))

    def test_absolute_year_not_replaced_by_model(self):
        plan, blocked = resolve("2018년 수확량", self.single,
                                proposal("inherit", "production", mq="수확량"))
        self.assertIsNone(plan)
        self.assertIsNotNone(blocked)
        plan, blocked = resolve("2018년 수확량", self.single,
                                proposal("explicit", "production", mq="수확량"))
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2018])

    def test_missing_metric_grounding_rejected(self):
        # With no metric cue in the question, use the last verified metric;
        # the model cannot silently switch from area to production.
        plan, blocked = resolve("그 전해는?", self.single,
                                proposal("previous_year", "production", "그 전해", ""))
        self.assertIsNone(blocked)
        self.assertEqual(plan["metrics"], ["생산면적_ha"])
        self.assertIsNone(resolve("수확량은?", self.single, proposal())[0])

    def test_malformed_or_missing_model_call_clarifies(self):
        for reply in ({"role": "assistant", "content": "수치는 999999다."},
                      {"role": "assistant", "tool_calls": []},
                      {"role": "assistant", "tool_calls": [{"function": {"name": "production"}}]}):
            client = Mock()
            client.complete.return_value = reply
            plan, blocked = interpret("그 전해는?", self.single, client)
            self.assertIsNone(plan)
            self.assertIsNotNone(blocked)

    def test_structured_json_without_tool_call(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": json.dumps(proposal("previous_year", yq="그 전해"))}
        plan, blocked = interpret("그 전해는?", self.single, client)
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2018])

    def test_end_to_end_interpretation_then_verified_render(self):
        client = Mock()
        agent = Agent(client)
        agent.previous_request = self.pair
        client.complete.return_value = model_reply(proposal(metric="exclude_area", mq="면적만 빼고"))
        answer = agent.ask("면적만 빼고 보여줘")
        self.assertIn("18,044", answer)
        self.assertIn("+3.16%", answer)
        self.assertNotIn("생산면적 (ha)", answer)
        self.assertEqual(client.complete.call_count, 1)

    def test_ambiguous_interpretation_never_dispatches_or_changes_state(self):
        client = Mock()
        client.complete.return_value = model_reply(proposal("previous_year", yq="그 전해"))
        agent = Agent(client)
        agent.previous_request = self.pair
        with patch("citrus_freellm.agent.execute") as execute:
            self.assertIn("기준", agent.ask("그 전해는?"))
            execute.assert_not_called()
        self.assertEqual(agent.previous_request, self.pair)

    def test_source_verification_still_required(self):
        client = Mock()
        client.complete.return_value = model_reply(proposal("previous_year", yq="그 전해"))
        agent = Agent(client)
        agent.previous_request = self.single
        with patch("citrus_freellm.agent.execute", return_value={"error": "bad"}):
            self.assertIn("보류", agent.ask("그 전해는?"))
        self.assertEqual(agent.previous_request, self.single)

    def test_live_failure_two_years_is_not_previous_year(self):
        wrong = proposal("compare_previous_year", "both", "전년", "생산량과면적", "compare")
        plan, blocked = resolve("두 해 차이는?", self.pair, wrong)
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2019, 2020])
        self.assertEqual(plan["metrics"], ["생산량_톤", "생산면적_ha"])

    def test_live_failure_missing_quote_recovers_from_exact_anchor(self):
        plan, blocked = resolve("그 전해는?", self.single, proposal("previous_year", "area"))
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2018])
        self.assertEqual(plan["metrics"], ["생산면적_ha"])
