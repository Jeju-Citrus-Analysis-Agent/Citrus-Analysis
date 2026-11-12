import unittest
from unittest.mock import Mock, patch

from citrus_freellm.analysis import plan_analysis, categories
from citrus_freellm.agent import Agent
from citrus_freellm.guardrails import request_for
from citrus_freellm.intent import resolve
from citrus_freellm.client import LazyFreeLLMClient


class AuditRegressions(unittest.TestCase):
    def test_other_fruit_ranking_uses_whole_group(self):
        plan, blocked = plan_analysis("2020년 기타과수 생산량 순위")
        self.assertIsNone(blocked)
        expected = {name for name, (_, level) in categories().items() if level == "기타과수"}
        self.assertEqual(set(plan["varieties"]), expected)
        self.assertGreater(len(plan["varieties"]), 1)

    def test_malformed_period_not_treated_as_three_selected_years(self):
        plan, blocked = plan_analysis("2015년부터 2017년까지 2019년 천혜향 생산량 평균")
        self.assertIsNone(plan)
        self.assertIsNotNone(blocked)

    def test_named_member_in_group_not_silently_ranked_alone(self):
        plan, blocked = plan_analysis("2020년 만감류 중 천혜향 생산량 순위")
        self.assertIsNone(plan)
        self.assertIn("전체", blocked)

    def test_previous_year_does_not_subtract_twice(self):
        seed = request_for("2019년 천혜향 생산량")[0]
        proposed = dict(action="lookup", year_operation="previous_year", metric_operation="inherit",
                        year_quote="그 전년", metric_quote="")
        plan, blocked = resolve("그 전년은?", seed, proposed)
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2018])

    def test_missing_analysis_year_explains_which_year(self):
        answer = Agent(Mock()).ask("2019년부터 2021년까지 천혜향 생산량 평균")
        self.assertIn("2021", answer)
        self.assertIn("자료", answer)
        self.assertIn("보류", answer)

    def test_local_analysis_does_not_require_api_configuration(self):
        with patch("citrus_freellm.client.FreeLLMClient", side_effect=ValueError("키 없음")) as factory:
            agent = Agent(LazyFreeLLMClient())
            self.assertIn("2015~2020", agent.ask("생산량 데이터는 몇 년까지 있어?"))
            self.assertIn("18,329", agent.ask("2019~2020년 천혜향 생산량 평균"))
            factory.assert_not_called()
            with self.assertRaises(RuntimeError):
                agent.ask("2019년 천혜향 생산량")
            self.assertIn("18,329", agent.ask("2019~2020년 천혜향 생산량 평균"))

    def test_named_variety_rank_still_uses_explicit_selection(self):
        plan, blocked = plan_analysis("2020년 한라봉 천혜향 생산량 순위")
        self.assertIsNone(blocked)
        self.assertEqual(plan["varieties"], ["한라봉", "천혜향"])

    def test_three_selected_years_average_remains_valid(self):
        plan, blocked = plan_analysis("2015년 2017년 2019년 천혜향 생산량 평균")
        self.assertIsNone(blocked)
        self.assertEqual(plan["years"], [2015, 2017, 2019])
