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

    def test_chat_rerun_does_not_repeat_question(self):
        app = self.app()
        self.assertFalse(app.exception)
        app.chat_input[0].set_value("날씨는 영향이 있나?").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 2)
        self.assertIn("상관이 인과", app.chat_message[1].markdown[0].value)
        app.run()
        self.assertEqual(len(app.session_state.agent.results), 1)

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
                self.assertEqual(len(app.session_state.exports), 3)
                body = next(data for name, data in app.session_state.exports if name.endswith('.json'))
                self.assertIn(b'sha256', body)

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
        self.assertIn("서버 연결", text)
        self.assertNotIn("private-test-secret", text)
