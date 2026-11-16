"""Exercise every public example, numerical checks and keyless failure paths."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

from citrus_freellm.agent import Agent
from citrus_freellm import local_tools as lt

RSS = b'''<rss><channel>
<item><title>Official statistics</title><link>https://kosis.kr/example</link></item>
<item><title>Untrusted</title><link>https://kosis.kr.evil.example/</link></item>
<item><title>HTTP</title><link>http://kosis.kr/</link></item>
<item><title>Other</title><link>https://example.com/</link></item>
</channel></rss>'''


class LocalToolTests(unittest.TestCase):
    def test_all_twenty_examples_work_without_model_or_key(self):
        with patch.dict('os.environ', {'FREELLMAPI_API_KEY': '', 'OPENAI_API_KEY': ''}), \
             patch('citrus_freellm.client.FreeLLMClient.complete', side_effect=AssertionError('model call')), \
             patch('requests.post', side_effect=AssertionError('external POST')), \
             patch.object(lt.requests, 'get') as get:
            get.return_value.content = RSS
            for name, title, questions in lt.TOOL_GUIDE:
                for question in questions:
                    with self.subTest(tool=name, question=question):
                        agent = Agent()
                        answer = agent.ask(question)
                        self.assertTrue(answer)
                        self.assertEqual(agent.last_trace[0]['tool'], title)
                        self.assertTrue(agent.last_trace[0]['success'], answer)
                        if name != 'conversation':
                            self.assertEqual(agent.results[-1]['conditions']['tool'], name)

    def test_chart_uses_verified_values_and_keeps_data(self):
        agent = Agent()
        answer = agent.ask('2019년과 2020년 천혜향 생산량 그래프')
        self.assertIn('18,044', answer)
        self.assertEqual(agent.last_artifacts[0]['data'], [
            {'연도': 2019, '생산량_톤': 18044}, {'연도': 2020, '생산량_톤': 18614}])
        self.assertIn('sha256', agent.results[-1]['sources'][0])
        agent.ask('안녕')
        self.assertEqual(agent.last_artifacts, [])

    def test_missing_or_unsupported_chart_data_is_not_invented(self):
        for question in ('2030년 천혜향 생산량 그래프', '천혜향 면적 그래프', '생산량 그래프'):
            agent = Agent()
            agent.ask(question)
            self.assertFalse(agent.last_trace[0]['success'])
            self.assertEqual(agent.results, [])
            self.assertEqual(agent.last_artifacts, [])

    def test_weather_join_requires_complete_days(self):
        original = lt.read_source
        def incomplete(relative):
            frame, source = original(relative)
            if relative.endswith('weather_daily.csv'):
                frame = frame[~((frame['지점명'] == '제주') & (frame['일자'] == '2019-01-01'))]
            return frame, source
        with patch.object(lt, 'read_source', side_effect=incomplete):
            agent = Agent()
            answer = agent.ask('2019년 천혜향 생산량과 기온을 한 표로 보여줘')
        self.assertIn('완전하지 않아', answer)
        self.assertEqual(agent.results, [])

    def test_known_correlation_and_small_sample_guard(self):
        frame = pd.DataFrame({'연도': [2018, 2019, 2020], '생산량_톤': [100, 200, 300],
                              '연평균기온_도': [10, 20, 30], '연강수량_mm': [30, 20, 10]})
        with patch.object(lt, 'merged_frame', return_value=(frame, '천혜향', [])):
            self.assertIn('상관계수: 1.000', lt.relationship_result('기온과 천혜향 생산량은 관계가 있어?')['text'])
            self.assertIn('상관계수: -1.000', lt.relationship_result('강수량과 천혜향 생산량은 관계가 있어?')['text'])
        with patch.object(lt, 'merged_frame', return_value=(frame.head(2), '천혜향', [])):
            with self.assertRaises(lt.ToolUnavailable):
                lt.relationship_result('기온과 천혜향 생산량은 관계가 있어?')

    def test_quality_counts_real_missing_and_duplicate_rows(self):
        frame = pd.DataFrame({'수량': [1.0, 1.0, None]})
        with patch.object(lt, 'read_source', return_value=(frame, {'path': 'fixture.csv'})):
            answer = lt.quality_result('생산량 자료에 빠진 값이 있어?')['text']
        self.assertIn('중복: 1행', answer)
        self.assertIn('빠진 값: 1칸', answer)
        self.assertIn('전체: 3행', answer)

    def test_sensitivity_arithmetic_and_no_compounding(self):
        agent = Agent()
        answer = agent.ask(lt.TOOL_GUIDE[8][2][0])
        self.assertIn('600,000', answer)
        self.assertIn('200,000', answer)
        self.assertIn('-200,000', answer)
        self.assertEqual(agent.scenario['changes'], {})
        for question in (
            '판매량 1000kg 단가 4000원 총비용 300만원 가격이 -10%, 20% 내려가면?',
            '판매량 1000kg 단가 4000원 총비용 300만원 가격이 110%, 120% 내려가면?',
            '판매량 10%, 20% 늘면?'):
            other = Agent()
            other.ask(question)
            self.assertFalse(other.last_trace[0]['success'])
            self.assertEqual(other.results, [])

    def test_document_search_never_reads_env_or_arbitrary_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            (root / 'README.md').write_text('공개 면적 설명', encoding='utf-8')
            (root / '.env').write_text('면적 PRIVATE_SENTINEL', encoding='utf-8')
            with patch.object(lt, 'ROOT', root):
                response = lt.document_result('문서에서 면적을 찾아줘')
                self.assertNotIn('PRIVATE_SENTINEL', response['text'])
                self.assertTrue(all(s['path'] == 'README.md' for s in response['sources']))
                with self.assertRaises(lt.ToolUnavailable):
                    lt.read_source('../outside.csv')

    def test_web_filters_domains_and_reports_network_failure(self):
        with patch.object(lt.requests, 'get') as get:
            get.return_value.content = RSS
            answer = lt.web_result('인터넷에서 감귤 통계 찾아줘')
            self.assertEqual(len(answer['sources']), 1)
            self.assertEqual(answer['sources'][0]['url'], 'https://kosis.kr/example')
            self.assertNotIn('evil.example', answer['text'])
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
        with patch.object(lt.requests, 'get', side_effect=requests.Timeout()):
            agent = Agent()
            answer = agent.ask('인터넷에서 감귤 통계 찾아줘')
        self.assertIn('연결하지 못했습니다', answer)
        self.assertIn('직접 열 수', answer)
        self.assertFalse(agent.last_trace[0]['success'])
        self.assertEqual(agent.results, [])

    def test_investigation_is_bounded_and_does_not_claim_causality(self):
        agent = Agent()
        answer = agent.ask('한라봉 생산량을 차례대로 살펴봐줘')
        self.assertIn('2017', answer)
        self.assertIn('원인은 확정하지 않았습니다', answer)
        self.assertEqual(len(agent.last_trace[0]['steps']), 4)
        self.assertEqual(len(agent.results[-1]['sources']), 2)

    def test_local_diagnosis_does_not_call_api(self):
        from citrus_freellm.__main__ import main
        with patch('sys.argv', ['citrus_freellm', '--diagnose']), \
             patch('requests.post', side_effect=AssertionError('external POST')), \
             patch('sys.stdout', new=io.StringIO()) as output:
            main()
            self.assertIn('API 키 없이', output.getvalue())


if __name__ == '__main__':
    unittest.main()
