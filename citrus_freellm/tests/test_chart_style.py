import unittest

from citrus_freellm.agent import Agent
from citrus_freellm.chart_style import is_restyle, requested_style


class ChartStyleTest(unittest.TestCase):
    def test_phrases(self):
        self.assertTrue(is_restyle('막대그래프로 바꿔줘'))
        self.assertTrue(is_restyle('영역 그래프로 보여줘'))
        self.assertTrue(is_restyle('점 그래프로 다시 그려줘'))
        self.assertFalse(is_restyle('천혜향 생산량 막대그래프로 보여줘'), 'a new subject draws a new chart')
        self.assertFalse(is_restyle('그래프로 그려줘'))
        self.assertEqual(requested_style('꺾은선으로 바꿔'), 'line')

    def test_restyle_keeps_numbers_and_new_chart_takes_style(self):
        agent = Agent(local_only=True)
        agent.ask('천혜향 생산량을 그래프로 보여줘')
        before = agent.last_artifacts[0]['data']
        answer = agent.ask('막대그래프로 바꿔줘')
        self.assertIn('막대그래프', answer)
        self.assertEqual(agent.last_artifacts[0]['chart_kind'], 'bar')
        self.assertEqual(agent.last_artifacts[0]['data'], before)
        self.assertEqual(agent.results[-1]['question'], '천혜향 생산량을 그래프로 보여줘', 'restyling is not a new result')
        agent.ask('영역 그래프로 바꿔줘')
        self.assertEqual(agent.last_artifacts[0]['chart_kind'], 'area')
        agent.ask('한라봉 생산량 막대그래프로 보여줘')
        self.assertEqual(agent.last_artifacts[0]['chart_kind'], 'bar')
        self.assertIn('한라봉', agent.last_artifacts[0]['title'])

    def test_without_a_chart_nothing_is_restyled(self):
        agent = Agent(local_only=True)
        answer = agent.ask('막대그래프로 바꿔줘')
        self.assertEqual(agent.last_artifacts, [])
        self.assertNotIn('바꿨어요', answer)


if __name__ == '__main__':
    unittest.main()
