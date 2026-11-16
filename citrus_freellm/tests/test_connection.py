import io
import unittest
from unittest.mock import Mock, patch

import requests

from citrus_freellm.client import FreeLLMClient
from citrus_freellm.__main__ import main


class ConnectionTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch("citrus_freellm.client.Path.is_file", return_value=True)
    @patch("citrus_freellm.client.Path.read_text")
    @patch("citrus_freellm.client.requests.post")
    def test_direct_openai_transport_and_error_redaction(self, post, read_text, is_file):
        read_text.return_value = ('FREELLMAPI_BASE_URL=https://api.openai.com/v1\n'
                                  'FREELLMAPI_API_KEY=test-private-key\n'
                                  'FREELLMAPI_MODEL=gpt-4.1-mini\n')
        client = FreeLLMClient()
        post.return_value.status_code = 200
        post.return_value.headers = {}
        post.return_value.json.return_value = {
            'model': 'gpt-4.1-mini-test',
            'choices': [{'message': {'role': 'assistant', 'content': 'OK'}}]}
        self.assertEqual(client.complete([{'role': 'user', 'content': 'test'}])['content'], 'OK')
        self.assertEqual(post.call_args.args[0], 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(post.call_args.kwargs['json']['model'], 'gpt-4.1-mini')
        self.assertEqual(client.routed_via, 'gpt-4.1-mini-test')
        for code in (401, 429):
            post.return_value.status_code = code
            post.return_value.text = 'test-private-key'
            with self.assertRaises(RuntimeError) as caught:
                client.complete([])
            self.assertIn('OpenAI', str(caught.exception))
            self.assertNotIn('test-private-key', str(caught.exception))

    @patch.dict("os.environ", {}, clear=True)
    @patch("citrus_freellm.client.Path.is_file", return_value=True)
    @patch("citrus_freellm.client.Path.read_text")
    def test_updated_env_file_is_loaded_by_new_client(self, read_text, is_file):
        read_text.return_value = 'FREELLMAPI_API_KEY=first-test-key\n'
        self.assertEqual(FreeLLMClient().key, 'first-test-key')
        read_text.return_value = 'FREELLMAPI_API_KEY=second-test-key\n'
        self.assertEqual(FreeLLMClient().key, 'second-test-key')

    @patch.dict("os.environ", {}, clear=True)
    @patch("citrus_freellm.client.Path.is_file", return_value=True)
    @patch("citrus_freellm.client.Path.read_text")
    def test_direct_openai_requires_https_and_explicit_model(self, read_text, is_file):
        for base, expected in (('http://api.openai.com/v1', 'https'),
                               ('https://api.openai.com/v1', 'FREELLMAPI_MODEL')):
            read_text.return_value = f'FREELLMAPI_API_KEY=test-key\nFREELLMAPI_BASE_URL={base}\n'
            with self.assertRaises(ValueError) as caught:
                FreeLLMClient()
            self.assertIn(expected, str(caught.exception))

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
    @patch("citrus_freellm.__main__.Agent")
    @patch("builtins.input", side_effect=["질문1", "질문2", "/exit"])
    def test_interactive_connection_error_does_not_exit(self, user_input, agent_class):
        agent_class.return_value.ask.side_effect = [RuntimeError("사용 한도 오류"), "다음 질문 성공"]
        with patch("sys.stdout", new=io.StringIO()) as output:
            main()
            self.assertIn("사용 한도", output.getvalue())
            self.assertIn("다음 질문 성공", output.getvalue())
        self.assertEqual(agent_class.return_value.ask.call_count, 2)
