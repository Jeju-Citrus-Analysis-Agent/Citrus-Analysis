"""Verify baseline, units, missing observations, and automatic comparison scope."""
import unittest

import pandas as pd

from citrus_freellm.agent import Agent
from citrus_freellm.comparisons import data_comparison, weather_comparison, pair_rows
from citrus_freellm.followup_charts import displayed_tables
from citrus_freellm.presentation import split_answer


class ComparisonTests(unittest.TestCase):
    def test_real_registered_queries_add_comparisons(self):
        for question in ('2020년 제주 날씨 보여줘', '2020년 수출 자료 보여줘',
                         '2020년 가공 자료 보여줘', '2025년 월별 가격 보여줘',
                         '2025년 1월 일별 가격 보여줘'):
            with self.subTest(question=question):
                agent = Agent()
                answer = agent.ask(question)
                self.assertIn('**비교 분석**', answer)
                self.assertIn('출처:', answer)
                self.assertTrue(agent.results, answer)
                self.assertNotIn('처리를 보류했습니다', answer)

    def test_single_year_lookup_compares_without_changing_followup_context(self):
        agent = Agent()
        answer = agent.ask('2020년 천혜향 생산량')
        summary, details = split_answer(answer)
        for expected in ('2019', '18,044', '18,614', '+3.16%'):
            self.assertIn(expected, summary)
        self.assertEqual(agent.previous_request['years'], [2020])
        self.assertEqual(agent.results[-1]['conditions']['years'], [2020])
        self.assertEqual(len(displayed_tables(details)), 1)

    def test_area_automatic_baseline_stays_on_same_side_of_2017(self):
        answer = Agent().ask('2017년 천혜향 생산면적')
        summary, _ = split_answer(answer)
        self.assertIn('2017', summary)
        self.assertIn('2018', summary)
        self.assertNotIn('2016', summary)

    def test_weather_matches_months_and_excludes_incomplete_observations(self):
        full = pd.DataFrame({
            '지점명': ['제주'] * 4,
            '연월': ['2019-01-01', '2019-02-01', '2020-01-01', '2020-02-01'],
            '관측일수': [31, 28, 31, 20],
            '평균기온_c': [-2., 5., 2., 7.], '강수량_mm': [0., 100., 20., 50.]})
        lead, body = weather_comparison(full.iloc[2:].copy(), full)
        self.assertIn('2019년 → 2020년', lead)
        self.assertIn('+4℃', lead)
        self.assertIn('관측일이 부족한 1개 월', body)
        self.assertIn('공통 항목 1개', body)
        self.assertIn('기준값이 0', body)
        tables = displayed_tables(body)
        temperature = next(header for header, _ in tables if any('기온' in c for c in header))
        self.assertFalse(any('변화율' in c for c in temperature))

    def test_multiple_stations_are_compared_on_same_dates(self):
        frame = pd.DataFrame({'지점명': ['제주', '서귀포'], '연월': ['2020-01-01'] * 2,
                              '관측일수': [31, 31], '평균기온_c': [5., 8.], '강수량_mm': [20., 30.]})
        lead, body = weather_comparison(frame, frame)
        self.assertIn('서귀포 → 제주', lead)
        self.assertIn('같은 월', body)
        self.assertIn('-3℃', lead)

    def test_exports_do_not_sum_total_rows_or_zero_missing_countries(self):
        full = pd.DataFrame({'연도': [2019] * 3 + [2020] * 4,
                             '국가': ['합계', 'A', 'B', '합계', 'A', 'B', 'C'],
                             '수출량_톤': [1000., 0., 10., 2000., 5., 20., 5.],
                             '수출액_천달러': [999., 0., 1., 888., 2., 3., 4.]})
        lead, body = data_comparison('exports', full[full['연도'] == 2020], full, '2020년 수출 보여줘')
        self.assertIn('공통 항목 2개', body)
        self.assertIn('한쪽에만 있는 1개', body)
        self.assertNotIn('| 합계 |', body)
        self.assertNotIn('| C |', body)
        self.assertIn('기준값이 0', body)
        self.assertIn('+100.00%', lead)

    def test_duplicate_keys_and_percentage_points(self):
        before = pd.DataFrame({'항목': ['가공률'], '값': [30.]})
        after = pd.DataFrame({'항목': ['가공률'], '값': [40.]})
        lead, body = pair_rows(before, after, ['항목'], [('값', '가공률', '%', False)], '이전', '현재')
        self.assertIn('+10퍼센트포인트', lead)
        self.assertNotIn('변화율', body)
        _, body = pair_rows(pd.concat([before, before], ignore_index=True), after, ['항목'],
                            [('값', '가공률', '%', False)], '이전', '현재')
        self.assertIn('중복', body)
        self.assertIn('보류', body)

    def test_price_keeps_same_day_variety_and_box_unit(self):
        full = pd.DataFrame({'품종': ['노지'] * 4, '날짜': ['2019-01-01', '2019-02-01', '2020-01-01', '2020-02-01'],
                             '합계_출하량_톤': [1., 3., 2., 4.], '합계_평균가_원_5kg': [1000., 3000., 1100., 4000.]})
        lead, body = data_comparison('price', full.iloc[[2]], full, '2020년 1월 일별 가격 보여줘')
        self.assertIn('01-01', body)
        self.assertNotIn('02-01', body)
        self.assertIn('원/5kg', body)
        self.assertIn('+10.00%', lead)

    def test_monthly_extremes_exclude_total(self):
        frame = pd.DataFrame({'품종구분': ['노지'] * 3, '산지연도': ['2025년산'] * 3,
                              '월구분': ['계', '9월', '10월'], '평균가_원_5kg': [999999., 100., 200.],
                              '출하량_톤': [888888., 1., 3.]})
        lead, body = data_comparison('monthly_price', frame, frame, '월별 가격 보여줘')
        self.assertIn('10월', lead)
        self.assertNotIn('999,999', body)
        self.assertNotIn('888,888', body)
        self.assertIn('단순 평균하지 않았습니다', body)

    def test_non_numeric_question_does_not_invent_comparison(self):
        answer = Agent().ask('안녕')
        self.assertNotIn('비교 분석', answer)
        answer = Agent().ask('2028년 날씨 예측해줘')
        self.assertNotIn('**비교 분석**', answer)


if __name__ == '__main__':
    unittest.main()
