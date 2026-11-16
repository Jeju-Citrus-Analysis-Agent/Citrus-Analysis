"""경영비·물가 보정·손익분기(노트북 03·04) 지원 회귀 테스트. 모델·네트워크를 쓰지 않는다."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch


from citrus_freellm import cost_tools
from citrus_freellm.agent import Agent
from citrus_freellm.evaluate import run_local_case
from citrus_freellm.insights import explain, load_knowledge, retrieve
from citrus_freellm.local_tools import ToolUnavailable, choose_tool, read_source, table
from citrus_freellm.tools import ROOT

CASES = Path(__file__).resolve().parents[1] / 'cost_evaluation_cases.json'
HAS_COST_DATA = (ROOT / cost_tools.STANDARD_INCOME).is_file() and (ROOT / cost_tools.CPI).is_file()


class CostKnowledgeTests(unittest.TestCase):
    def test_new_cards_load_with_verified_quotes(self):
        cards, sources = load_knowledge()
        ids = {card['id'] for card in cards}
        self.assertLessEqual({'cost_income', 'inflation_real', 'breakeven', 'income_decomposition',
                              'standard_vs_average', 'variety_cost_index'}, ids)
        self.assertIn('cost_analysis_04', sources)

    def test_retrieval_routes_explanation_questions(self):
        for question, expected in (('제주 생산량이 몇 톤 넘으면 노지 농가가 적자야?', 'breakeven'),
                                   ('하우스온주 소득이 왜 줄었어?', 'income_decomposition'),
                                   ('표준소득표 총수입이랑 제주 평균 차이는?', 'standard_vs_average'),
                                   ('가격이 오른 건 물가 때문이야?', 'inflation_real'),
                                   ('품종별 경영비 물가는 어때?', 'variety_cost_index'),
                                   ('어떤 품종이 제일 돈 돼?', 'cost_income')):
            with self.subTest(question=question):
                self.assertIn(expected, retrieve(question))

    def test_revenue_card_no_longer_claims_costs_are_missing(self):
        answer = explain('어떤 품종이 면적당 매출이 높나?')['text']
        self.assertIn('9년 중 6년', answer)
        self.assertNotIn('비용이 확보되면', answer)

    def test_summary_leads_with_asked_variety(self):
        summary = explain('하우스온주 소득이 왜 줄었어?')['text'].split('**세부 설명**')[0]
        self.assertIn('하우스온주: 가격(−121)', summary)

    def test_noji_only_analysis_is_flagged_for_other_varieties(self):
        self.assertIn('노지온주 자료입니다', explain('천혜향은 생산량이 몇 톤 넘으면 적자야?')['text'])


class CostRoutingTests(unittest.TestCase):
    def test_lookup_vs_explanation_vs_scenario(self):
        self.assertEqual(choose_tool('노지온주 경영비 알려줘'), 'cost')
        self.assertEqual(choose_tool('2024년산 품종별 소득 비교해줘'), 'cost')
        self.assertEqual(choose_tool('노지온주 손익분기 단가는?'), 'cost')
        for question in ('하우스온주 소득이 왜 줄었어?', '제주 생산량이 몇 톤 넘으면 노지 농가가 적자야?',
                         '판매량 10000kg 단가 1500원 경영비 1200만원이면 손익분기 단가는?',
                         '내년 노지온주 소득 예측해줘', '품종별 경영비 물가는 어때?'):
            with self.subTest(question=question):
                self.assertNotEqual(choose_tool(question), 'cost')

    def test_scenario_without_numbers_prefers_analysis(self):
        agent = Agent()
        answer = agent.ask('경영비 빼면 어떤 품종 소득이 높아?')
        self.assertEqual(agent.results[-1]['kind'], 'analysis_explanation')
        self.assertNotIn('가정 계산에 필요한 입력', answer)


@unittest.skipUnless(HAS_COST_DATA, '표준소득표·CPI 파일이 없는 환경 (git 제외 자료)')
class CostLookupTests(unittest.TestCase):
    def lookup(self, question):
        return cost_tools.cost_result(question, read_source, table, ToolUnavailable)

    def test_breakeven_matches_notebook_formula(self):
        text, sources, summary, plan, charts = self.lookup('노지온주 손익분기 단가는?')
        self.assertEqual(plan['kind'], 'breakeven')
        self.assertIn('885원/kg', summary)
        self.assertIn('2,229원/kg', summary)
        self.assertIn('0.96~1.41배', summary)
        chart, = charts  # actual price and both break-even prices share one 원/kg axis
        self.assertEqual({row['지표'] for row in chart['data']},
                         {'실제 단가(원/kg)', '경영비 손익분기(원/kg)', '생산비 손익분기(원/kg)'})
        self.assertEqual(chart['unit'], '원/kg')

    def test_real_price_reproduces_cpi_change(self):
        _, sources, summary, _, _ = self.lookup('물가 보정한 노지온주 실질 단가 알려줘')
        self.assertIn('+26.8%', summary)
        self.assertEqual({s['path'] for s in sources}, {cost_tools.PRODUCTION, cost_tools.CPI})

    def test_missing_variety_year_is_reported(self):
        with self.assertRaises(ToolUnavailable) as caught:
            self.lookup('황금향 2020년 소득')
        self.assertIn('2022~2024년산만', str(caught.exception))

    def test_broken_identity_is_rejected(self):
        frame, source = read_source(cost_tools.STANDARD_INCOME)
        broken = frame.copy()
        broken.loc[0, '소득_원_10a'] += 1000

        def fake_read(relative):
            return (broken, source) if relative == cost_tools.STANDARD_INCOME else read_source(relative)
        with self.assertRaises(ValueError):
            cost_tools.cost_result('노지온주 소득', fake_read, table, ToolUnavailable)

    def test_rank_column_and_particles(self):
        text, _, summary, _, _ = self.lookup('2024년산 품종별 소득 비교해줘')
        self.assertIn('소득 순위(큰 값=1)', text)
        _, _, summary, _, _ = self.lookup('천혜향 2020년부터 2024년까지 소득 보여줘')
        self.assertIn('소득은', summary)
        self.assertNotIn('소득는', summary)

    def test_cost_explanations_come_with_a_verified_chart(self):
        for question, title in (('가격이 오른 건 물가 때문이야?', '명목 단가와 물가 보정 단가'),
                                ('경영비 빼면 어떤 품종이 좋아?', '품종별 소득 추이'),
                                ('하우스온주 소득이 왜 줄었어?', '(2020년 물가)')):
            with self.subTest(question=question):
                agent = Agent()
                agent.ask(question)
                self.assertEqual(agent.results[-1]['kind'], 'analysis_explanation')
                self.assertTrue(any(title in chart['title'] for chart in agent.last_artifacts), agent.last_artifacts)

    def test_offline_evaluation_cases_pass(self):
        for case in json.loads(CASES.read_text(encoding='utf-8')):
            with self.subTest(case=case['id']), \
                 patch('requests.post', side_effect=AssertionError('external POST')), \
                 patch('requests.get', side_effect=AssertionError('external GET')):
                result = run_local_case(case)
                self.assertTrue(result['passed'], json.dumps(result['checks'], ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
