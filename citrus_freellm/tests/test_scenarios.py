import unittest
from decimal import Decimal
from unittest.mock import Mock

from citrus_freellm.agent import Agent
from citrus_freellm.scenarios import parse_scenario, compute, render_scenario

BASE = "판매량 1,000kg, 단가 4,000원, 총비용 300만원"


class ScenarioTests(unittest.TestCase):
    def plan(self, question, previous=None):
        plan, blocked = parse_scenario(question, previous)
        self.assertIsNone(blocked)
        return plan

    def test_price_down_ten_percent_golden(self):
        plan = self.plan(BASE + "이라면 단가가 10% 떨어질 때 이익은?")
        result = compute(plan)
        self.assertEqual(result["before"]["profit"], Decimal(1000000))
        self.assertEqual(result["after"]["profit"], Decimal(600000))
        self.assertEqual(result["changed"]["price_won_kg"], Decimal(3600))

    def test_break_even_no_price_needed(self):
        plan = self.plan("판매 가능한 양이 1,000kg이고 총비용이 300만원이면 손해를 피할 최소 단가는?")
        self.assertEqual(compute(plan)["break_even"], Decimal(3000))
        self.assertNotIn("before", compute(plan))

    def test_price_and_cost_changes(self):
        plan = self.plan(BASE + ", 단가가 10% 내려가고 비용이 5% 오르면 이익은?")
        result = compute(plan)
        self.assertEqual(result["after"]["profit"], Decimal(450000))
        self.assertEqual(result["changed_break_even"], Decimal(3150))

    def test_followup_does_not_accumulate_percentages(self):
        previous = self.plan(BASE + ", 단가 10% 하락 이익")
        updated = self.plan("그럼 단가가 20% 떨어지면?", previous)
        self.assertEqual(compute(updated)["changed"]["price_won_kg"], Decimal(3200))
        self.assertEqual(compute(updated)["after"]["profit"], Decimal(200000))

    def test_tonnes_and_thousand_currency(self):
        result = compute(self.plan("판매량 1톤, 단가 4천원, 총비용 0.03억원 이익"))
        self.assertEqual(result["before"]["profit"], Decimal(1000000))

    def test_operating_cost_not_called_net_profit(self):
        plan = self.plan("판매량 1000kg, 단가 4000원, 경영비 300만원 이익")
        answer = render_scenario(plan)
        self.assertIn("경영비 차감 잔여액", answer)
        self.assertIn("총비용 기준 순이익 아님", answer)

    def test_negative_and_zero_quantities_blocked(self):
        for quantity in ("0", "-1"):
            plan, blocked = parse_scenario(f"판매량 {quantity}kg, 단가 4000원, 총비용 300만원")
            self.assertIsNone(plan)
            self.assertIsNotNone(blocked)

    def test_more_than_total_decrease_and_zero_after_quantity(self):
        for suffix in ("단가 101% 하락", "수량 100% 감소"):
            plan, blocked = parse_scenario(BASE + ", " + suffix)
            self.assertIsNone(plan)
            self.assertIsNotNone(blocked)

    def test_explicit_inputs_required_and_no_production_to_sales_assumption(self):
        for question in ("총비용 300만원이면 이익은?", "생산량 1000kg, 단가 4000원, 총비용 300만원 이익"):
            plan, blocked = parse_scenario(question)
            self.assertIsNone(plan)
            self.assertIn("판매가능수량", blocked)

    def test_box_price_not_silently_used_as_per_kg(self):
        plan, blocked = parse_scenario("판매량 1000kg, 단가 20000원/5kg, 총비용 300만원")
        self.assertIsNone(plan)
        self.assertIn("원/kg", blocked)

    def test_unparsed_followup_not_silently_ignored(self):
        previous = self.plan(BASE + ", 단가 10% 하락")
        for question in ("단가 20퍼센트 하락", "총비용 500", "수량 2상자"):
            self.assertIsNone(parse_scenario(question, previous)[0])

    def test_no_external_call_and_reset(self):
        client = Mock()
        agent = Agent(client)
        answer = agent.ask(BASE + ", 단가 10% 하락 이익")
        self.assertIn("600,000", answer)
        self.assertEqual(agent.results[-1]["kind"], "user_scenario")
        client.complete.assert_not_called()
        agent.reset()
        self.assertIsNone(agent.scenario)
        self.assertEqual(agent.results, [])

    def test_private_scenario_not_in_later_model_history(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "OK"}
        agent = Agent(client)
        agent.ask("판매량 1000kg, 단가 4000원, 총비용 399만원 이익")
        agent.ask("2019년 천혜향 생산량")
        messages = str(client.complete.call_args.args[0])
        self.assertNotIn("399만원", messages)
        self.assertNotIn("3,990,000", messages)

    def test_generic_cost_is_still_a_local_scenario(self):
        plan = self.plan("판매량 1000kg, 단가 4000원, 비용 300만원 이익")
        self.assertEqual(compute(plan)["before"]["profit"], Decimal(1000000))

    def test_unstructured_private_money_not_sent_to_model(self):
        client = Mock()
        answer = Agent(client).ask("2019년 한라봉 생산량 알려줘. 우리 비용 987만원이야.")
        client.complete.assert_not_called()
        self.assertNotIn("원자료", answer)

    def test_future_dated_assumption_is_not_blocked_as_forecast(self):
        plan = self.plan(BASE + ", 내년에 단가가 10% 떨어진다고 가정하면 이익은?")
        self.assertEqual(compute(plan)["after"]["profit"], Decimal(600000))

    def test_per_area_cost_not_used_as_whole_farm_total(self):
        plan, blocked = parse_scenario("판매량 1000kg, 단가 4000원, 총비용 300만원/10a 이익")
        self.assertIsNone(plan)
        self.assertIn("면적당", blocked)
