"""Explicit follow-ups, original question context, and non-destructive number help."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from citrus_freellm.agent import Agent
from citrus_freellm import local_tools as lt
from citrus_freellm.usability import (source_availability, availability_signature, followup_context,
                                     comparison_followup, chart_followup, snapshot_context,
                                     restore_context, korean_number, number_hints)
from citrus_freellm.usability import unit_hints


class UsabilityTests(unittest.TestCase):
    def test_followup_keeps_years_variety_and_supported_comparison(self):
        question = '2019년과 2020년 천혜향 생산량 비교'
        agent = Agent()
        agent.ask(question)
        context = followup_context(question, agent, source_availability())
        self.assertEqual(context['variety'], '천혜향')
        self.assertEqual(context['years'], [2019, 2020])
        self.assertEqual(context['anchor'], 2020)
        self.assertIn('2019, 2020년 천혜향', chart_followup(context))
        self.assertEqual(comparison_followup(context, 2018), '2020년과 2018년 천혜향 생산량 비교')
        with self.assertRaises(ValueError):
            comparison_followup(context, 2030)

    def test_area_comparison_never_crosses_2017_break(self):
        for year, expected in ((2016, [2015]), (2018, [2017, 2019, 2020])):
            question = f'{year}년 천혜향 생산면적'
            agent = Agent()
            agent.ask(question)
            context = followup_context(question, agent, source_availability())
            self.assertEqual(context['metric'], '생산면적')
            self.assertEqual(context['compare_years'], expected)

    def test_replaying_followup_restores_original_assumptions(self):
        agent = Agent()
        agent.ask('판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 10% 하락 이익은?')
        before = snapshot_context(agent)
        agent.ask('판매량 2000kg, 단가 5000원, 총비용 300만원이면 이익은?')
        restore_context(agent, before)
        answer = agent.ask('그럼 단가 20% 하락이면?')
        self.assertIn('200,000원', answer)
        self.assertEqual(before['scenario']['price_won_kg'], '4000')
        self.assertEqual(before['scenario']['changes']['price_won_kg'], '-10')
        self.assertEqual(agent.scenario['changes']['price_won_kg'], '-20')

    def test_coverage_reads_actual_files_and_invalidates_on_change(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            path = root / 'weather.csv'
            path.write_text('연월,평균기온_c\n2022-01-01,5\n2024-02-01,8\n', encoding='utf-8')
            with patch.object(lt, 'ROOT', root), \
                 patch.object(lt, 'DATASETS', {'weather': ('weather.csv', '날씨', '연월')}):
                initial = availability_signature()
                records = source_availability()
                self.assertEqual(records[0]['years'], [2022, 2024])
                self.assertEqual(records[0]['period'], '2022-01~2024-02')
                path.write_text('연월,평균기온_c\n2023-01-01,12\n', encoding='utf-8')
                self.assertNotEqual(availability_signature(), initial)
                self.assertEqual(source_availability()[0]['years'], [2023])

    def test_number_hints_keep_values_sign_and_units(self):
        for value, expected in ((18614, '1만 8,614'), (1000000, '100만'),
                                (-200000, '-20만'), ('18614.5', '1만 8,614.5')):
            self.assertEqual(korean_number(value), expected)
        text = '**18,614톤**, **1,000,000원**, **-200,000원** · 2020년 · 10%'
        hints = number_hints(text)
        self.assertEqual(len(hints), 3)
        self.assertIn('18,614톤 = 1만 8,614톤', hints)
        self.assertIn('-200,000원 = -20만원', hints)
        self.assertNotIn('2020', ' '.join(hints))
        self.assertEqual(text, '**18,614톤**, **1,000,000원**, **-200,000원** · 2020년 · 10%')

    def test_unit_help_is_specific_to_answer_and_ignores_search_urls(self):
        self.assertEqual(unit_hints('안녕하세요!'), [])
        self.assertEqual(unit_hints('검색 링크 https://example.com/?q=%ED%86%A4'), [])
        weight = unit_hints('생산량은 18,614톤입니다.')
        self.assertEqual(weight, ['1톤 = 1,000kg입니다.'])
        self.assertTrue(any('1kg당' in h for h in unit_hints('단가 4,000원/kg')))
        self.assertTrue(any('5kg 기준' in h for h in unit_hints('평균가_원_5kg')))
        self.assertTrue(any('면적' in h for h in unit_hints('생산면적(ha)')))
        self.assertTrue(any('섭씨' in h for h in unit_hints('평균 기온(℃)')))
