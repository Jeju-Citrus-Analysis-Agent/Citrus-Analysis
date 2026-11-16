"""Follow-up charts must reproduce the table the user actually saw."""
import unittest
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.followup_charts import table_artifacts


class FollowupChartTests(unittest.TestCase):
    def test_comparison_reuses_only_displayed_years_without_reading_again(self):
        agent = Agent()
        agent.ask('2019년과 2020년 천혜향 생산량 비교')
        sources = agent.results[-1]['sources']
        with patch('citrus_freellm.local_tools.production', side_effect=AssertionError('must not requery')):
            answer = agent.ask('그래프로 그려줘')
        chart = agent.last_artifacts[0]
        self.assertEqual(chart['data'], [
            {'항목': '2019', '생산량 (톤)': 18044.0},
            {'항목': '2020', '생산량 (톤)': 18614.0}])
        self.assertEqual(agent.results[-1]['sources'], sources)
        self.assertIn('https://jejudatahub.net', answer)
        self.assertNotIn('.csv', answer)
        agent.ask('선 그래프로 보여줘')
        self.assertEqual(agent.last_artifacts[0]['data'], chart['data'])
        self.assertEqual(agent.last_artifacts[0]['chart_kind'], 'line')

    def test_multiple_varieties_and_area_keep_their_metrics(self):
        for question, labels, metric in (
            ('2020년 한라봉과 천혜향 생산량 비교', ['한라봉', '천혜향'], '톤'),
            ('2016년과 2018년 천혜향 생산면적 비교', ['2016', '2018'], 'ha'),
        ):
            agent = Agent()
            agent.ask(question)
            answer = agent.ask('이 표를 그래프로 그려줘')
            self.assertTrue(agent.last_artifacts, answer)
            chart = agent.last_artifacts[0]
            self.assertEqual([r['항목'] for r in chart['data']], labels)
            self.assertEqual(chart['unit'], metric)
            if metric == 'ha':
                self.assertIn('2017년', answer)
                self.assertEqual(chart['chart_kind'], 'bar')

    def test_weather_uses_displayed_rows_and_separate_axes(self):
        agent = Agent()
        agent.ask('2020년 서귀포 날씨 보여줘')
        expected = table_artifacts(agent.results[-1]['text'], '그래프로 그려줘')
        agent.ask('그래프로 그려줘')
        self.assertEqual(agent.last_artifacts, expected)
        self.assertGreaterEqual(len(agent.last_artifacts), 3)
        self.assertTrue(all(len(c['data']) == 12 for c in agent.last_artifacts))
        self.assertEqual(len({c['y'] for c in agent.last_artifacts[:3]}), 3)

    def test_no_table_reset_or_unrelated_answer_never_uses_stale_results(self):
        agent = Agent()
        self.assertIn('앞선 표가 없습니다', agent.ask('그래프로 그려줘'))
        agent.ask('2020년 천혜향 생산량')
        agent.ask('안녕')
        self.assertIn('앞선 표가 없습니다', agent.ask('차트로 보여줘'))
        self.assertFalse(agent.last_artifacts)
        agent.ask('2020년 천혜향 생산량')
        agent.reset()
        self.assertIn('앞선 표가 없습니다', agent.ask('그래프로 그려줘'))

    def test_client_mode_followup_stays_local(self):
        client = Mock()
        agent = Agent(client=client)
        agent.ask('2020년 한라봉과 천혜향 생산량 비교')
        client.reset_mock()
        agent.ask('막대 그래프로 그려줘')
        client.complete.assert_not_called()
        self.assertTrue(agent.last_artifacts)

    def test_missing_values_and_repeated_categories_are_not_zeroed_or_summed(self):
        text = '| 국가 | 수출량 (톤) |\n|---|---|\n| 미국 | 없음 |\n| 미국 | 1,234.5 |'
        chart = table_artifacts(text, '그래프로 그려줘')[0]
        self.assertEqual([r[chart['y']] for r in chart['data']], [None, 1234.5])
        self.assertNotEqual(chart['data'][0]['항목'], chart['data'][1]['항목'])

    def test_explicit_new_chart_question_overrides_previous_table(self):
        agent = Agent()
        agent.ask('2020년 천혜향 생산량')
        agent.ask('2019년 한라봉 생산량 그래프 그려줘')
        self.assertIn('한라봉', agent.last_artifacts[0]['title'])
        self.assertEqual(len(agent.last_artifacts[0]['data']), 1)
