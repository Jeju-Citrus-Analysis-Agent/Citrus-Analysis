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

    def test_weather_metrics_share_one_ratio_chart(self):
        agent = Agent()
        agent.ask('2020년 서귀포 날씨 보여줘')
        expected = table_artifacts(agent.results[-1]['text'], '그래프로 그려줘')
        answer = agent.ask('그래프로 그려줘')
        self.assertEqual(agent.last_artifacts, expected)
        # Derived '비교 분석' tables are not charted when the answer's own table exists.
        self.assertEqual(len(agent.last_artifacts), 1)
        chart = agent.last_artifacts[0]
        self.assertEqual(chart['series'], '지표')
        self.assertEqual(chart['y'], '비율(%)')
        metrics = list(dict.fromkeys(row['지표'] for row in chart['data']))
        self.assertEqual(metrics, ['평균 기온(℃)', '강수량(mm)'])  # 관측일 수 is coverage, not a measure
        self.assertEqual(len(chart['data']), 12 * len(metrics))
        for metric in metrics:
            rows = [r for r in chart['data'] if r['지표'] == metric]
            self.assertEqual(max(r['비율(%)'] for r in rows), 100.0)
            peak = max(rows, key=lambda r: r['원래 값'])
            self.assertEqual(peak['비율(%)'], 100.0)
        self.assertIn('비율(%)로', answer)

    def test_ratio_bases(self):
        yearly = ('| 연도 | 품종 | 경영비(만원/10a) | 소득(만원/10a) | 소득 순위(큰 값=1) |\n|---|---|---|---|---|\n'
                  '| 2016 | 노지온주 | 100 | 200 | 1 |\n| 2017 | 노지온주 | 150 | 100 | 1 |\n| 2018 | 노지온주 | 125 | 300 | 1 |\n')
        chart, = table_artifacts(yearly, '그래프로 그려줘')
        self.assertEqual(chart['basis'], '2016 = 100')
        self.assertEqual([r['항목'] for r in chart['data']][:3], ['2016', '2017', '2018'])  # constant 품종 dropped
        self.assertNotIn('소득 순위(큰 값=1)', {r['지표'] for r in chart['data']})
        self.assertEqual([r['비율(%)'] for r in chart['data'] if r['지표'] == '경영비(만원/10a)'], [100.0, 150.0, 125.0])
        negative = yearly.replace('| 2016 | 노지온주 | 100 | 200 |', '| 2016 | 노지온주 | 100 | -50 |')
        chart, = table_artifacts(negative, '선 그래프로 그려줘')
        self.assertIn('절댓값', chart['basis'])
        self.assertEqual(chart['chart_kind'], 'line')
        self.assertEqual([r['비율(%)'] for r in chart['data'] if r['지표'] == '소득(만원/10a)'], [-16.7, 33.3, 100.0])
        single = '| 품종 | 생산량 (톤) |\n|---|---|\n| 한라봉 | 10 |\n| 천혜향 | 20 |\n'
        chart, = table_artifacts(single, '그래프로 그려줘')
        self.assertNotIn('series', chart)  # one metric keeps its own unit
        self.assertEqual(chart['unit'], '톤')

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
