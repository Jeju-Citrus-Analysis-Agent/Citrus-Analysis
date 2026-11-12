import io
import unittest
from unittest.mock import Mock, patch

import requests

from citrus_freellm.client import FreeLLMClient
from citrus_freellm.__main__ import main


class ConnectionTests(unittest.TestCase):
    @patch.dict("os.environ", {"FREELLMAPI_API_KEY": "test-private-key", "FREELLMAPI_BASE_URL": "http://127.0.0.1:3001/v1"})
    @patch("citrus_freellm.client.requests.post")
    def test_error_messages_and_no_secret_leak(self, post):
        client = FreeLLMClient()
        for code, text in ((401, "통합 API 키"), (429, "사용 한도"), (503, "공급자"), (404, "모델")):
            post.return_value.status_code = code
            post.return_value.text = "test-private-key"
            with self.assertRaises(RuntimeError) as caught:
                client.complete([])
            self.assertIn(text, str(caught.exception))
            self.assertNotIn("test-private-key", str(caught.exception))
        for exception, expected in ((requests.Timeout(), "응답 시간"), (requests.ConnectionError(), "start-agent.cmd")):
            post.side_effect = exception
            with self.assertRaises(RuntimeError) as caught:
                client.complete([])
            self.assertIn(expected, str(caught.exception))

    @patch("sys.argv", ["citrus_freellm"])
    @patch("citrus_freellm.__main__.FreeLLMClient")
    @patch("citrus_freellm.__main__.Agent")
    @patch("builtins.input", side_effect=["질문1", "질문2", "/exit"])
    def test_interactive_connection_error_does_not_exit(self, user_input, agent_class, client_class):
        agent_class.return_value.ask.side_effect = [RuntimeError("사용 한도 오류"), "다음 질문 성공"]
        with patch("sys.stdout", new=io.StringIO()) as output:
            main()
            self.assertIn("사용 한도", output.getvalue())
            self.assertIn("다음 질문 성공", output.getvalue())
        self.assertEqual(agent_class.return_value.ask.call_count, 2)
