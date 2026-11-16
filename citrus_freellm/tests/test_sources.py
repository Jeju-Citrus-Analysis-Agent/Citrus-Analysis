"""Public citations follow README while local evidence stays reproducible."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from citrus_freellm.agent import Agent
from citrus_freellm.insights import explain
from citrus_freellm.sources import readme_source, source_citation


class SourceTests(unittest.TestCase):
    def test_lookup_and_chart_link_public_origin_and_keep_file_hash(self):
        for question in ('2020년 천혜향 생산량', '천혜향 생산량 그래프'):
            agent = Agent()
            answer = agent.ask(question)
            self.assertIn('[제주데이터허브](https://jejudatahub.net)', answer)
            self.assertNotIn('.csv', answer)
            evidence = agent.results[-1]['sources'][0]
            self.assertEqual(evidence['path'], 'data/raw/public/fruit_production.csv')
            self.assertEqual(len(evidence['sha256']), 64)
            self.assertEqual(evidence['data_origin']['url'], 'https://jejudatahub.net')

    def test_distribution_and_analysis_origins(self):
        citation = source_citation({'path': 'data/processed/noji_monthly_2025.csv'})
        self.assertIn('https://jasdc.or.kr/tangerine/day/distribution/tangerine1.htm', citation)
        response = explain('언제 팔면 비싼가?')
        self.assertIn('[제주농산물수급관리센터](https://jasdc.or.kr)', response['text'])
        self.assertIn('분석 근거:', response['text'])
        self.assertIn('github.com', response['sources'][0]['url'])
        self.assertEqual(response['sources'][0]['data_origin']['url'], 'https://jasdc.or.kr')

    def test_uncertain_and_unlinked_origins_remain_explicit(self):
        self.assertIn('추정', source_citation({'path': 'data/processed/jeju_special_crops.csv'}))
        weather = source_citation({'path': 'data/processed/weather_monthly.csv'})
        self.assertIn('기상청 ASOS', weather)
        self.assertIn('https://data.kma.go.kr/data/grnd/selectAsosRltmList.do?pgmNo=36', weather)
        self.assertEqual(source_citation({'path': 'unknown.csv'}), '원문 출처 미확인')

    def test_readme_link_changes_are_used_without_code_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'README.md').write_text('[제주데이터허브](https://example.org/data)', encoding='utf-8')
            with patch('citrus_freellm.sources.repository_root', return_value=root):
                self.assertEqual(readme_source('fruit_production.csv')['url'], 'https://example.org/data')
            (root / 'README.md').unlink()
            with patch('citrus_freellm.sources.repository_root', return_value=root):
                self.assertEqual(source_citation({'path': 'fruit_production.csv'}), '원문 출처 미확인')

    def test_derived_sources_follow_parents_and_specific_publications(self):
        crop = readme_source('data/interim/jeju_special_crops_clean.csv')
        self.assertEqual(crop['lineage'], ['jeju_special_crops_clean.csv', 'jeju_special_crops.csv', 'crop_production.csv'])
        self.assertIn('추정', crop['note'])
        for path, endpoint in (
            ('citrus_production_yearly.csv', '/tangerine/output/output1.htm'),
            ('citrus_processing_yearly.csv', '/tangerine/processing.htm'),
            ('citrus_processing_by_company.csv', '/tangerine/processing.htm'),
            ('citrus_export_yearly.csv', '/tangerine/export.htm'),
        ):
            origin = readme_source('data/processed/' + path)
            self.assertTrue(origin['url'].endswith(endpoint))
            self.assertTrue(origin['transformations'])
            citation = source_citation({'path': path})
            self.assertNotIn('.csv', citation)
            self.assertIn(endpoint, citation)

    def test_metadata_documents_and_reports_do_not_expose_csv_names(self):
        for question in ('어떤 데이터가 있어?', '어떤 데이터가 있어? 자세히',
                         '문서에서 유통처리 찾아줘'):
            agent = Agent()
            answer = agent.ask(question)
            self.assertNotIn('.csv', answer)
            self.assertNotIn('data/processed/', answer)
            if agent.results:
                self.assertEqual(agent.results[-1]['text'], answer)
