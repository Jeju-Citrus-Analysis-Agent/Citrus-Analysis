import json
import unittest
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.client import FreeLLMClient
from citrus_freellm.tools import execute, production


CALL = {"role": "assistant", "content": None, "tool_calls": [
    {"id": "call1", "type": "function", "function": {
        "name": "production", "arguments": json.dumps({
            "variety": "천혜향", "start_year": 2019, "end_year": 2020})}}]}


class AgentTests(unittest.TestCase):
    def test_real_production(self):
        result = production("천혜향", 2019, 2020)
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["missing_years"], [])
        self.assertIn("생산량_톤", result["change"])

    def test_invalid_inputs(self):
        for call in [{"name": "unknown", "arguments": "{}"},
                     {"name": "catalog", "arguments": "[]"},
                     {"name": "production", "arguments": "invalid"}]:
            self.assertIn("error", execute(call))
        self.assertIn("error", execute({"name": "read_dataset", "arguments": '{"dataset":"../../private","filters":{}}'}))

    def test_tool_roundtrip_and_memory(self):
        client = Mock()
        client.complete.side_effect = [CALL, {"role": "assistant", "content": "조회했습니다."}]
        agent = Agent(client)
        result = agent.ask("2019년과 2020년 천혜향 생산량 비교")
        self.assertIn("data/raw/public/fruit_production.csv", result)
        self.assertIn("18,044", result)
        self.assertIn("+3.16%", result)
        self.assertEqual(client.complete.call_count, 1)
        self.assertEqual(len(agent.history), 2)

    def test_loop_limit(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "tool_calls": [
            {"id": "catalog1", "type": "function", "function": {"name": "catalog", "arguments": "{}"}}]}
        agent = Agent(client, max_steps=2)
        self.assertIn("한도", agent.ask("2019년 천혜향 생산량"))
        self.assertEqual(client.complete.call_count, 2)

    @patch.dict("os.environ", {"FREELLMAPI_API_KEY": "test-secret", "FREELLMAPI_BASE_URL": "http://localhost:3001/v1"})
    @patch("citrus_freellm.client.requests.post")
    def test_transport_and_redaction(self, post):
        response = post.return_value
        response.status_code = 200
        response.headers = {"X-Routed-Via": "provider/model"}
        response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
        client = FreeLLMClient()
        self.assertEqual(client.complete([{"role": "user", "content": "hi"}])["content"], "OK")
        self.assertEqual(post.call_args.args[0], "http://localhost:3001/v1/chat/completions")
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertEqual(client.routed_via, "provider/model")
        response.status_code = 401
        response.text = "test-secret"
        with self.assertRaises(RuntimeError) as caught:
            client.complete([])
        self.assertNotIn("test-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
