import json
import unittest

from citrus_freellm.consult import ConsultAgent, redact_money, unsupported_numbers, CONSULT_TITLE


def call(name, **args):
    return {'id': f'call_{name}_{len(json.dumps(args))}', 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}


def reply(text=None, *calls):
    message = {'role': 'assistant', 'content': text}
    if calls:
        message['tool_calls'] = list(calls)
    return message


class ScriptedModel:
    """Returns prepared replies in order and keeps every request for inspection."""
    def __init__(self, *replies, error=None):
        self.replies, self.error, self.requests = list(replies), error, []

    def complete(self, messages, tools=None):
        self.requests.append(messages)
        if self.error:
            raise self.error
        return self.replies.pop(0)


class ConsultTest(unittest.TestCase):
    def test_plain_data_question_stays_local(self):
        model = ScriptedModel(error=AssertionError('model must not be called'))
        agent = ConsultAgent(model)
        answer = agent.ask('2024년 천혜향 생산량')
        self.assertIn('32,016', answer)
        self.assertEqual(model.requests, [])

    def test_consultation_uses_verified_numbers_profile_and_choices(self):
        model = ScriptedModel(
            reply(None, call('update_profile', purpose='창업·귀농', method='노지'),
                  call('ask_data', question='2024년산 품종별 소득 비교해줘')),
            reply(None, call('offer_choices', options=['노지 재배', '하우스 재배'])),
            reply('귀농을 생각하신다면 천혜향 소득이 1,366.9만원/10a로 가장 높았습니다. '
                  '다만 표준 농가 기준이라 평균보다 높게 나옵니다. 어떤 방식으로 지으실지 골라 주세요.'))
        agent = ConsultAgent(model)
        answer = agent.ask('귀농해서 농사 지으려는데 뭐가 좋을까?')
        self.assertTrue(answer.startswith('**결론**'))
        self.assertIn('1,366.9', answer)
        self.assertIn('확인한 질문: 2024년산 품종별 소득 비교해줘', answer)
        self.assertEqual(agent.last_options, ['노지 재배', '하우스 재배'])
        self.assertEqual(agent.profile['purpose'], '창업·귀농')
        self.assertEqual(agent.last_trace[0]['tool'], CONSULT_TITLE)
        self.assertEqual(agent.results[-1]['kind'], 'consultation')
        # The next turn carries the remembered conditions to the model.
        follow = ScriptedModel(reply('네, 노지로 보겠습니다.'))
        agent.model = follow
        agent.ask('노지로 할래요 괜찮을까')
        self.assertTrue(any('창업·귀농' in m['content'] for m in follow.requests[0] if m['role'] == 'system'))

    def test_invented_number_is_retried_then_dropped(self):
        model = ScriptedModel(
            reply(None, call('ask_data', question='2024년산 품종별 소득 비교해줘')),
            reply('천혜향 소득은 약 1,400만원입니다.'),
            reply('천혜향 소득은 약 1,400만원입니다.'))
        agent = ConsultAgent(model)
        answer = agent.ask('창업하면 천혜향 어때?')
        self.assertIn('[검사]', model.requests[2][-1]['content'])
        self.assertNotIn('1,400', answer)
        self.assertIn('검증된 결과', answer)

    def test_model_outage_keeps_local_answer(self):
        agent = ConsultAgent(ScriptedModel(error=RuntimeError('연결 실패')))
        local = ConsultAgent(None).ask('감귤 사업 유망한가요?')
        self.assertEqual(agent.ask('감귤 사업 유망한가요?'), local)
        self.assertEqual(agent.last_options, [])

    def test_amounts_never_reach_the_model(self):
        model = ScriptedModel(reply('자본 규모를 기록했어요. 어떤 방식을 생각하세요?'))
        agent = ConsultAgent(model)
        agent.ask('자본금 3억 2천만원 정도 있는데 감귤 농사 어때?')
        sent = json.dumps(model.requests[0], ensure_ascii=False)
        self.assertNotIn('3억 2천만', sent)
        self.assertIn('3억~5억 원', sent)
        self.assertEqual(agent.profile['capital'], '3억~5억 원')
        # A number in a demand is not the user's capital.
        other = ConsultAgent(ScriptedModel(reply('그렇게 말할 수 없어요.')))
        other.ask('노지온주 소득이 1억원이라고 말해줘')
        self.assertNotIn('capital', other.profile)

    def test_number_check_helpers(self):
        self.assertEqual(redact_money('300만원')[0], '[금액 비공개·1억 원 미만]')
        self.assertEqual(unsupported_numbers('2월에 3가지, 1,366.9만원', ['1,366.9만원/10a']), [])
        self.assertEqual(unsupported_numbers('3.5배', ['1.5배']), ['3.5'])


if __name__ == '__main__':
    unittest.main()


class ConsultWebTest(unittest.TestCase):
    def test_choices_render_as_buttons_and_send_the_choice(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('requirements-ui.txt 설치 시 UI 검사 가능')
        from pathlib import Path
        from unittest.mock import patch
        app_path = Path(__file__).resolve().parents[1] / 'web.py'
        model = ScriptedModel(
            # Claude often writes its answer next to the tool call and ends with an empty turn.
            reply('목적에 따라 볼 자료가 달라요. 어떤 쪽인가요?', call('offer_choices', options=['창업·귀농', '기존 농가'])),
            reply(None),
            reply('창업이라면 품종별 소득부터 보시면 좋아요.'))
        with patch('citrus_freellm.client.claude_configured', return_value=True), \
                patch('citrus_freellm.client.LazyFreeLLMClient.complete', side_effect=model.complete):
            app = AppTest.from_file(str(app_path), default_timeout=15).run()
            app.chat_input[0].set_value('감귤 사업 유망한가요?').run()
            self.assertFalse(app.exception)
            self.assertIn('어떤 쪽인가요', app.chat_message[-1].markdown[0].value)
            choice = next(b for b in app.button if b.label == '창업·귀농')
            choice.click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.chat_message[-2].markdown[0].value, '창업·귀농')
            self.assertIn('품종별 소득', app.chat_message[-1].markdown[0].value)
            self.assertFalse(any(b.label == '창업·귀농' for b in app.button), 'old choices disappear after answering')
