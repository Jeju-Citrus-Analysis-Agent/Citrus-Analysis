import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.analysis import plan_analysis, calculate, render_analysis, validate_calculation, validate_plan


class AnalysisTests(unittest.TestCase):
    def plan(self, text):
        plan, blocked = plan_analysis(text)
        self.assertIsNone(blocked)
        self.assertIsNotNone(plan)
        return plan

    def test_comparison_golden_values(self):
        plan = self.plan("2020년 한라봉과 천혜향 생산량 비교")
        answer = render_analysis(calculate(plan), plan)
        for expected in ("41,222", "18,614", "-22,608.00", "-54.84%"):
            self.assertIn(expected, answer)

    def test_rank_has_defined_group_and_correct_top_three(self):
        plan = self.plan("2020년 만감류 생산량 상위 3개")
        answer = render_analysis(calculate(plan), plan)
        for expected in ("| 1 | 한라봉 | 41,222 |", "| 2 | 천혜향 | 18,614 |", "| 3 | 레드향 | 11,676 |"):
            self.assertIn(expected, answer)
        self.assertNotIn("온주밀감노지", answer)

    def test_average_golden_and_no_weighting(self):
        plan = self.plan("2019년부터 2020년까지 천혜향 생산량 평균")
        answer = render_analysis(calculate(plan), plan)
        self.assertIn("18,329", answer)
        self.assertIn("2개 연도의 산술평균", answer)
        self.assertIn("면적 가중평균이 아닙니다", answer)

    def test_discrete_average_does_not_fill_intermediate_year(self):
        plan = self.plan("2016년과 2018년 천혜향 생산량 평균")
        self.assertEqual(plan["years"], [2016, 2018])
        answer = render_analysis(calculate(plan), plan)
        self.assertIn("14,671.5", answer)

    def test_missing_year_does_not_reduce_denominator(self):
        plan = self.plan("2019~2021년 천혜향 생산량 평균")
        with self.assertRaises(ValueError):
            calculate(plan)

    def test_missing_variety_year_does_not_rank_partial_group(self):
        plan = self.plan("2021년 만감류 생산량 순위")
        with self.assertRaises(ValueError):
            calculate(plan)

    def test_mixed_hierarchy_rejected(self):
        plan, blocked = plan_analysis("2020년 온주밀감노지와 천혜향 생산량 비교")
        self.assertIsNone(plan)
        self.assertIn("집계수준", blocked)

    def test_area_break_average_rejected(self):
        plan, blocked = plan_analysis("2016~2018년 천혜향 생산면적 평균")
        self.assertIsNone(plan)
        self.assertIn("통계 단절", blocked)

    def test_ambiguous_rank_requires_scope(self):
        self.assertIn("비교 대상", plan_analysis("2020년 생산량 순위")[1])

    def test_direct_plan_cannot_bypass_area_break(self):
        plan = self.plan("2019~2020년 천혜향 생산면적 평균")
        plan["years"] = [2016, 2017]
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_computed_value_tampering_blocked(self):
        plan = self.plan("2019~2020년 천혜향 생산량 평균")
        result = calculate(plan)
        result["values"]["천혜향"] = 99999
        with self.assertRaises(ValueError):
            validate_calculation(result, plan)

    def test_evidence_tampering_blocked_even_if_aggregate_matches(self):
        plan = self.plan("2019~2020년 천혜향 생산량 평균")
        result = calculate(plan)
        result["evidence"]["천혜향"]["rows"][0]["생산량_톤"] += 10
        result["evidence"]["천혜향"]["rows"][1]["생산량_톤"] -= 10
        with self.assertRaises(ValueError):
            validate_calculation(result, plan)

    def test_tied_rank_cutoff_includes_all_ties(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            path = root / "data/raw/public/fruit_production.csv"
            path.parent.mkdir(parents=True)
            path.write_text("기준연도,품종대분류,품종소분류,생산면적(ha),생산량(톤)\n"
                            "2020,만감류,한라봉,1,10\n2020,만감류,천혜향,1,10\n2020,만감류,레드향,1,5\n", encoding="utf-8")
            with patch("citrus_freellm.tools.ROOT", root):
                plan = self.plan("2020년 한라봉 천혜향 레드향 생산량 상위 1개")
                answer = render_analysis(calculate(plan), plan)
                self.assertIn("| 1 | 한라봉 | 10 |", answer)
                self.assertIn("| 1 | 천혜향 | 10 |", answer)
                self.assertNotIn("| 3 | 레드향", answer)
                plan["limit"] = 3
                self.assertIn("| 3 | 레드향 | 5 |", render_analysis(calculate(plan), plan))

    def test_agent_calculations_are_local_and_clear_single_context(self):
        client = Mock()
        agent = Agent(client)
        agent.previous_request = {"variety": "천혜향", "start_year": 2019, "end_year": 2019}
        self.assertIn("18,329", agent.ask("2019~2020년 천혜향 생산량 평균"))
        self.assertIsNone(agent.previous_request)
        client.complete.assert_not_called()

    def test_missing_analysis_answer_does_not_invent_numbers(self):
        agent = Agent(Mock())
        self.assertIn("보류", agent.ask("2021년 한라봉 천혜향 생산량 비교"))

    def test_compact_metadata_and_details_preserve_conditions(self):
        agent = Agent(Mock())
        before = {"variety": "천혜향", "start_year": 2019, "end_year": 2019}
        agent.previous_request = before
        short = agent.ask("생산량 데이터는 몇 년까지 있어?")
        self.assertLess(len(short.splitlines()), 12)
        self.assertNotIn("| 자료 |", short)
        full = agent.ask("자세히")
        self.assertIn("| 자료 |", full)
        self.assertEqual(agent.previous_request, before)
        agent.reset()
        self.assertIsNone(agent.last_metadata_question)
