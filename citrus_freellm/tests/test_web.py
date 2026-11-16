"""화면 재실행 시 대화 중복, 세션 혼합, 리포트 누락을 검증한다."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

APP = Path(__file__).resolve().parents[1] / "web.py"


@unittest.skipIf(AppTest is None, "requirements-ui.txt 설치 시 UI 검사 가능")
class WebTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(APP), default_timeout=15).run()

    def test_scroll_iframe_height_is_positive_after_questions_and_edit(self):
        import streamlit as st
        app = self.app()
        with patch('streamlit.iframe', wraps=st.iframe) as iframe:
            app.chat_input[0].set_value('2020년 천혜향 생산량').run()
            app.chat_input[0].set_value('그래프로 그려줘').run()
            next(b for b in app.button if b.key == 'edit_0').click().run()
        self.assertFalse(app.exception)
        self.assertGreaterEqual(iframe.call_count, 3)
        self.assertTrue(all(call.kwargs['height'] > 0 for call in iframe.call_args_list))

    def test_each_submitted_question_scrolls_to_its_own_turn(self):
        import streamlit as st
        app = self.app()
        with patch('streamlit.iframe', wraps=st.iframe) as iframe:
            app.chat_input[0].set_value('2020년 천혜향 생산량').run()
            first = iframe.call_args.args[0]
            app.chat_input[0].set_value('그래프로 그려줘').run()
            second = iframe.call_args.args[0]
        self.assertIn("getElementById('question-0')", first)
        self.assertIn("getElementById('question-2')", second)
        self.assertNotEqual(first, second)
        self.assertFalse(app.exception)
        self.assertFalse(any(b.label in {'생산량 그래프로 보기', '다른 연도와 비교'} for b in app.button))

    def test_chat_rerun_does_not_repeat_question(self):
        app = self.app()
        self.assertFalse(app.exception)
        app.chat_input[0].set_value("날씨는 영향이 있나?").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 2)
        self.assertIn("상관이 인과", app.chat_message[1].markdown[0].value)
        app.run()
        self.assertEqual(len(app.session_state.agent.results), 1)

    def test_each_submission_targets_its_question_including_followups(self):
        from citrus_freellm.navigation import scroll_script
        with patch('citrus_freellm.navigation.scroll_script', wraps=scroll_script) as scroll:
            app = self.app()
            for index, question in enumerate(('2020년 천혜향 생산량', '그래프로 그려줘', '그러면 2019년은?')):
                app.chat_input[0].set_value(question).run()
                self.assertFalse(app.exception)
                scroll.assert_called_with(index * 2, index + 1)
                self.assertEqual(scroll.call_count, index + 1)
            app.run()
            self.assertEqual(scroll.call_count, 3, 'ordinary reruns must not move the reader')

    def test_default_mode_queries_production_without_model(self):
        app = self.app()
        with patch("citrus_freellm.client.LazyFreeLLMClient.complete", side_effect=AssertionError("external call")) as complete:
            app.chat_input[0].set_value("2019년과 2020년 천혜향 생산량 비교").run()
        self.assertFalse(app.exception)
        self.assertIn("18,044", app.chat_message[-1].markdown[0].value)
        self.assertIn("+3.16%", app.chat_message[-1].markdown[0].value)
        complete.assert_not_called()

    def test_scenario_followup_and_reset(self):
        app = self.app()
        app.chat_input[0].set_value("판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 10% 하락 이익은?").run()
        app.chat_input[0].set_value("그럼 단가 20% 하락이면?").run()
        self.assertIn("200,000", app.chat_message[-1].markdown[0].value)
        next(b for b in app.button if b.label == "새 대화").click().run()
        self.assertEqual(app.session_state.agent.results, [])
        self.assertEqual(len(app.chat_message), 0)
        self.assertFalse(app.exception)

    def test_report_downloads_retain_source_and_result(self):
        app = self.app()
        app.chat_input[0].set_value("언제 팔면 비싼가?").run()
        with tempfile.TemporaryDirectory(dir=APP.parent / "tests") as directory:
            with patch("citrus_freellm.reporting.OUTPUT", Path(directory)):
                next(b for b in app.button if b.label == "리포트 만들기").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(sorted(Path(name).suffix for name, _ in app.session_state.exports), ['.md', '.pdf'])
                body = next(data for name, data in app.session_state.exports if name.endswith('.md'))
                self.assertIn('sha256'.encode(), body)
                labels = {b.label for b in app.sidebar.get('download_button')}
                self.assertEqual(labels, {'PDF 리포트', 'Markdown 리포트'})

    def test_sessions_do_not_share_agent(self):
        first, second = self.app(), self.app()
        first.chat_input[0].set_value("날씨는 영향이 있나?").run()
        self.assertEqual(len(second.session_state.agent.results), 0)
        self.assertIsNot(first.session_state.agent, second.session_state.agent)

    def test_connection_error_keeps_conversation_and_hides_details(self):
        app = self.app()
        with patch("citrus_freellm.agent.Agent.ask", side_effect=RuntimeError("private-test-secret")):
            app.chat_input[0].set_value("질문").run()
        self.assertFalse(app.exception)
        text = app.chat_message[-1].markdown[0].value
        self.assertIn("입력한 조건", text)
        self.assertNotIn("private-test-secret", text)

    def test_keyless_tools_gallery_chart_and_report(self):
        app = self.app()
        self.assertEqual(len(app.checkbox), 0)
        self.assertIsNone(app.session_state.agent.client)
        self.assertEqual(len(app.selectbox[0].options), 9)
        app.selectbox[0].select('그래프 그리기').run()
        next(b for b in app.button if b.key == 'example_그래프 그리기_0').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.messages[-1]['artifacts']), 1)
        self.assertTrue(app.session_state.messages[-1]['trace'])
        with tempfile.TemporaryDirectory(dir=APP.parent / 'tests') as directory:
            with patch('citrus_freellm.reporting.OUTPUT', Path(directory)):
                next(b for b in app.button if b.label == '리포트 만들기').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.exports), 2)  # Markdown + PDF

    def test_conclusion_and_details_are_visible_in_order(self):
        app = self.app()
        app.chat_input[0].set_value('2019년과 2020년 천혜향 생산량 비교').run()
        message = app.chat_message[-1]
        self.assertTrue(message.markdown[0].value.startswith('**결론**'))
        self.assertIn('+3.16%', message.markdown[0].value)
        self.assertTrue(message.markdown[1].value.startswith('**세부 설명**'))
        self.assertIn('| 연도 |', message.markdown[1].value)
        self.assertIn('출처:', message.markdown[1].value)
        self.assertFalse(any(e.label.startswith('자세한 내용 보기') for e in message.expander))
        self.assertFalse(message.expander)  # a short lookup stays fully open

    def test_long_explanation_shows_conclusion_and_chart_before_folded_details(self):
        app = self.app()
        app.chat_input[0].set_value('가격이 오른 건 물가 때문이야?').run()
        message = app.chat_message[-1]
        self.assertTrue(message.markdown[0].value.startswith('**결론**'))
        folded, = message.expander
        self.assertTrue(folded.label.startswith('자세히 보기'))
        self.assertTrue(folded.markdown[0].value.startswith('**세부 설명**'))
        self.assertTrue(app.session_state.messages[-1]['artifacts'])  # chart sits above the fold

    def test_followup_questions_work_without_action_buttons(self):
        app = self.app()
        app.chat_input[0].set_value('2019년과 2020년 천혜향 생산량 비교').run()
        self.assertFalse(any(b.label in {'생산량 그래프로 보기', '다른 연도와 비교'} for b in app.button))
        app.chat_input[0].set_value('그래프로 그려줘').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.messages[-1]['artifacts'][0]['data']), 2)
        app.chat_input[0].set_value('2020년과 2018년 천혜향 생산량 비교').run()
        self.assertFalse(app.exception)
        self.assertIn('2020년과 2018년 천혜향', app.session_state.messages[-2]['content'])
        self.assertIn('15,943', app.chat_message[-1].markdown[0].value)
        self.assertEqual(len(app.session_state.agent.results), 3)
        app.run()
        self.assertEqual(len(app.session_state.agent.results), 3)

    def test_typed_followup_charts_previous_table(self):
        app = self.app()
        app.chat_input[0].set_value('2019년과 2020년 천혜향 생산량 비교').run()
        app.chat_input[0].set_value('그래프로 그려줘').run()
        self.assertFalse(app.exception)
        message = app.session_state.messages[-1]
        self.assertIn('앞선 답변의 표', message['content'])
        chart = message['artifacts'][0]
        self.assertEqual(chart['chart_kind'], 'bar')
        self.assertEqual([r['항목'] for r in chart['data']], ['2019', '2020'])
        self.assertEqual([r[chart['y']] for r in chart['data']], [18044.0, 18614.0])
        self.assertEqual(len(app.get('vega_lite_chart')), 1)

    def test_inline_edit_replaces_question_and_cancel_keeps_history(self):
        app = self.app()
        original = '2020년 천혜향 생산량'
        app.chat_input[0].set_value(original).run()
        next(b for b in app.button if b.key == 'edit_0').click().run()
        self.assertEqual(app.text_area[0].value, original)
        self.assertEqual(app.chat_message[0].text_area[0].value, original)
        self.assertFalse(any(b.label == '다시 실행' for b in app.button))
        app.text_area[0].set_value('2020년 한라봉 생산량')
        next(b for b in app.button if b.label == '저장하고 답변 받기').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.messages[0]['content'], '2020년 한라봉 생산량')
        self.assertEqual(app.session_state.messages[-2]['content'], '2020년 한라봉 생산량')
        self.assertIn('41,222', app.chat_message[-1].markdown[0].value)
        next(b for b in app.button if b.key == 'edit_0').click().run()
        next(b for b in app.button if b.label == '취소').click().run()
        self.assertEqual(len(app.session_state.messages), 2)
        self.assertEqual(len(app.text_area), 0)

    def test_edit_uses_original_scenario_and_removes_obsolete_answers(self):
        app = self.app()
        app.chat_input[0].set_value('판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 10% 하락 이익은?').run()
        app.chat_input[0].set_value('그럼 단가 20% 하락이면?').run()
        app.chat_input[0].set_value('판매량 2000kg, 단가 5000원, 총비용 300만원이면 이익은?').run()
        next(b for b in app.button if b.key == 'edit_2').click().run()
        app.text_area[0].set_value('그럼 단가 20% 하락이면?')
        next(b for b in app.button if b.label == '저장하고 답변 받기').click().run()
        self.assertFalse(app.exception)
        self.assertIn('200,000원', app.chat_message[-1].markdown[0].value)
        self.assertEqual(app.session_state.messages[-2]['content'], '그럼 단가 20% 하락이면?')
        self.assertEqual(len(app.session_state.agent.results), 2)
        self.assertEqual(len(app.session_state.messages), 4)

    def test_coverage_and_unit_help_and_single_year_chart(self):
        app = self.app()
        # The home screen no longer shows the coverage line; '어떤 데이터가 있어?' answers it.
        self.assertFalse(any('조회 가능 기간' in c.value for c in app.caption))
        self.assertFalse(any(e.label in {'조회 가능한 자료', '숫자·단위 도움말', '도구별 쉬운 질문'} for e in app.expander))
        self.assertFalse(any('단위 도움말:' in c.value for c in app.caption))
        app.chat_input[0].set_value('2020년 천혜향 생산량').run()
        self.assertTrue(any('1톤 = 1,000kg' in c.value for c in app.chat_message[-1].caption))
        self.assertTrue(any('1만 8,614톤' in c.value for c in app.chat_message[-1].caption))
        app.chat_input[0].set_value('그래프로 그려줘').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.messages[-1]['artifacts'][0]['data']), 1)

    def test_empty_edit_does_not_execute_and_reset_closes_editor(self):
        app = self.app()
        app.chat_input[0].set_value('2020년 천혜향 생산량').run()
        next(b for b in app.button if b.key == 'edit_0').click().run()
        app.text_area[0].set_value('  ')
        next(b for b in app.button if b.label == '저장하고 답변 받기').click().run()
        self.assertTrue(any('질문을 입력해 주세요' in w.value for w in app.warning))
        self.assertEqual(len(app.session_state.messages), 2)
        next(b for b in app.button if b.label == '새 대화').click().run()
        self.assertEqual(len(app.text_area), 0)
        self.assertEqual(len(app.chat_message), 0)
        self.assertEqual(app.session_state.agent.results, [])

    def test_questions_from_older_sessions_can_also_be_edited(self):
        app = self.app()
        app.session_state.messages = [{'role': 'user', 'content': '2020년 천혜향 생산량'},
                                      {'role': 'assistant', 'content': '이전 답변'}]
        app.run()
        button = next(b for b in app.button if b.key == 'edit_0')
        self.assertFalse(button.disabled)
        button.click().run()
        self.assertEqual(app.chat_message[0].text_area[0].value, '2020년 천혜향 생산량')
        app.text_area[0].set_value('2020년 한라봉 생산량')
        next(b for b in app.button if b.label == '저장하고 답변 받기').click().run()
        self.assertFalse(app.exception)
        self.assertIn('41,222', app.chat_message[-1].markdown[0].value)

    def test_complete_selector_is_inside_examples(self):
        app = self.app()
        example = next(e for e in app.sidebar.expander if e.label == '예시 질문')
        selector = example.selectbox[0]
        self.assertEqual(selector.label, '무엇을 하고 싶으세요?')
        self.assertEqual(len(selector.options), 9)
        self.assertNotIn('자료 문제 확인', selector.options)
        self.assertIn('여러 자료 보기', selector.options)
        self.assertIn('가격별 이익 비교', selector.options)
        self.assertIn('차례대로 살펴보기', selector.options)
        selector.select('여러 자료 보기').run()
        next(b for b in app.button if b.label == '2020년 제주 날씨 보여줘').click().run()
        self.assertFalse(app.exception)
        self.assertIn('제주 관측소', app.chat_message[-1].markdown[0].value)
        self.assertTrue(any('섭씨' in c.value for c in app.chat_message[-1].caption))
