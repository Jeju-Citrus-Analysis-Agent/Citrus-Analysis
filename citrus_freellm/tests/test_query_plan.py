import json
import unittest
from unittest.mock import Mock

from citrus_freellm.agent import Agent
from citrus_freellm.guardrails import request_for, lookup_request, render
from citrus_freellm.tools import production


def answer_call(start, end):
    return {"role": "assistant", "tool_calls": [{"id": "p", "type": "function", "function": {
        "name": "production", "arguments": json.dumps({"variety": "천혜향", "start_year": start, "end_year": end})}}]}


class QueryPlanTests(unittest.TestCase):
    def plan(self, question, previous=None):
        plan, blocked = request_for(question, previous)
        self.assertIsNone(blocked)
        return plan

    def test_pair_versus_continuous_range(self):
        for question in ("2016년과 2018년 천혜향 생산량 비교", "2016년, 2018년 천혜향 생산량"):
            plan = self.plan(question)
            self.assertEqual(plan["years"], [2016, 2018])
            self.assertEqual(plan["mode"], "selected")
        for question in ("2016년부터 2018년까지 천혜향 생산량", "2016~2018년 천혜향 생산량", "2016년과 2018년 천혜향 연도별 생산량"):
            plan = self.plan(question)
            self.assertEqual(plan["years"], [2016, 2017, 2018])
            self.assertEqual(plan["mode"], "range")

    def test_selected_answer_excludes_middle_year(self):
        question = "2016년과 2018년 천혜향 생산량 비교"
        plan = self.plan(question)
        answer = render(production(**lookup_request(plan)), plan, question)
        self.assertIn("| 2016 |", answer)
        self.assertIn("| 2018 |", answer)
        self.assertNotIn("| 2017 |", answer)
        self.assertIn("비교 기준: 2016년 → 2018년", answer)

    def test_range_answer_includes_middle_year(self):
        question = "2016년부터 2018년까지 천혜향 연도별 생산량"
        plan = self.plan(question)
        answer = render(production(**lookup_request(plan)), plan, question)
        self.assertIn("| 2017 |", answer)
        self.assertIn("2016~2018년", answer)

    def test_three_discrete_years_do_not_imply_pair_comparison(self):
        plan = self.plan("2015년, 2017년, 2019년 천혜향 생산량")
        self.assertEqual(plan["years"], [2015, 2017, 2019])
        answer = render(production(**lookup_request(plan)), plan, "생산량")
        self.assertNotIn("| 2016 |", answer)
        self.assertNotIn("변화율:", answer)

    def test_area_metric_survives_year_followup(self):
        previous = self.plan("2019년과 2020년 천혜향 생산면적 비교")
        plan = self.plan("그러면 2018년은?", previous)
        self.assertEqual(plan["years"], [2018])
        self.assertEqual(plan["metrics"], ["생산면적_ha"])
        answer = render(production(**lookup_request(plan)), plan, "그러면 2018년은?")
        self.assertIn("생산면적 (ha)", answer)
        self.assertNotIn("생산량 (톤)", answer)
        self.assertIn("천혜향 · 2018년", answer)

    def test_metric_only_followup_retains_year_selection(self):
        previous = self.plan("2016년과 2018년 천혜향 생산량 비교")
        plan = self.plan("면적은?", previous)
        self.assertEqual(plan["years"], [2016, 2018])
        self.assertEqual(plan["metrics"], ["생산면적_ha"])

    def test_both_metrics_and_explicit_override(self):
        previous = self.plan("2019년과 2020년 천혜향 생산량과 면적 비교")
        self.assertEqual(previous["metrics"], ["생산량_톤", "생산면적_ha"])
        self.assertEqual(self.plan("2018년은?", previous)["metrics"], previous["metrics"])
        self.assertEqual(self.plan("생산량만 알려줘", previous)["metrics"], ["생산량_톤"])
        self.assertEqual(self.plan("생산량 말고 면적은?", previous)["metrics"], ["생산면적_ha"])
        self.assertEqual(self.plan("둘 다 알려줘", previous)["metrics"], previous["metrics"])

    def test_metric_only_followup_retains_range(self):
        previous = self.plan("2016~2018년 천혜향 면적")
        plan = self.plan("생산량은?", previous)
        self.assertEqual(plan["years"], [2016, 2017, 2018])
        self.assertEqual(plan["mode"], "range")

    def test_previous_year_comparison(self):
        plan = self.plan("2020년 천혜향 생산량 전년 대비")
        self.assertEqual(plan["years"], [2019, 2020])
        answer = render(production(**lookup_request(plan)), plan, "생산량")
        self.assertIn("+3.16%", answer)

    def test_ambiguous_periods_are_not_silently_inherited(self):
        previous = self.plan("2019년과 2020년 천혜향 생산량 비교")
        for question in ("올해 면적은?", "작년 생산량", "최근 천혜향 생산량", "2020년부터 2019년까지 천혜향 생산량"):
            self.assertIsNotNone(request_for(question, previous)[1])

    def test_end_to_end_area_followup_and_reset(self):
        client = Mock()
        client.complete.side_effect = [answer_call(2019, 2020), answer_call(2018, 2018), answer_call(2018, 2018)]
        agent = Agent(client)
        first = agent.ask("2019년과 2020년 천혜향 생산면적 비교")
        self.assertIn("893", first)
        self.assertIn("894", first)
        self.assertIn("+0.11%", first)
        second = agent.ask("그러면 2018년은?")
        self.assertIn("생산면적 (ha)", second)
        third = agent.ask("생산량은?")
        self.assertIn("생산량 (톤)", third)
        self.assertNotIn("생산면적 (ha)", third)
        agent.reset()
        self.assertIn("명시", agent.ask("면적은?"))
        self.assertEqual(client.complete.call_count, 3)

    def test_missing_year_selection_is_explicit(self):
        question = "2019년과 2021년 천혜향 생산량 비교"
        plan = self.plan(question)
        answer = render(production(**lookup_request(plan)), plan, question)
        self.assertNotIn("| 2020 |", answer)
        self.assertIn("| 2021 | 자료 없음 |", answer)
        self.assertNotIn("변화율:", answer)

    def test_failed_followup_does_not_change_last_verified_plan(self):
        client = Mock()
        client.complete.side_effect = [answer_call(2019, 2020), answer_call(2019, 2020)]
        agent = Agent(client)
        agent.ask("2019년과 2020년 천혜향 면적 비교")
        before = dict(agent.previous_request)
        self.assertIn("보류", agent.ask("2018년 생산량은?"))
        self.assertEqual(agent.previous_request, before)
