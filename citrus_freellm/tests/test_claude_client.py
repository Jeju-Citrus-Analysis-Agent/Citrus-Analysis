import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from citrus_freellm import client as client_module
from citrus_freellm.client import ClaudeClient, make_client


def block(**fields):
    data = dict(fields)
    return SimpleNamespace(**fields, to_dict=lambda: data)


def response(*content, stop_reason='end_turn'):
    return SimpleNamespace(model='claude-haiku-5-5', stop_reason=stop_reason, content=list(content))


TOOL = {'type': 'function', 'function': {'name': 'production', 'description': '생산량 조회',
        'parameters': {'type': 'object', 'properties': {'variety': {'type': 'string'}}}}}


class ClaudeClientTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'sk-ant-test', 'CLAUDE_MODEL': 'claude-haiku-5-5'})
        env.start()
        self.addCleanup(env.stop)

    def test_factory_prefers_claude_when_key_is_set(self):
        self.assertIsInstance(make_client(), ClaudeClient)
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}), \
                patch.object(client_module, 'read_config', return_value={}), \
                patch.object(client_module, 'FreeLLMClient', return_value='free') as free:
            self.assertEqual(make_client(), 'free')
            free.assert_called_once()

    def test_tool_call_comes_back_in_openai_shape_and_replays(self):
        claude = ClaudeClient()
        thinking = block(type='thinking', thinking='', signature='sig')
        use = block(type='tool_use', id='toolu_1', name='production', input={'variety': '한라봉'})
        with patch.object(claude.client.messages, 'create', return_value=response(thinking, use)) as create:
            reply = claude.complete([{'role': 'system', 'content': '규칙'}, {'role': 'user', 'content': '질문'}], [TOOL])
        sent = create.call_args.kwargs
        self.assertEqual(sent['model'], 'claude-haiku-5-5')
        self.assertEqual(sent['system'], '규칙')
        self.assertEqual(sent['tools'][0]['input_schema'], TOOL['function']['parameters'])
        self.assertEqual(sent['tool_choice'], {'type': 'auto'})
        call = reply['tool_calls'][0]
        self.assertEqual((call['id'], call['type'], call['function']['name']), ('toolu_1', 'function', 'production'))
        self.assertEqual(json.loads(call['function']['arguments']), {'variety': '한라봉'})

        # The next turn replays Claude's own blocks (thinking included) and groups tool results.
        system, messages = ClaudeClient.convert([
            {'role': 'user', 'content': '질문'}, reply,
            {'role': 'tool', 'tool_call_id': 'toolu_1', 'content': '{}'}])
        self.assertEqual(messages[1]['content'][0]['type'], 'thinking')
        self.assertEqual(messages[2], {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'toolu_1', 'content': '{}'}]})

    def test_text_answer_and_refusal(self):
        claude = ClaudeClient()
        with patch.object(claude.client.messages, 'create', return_value=response(block(type='text', text='{"a": 1}'))):
            self.assertEqual(claude.complete([{'role': 'user', 'content': 'q'}])['content'], '{"a": 1}')
        with patch.object(claude.client.messages, 'create', return_value=response(stop_reason='refusal')):
            with self.assertRaisesRegex(RuntimeError, '답하지 않았습니다'):
                claude.complete([{'role': 'user', 'content': 'q'}])


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


def intent_reply(**fields):
    value = {'action': 'lookup', 'year_operation': 'explicit', 'metric_operation': 'inherit',
             'year_quote': '', 'metric_quote': '', **fields}
    return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 't1', 'type': 'function',
            'function': {'name': 'interpret_intent', 'arguments': json.dumps(value, ensure_ascii=False)}}]}


class ModelAssistTest(unittest.TestCase):
    def test_model_only_fills_slots_numbers_come_from_local_data(self):
        from citrus_freellm.agent import Agent
        from citrus_freellm.guardrails import CLARIFY
        fake = FakeClient(intent_reply())
        agent = Agent(fake, local_only=True)
        agent.ask('2020년 천혜향 생산량')
        answer = agent.model_assist('2019년 걸로 다시', CLARIFY)
        self.assertEqual(fake.calls, 1)
        self.assertIn('18,044', answer)

    def test_model_failure_or_off_topic_keeps_local_answer(self):
        from citrus_freellm.agent import Agent
        local = Agent(local_only=True).ask('이거 어때?')
        broken = FakeClient(error=RuntimeError('연결 실패'))
        self.assertEqual(Agent(broken, local_only=True).ask('이거 어때?'), local)
        silent = FakeClient(error=AssertionError('must not call'))
        Agent(silent, local_only=True).ask('오늘 서울 날씨 알려줘')
        self.assertEqual(silent.calls, 0)


if __name__ == '__main__':
    unittest.main()
