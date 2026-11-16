"""Conclusions must preserve verified numbers and material caveats before details."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from citrus_freellm.agent import Agent
from citrus_freellm.presentation import split_answer, SUMMARY_HEADER
from citrus_freellm.reporting import save_report


class PresentationTests(unittest.TestCase):
    def parts(self, question):
        agent = Agent()
        answer = agent.ask(question)
        summary, details = split_answer(answer)
        self.assertTrue(summary.startswith(SUMMARY_HEADER), answer)
        self.assertTrue(details, answer)
        self.assertNotIn('|', summary)
        return agent, summary, details

    def test_comparison_leads_with_values_and_percentage(self):
        _, summary, details = self.parts('2019년과 2020년 천혜향 생산량 비교')
        for value in ('18,044', '18,614', '+3.16%'):
            self.assertIn(value, summary)
        self.assertIn('| 연도 |', details)
        self.assertIn('출처:', details)

    def test_area_discontinuity_and_definition_stay_visible(self):
        _, summary, _ = self.parts('2016년과 2018년 천혜향 생산면적 비교')
        self.assertIn('증감은 비교하지 않습니다', summary)
        self.assertNotIn('%', summary)
        _, summary, _ = self.parts('2020년 천혜향 수확면적')
        self.assertIn('참고값', summary)

    def test_profit_summary_preserves_cost_basis_and_assumptions(self):
        _, summary, details = self.parts('판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 20% 하락 이익은?')
        self.assertIn('200,000원', summary)
        self.assertIn('3,000원/kg', summary)
        self.assertIn('미래 예측은 아닙니다', summary)
        self.assertIn('계산식:', details)
        _, summary, _ = self.parts('판매량 1000kg, 단가 4000원, 경영비 300만원이면 이익은?')
        self.assertIn('총비용 기준 순이익 아님', summary)

    def test_chart_relationship_and_example_have_real_summaries(self):
        agent, summary, details = self.parts('천혜향 생산량 그래프')
        self.assertIn('10,228', summary)
        self.assertIn('18,614', summary)
        self.assertTrue(agent.last_artifacts)
        _, summary, _ = self.parts('기온과 천혜향 생산량은 관계가 있어?')
        self.assertIn('6개 연도', summary)
        self.assertIn('원인이라는 뜻은 아닙니다', summary)
        _, summary, _ = self.parts('가격이 내려갈 때 이익을 예시로 보여줘')
        for value in ('예시', '600,000', '200,000', '-200,000', '미래 예측이 아닙니다'):
            self.assertIn(value, summary)

    def test_search_failure_is_not_summarized_as_success(self):
        import requests
        with patch('citrus_freellm.local_tools.requests.get', side_effect=requests.Timeout()):
            agent, summary, details = self.parts('인터넷에서 감귤 통계 찾아줘')
        self.assertIn('연결하지 못했습니다', summary)
        self.assertIn('직접', summary)
        self.assertIn('https://', details)
        self.assertFalse(agent.last_trace[0]['success'])

    def test_report_keeps_summary_before_evidence(self):
        agent, summary, details = self.parts('천혜향 생산량 그래프')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch('citrus_freellm.reporting.OUTPUT', Path(folder)):
                paths = save_report(agent.results)
            markdown = next(Path(p).read_text(encoding='utf-8') for p in paths if p.endswith('.md'))
            payload = json.loads(next(Path(p).read_text(encoding='utf-8') for p in paths if p.endswith('.json')))
        self.assertLess(markdown.index('**결론**'), markdown.index('| 연도 |'))
        self.assertEqual(payload['results'][0]['text'], agent.history[-1]['content'])

    def test_simple_greeting_and_error_stay_short(self):
        for question in ('안녕', '2030년 천혜향 생산량 그래프'):
            answer = Agent().ask(question)
            first, details = split_answer(answer)
            self.assertTrue(first)
            self.assertFalse(details)
