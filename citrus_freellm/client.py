"""Chat transports: Claude (Anthropic SDK), FreeLLMAPI and direct OpenAI access.

Callers speak one OpenAI-style message format; ClaudeClient converts it.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import requests


class LazyFreeLLMClient:
    """Local metadata/calculations should not depend on provider credentials."""
    def __init__(self):
        self._client = None

    @property
    def routed_via(self):
        return self._client.routed_via if self._client else None

    def complete(self, messages, tools=None):
        if self._client is None:
            try:
                self._client = make_client()
            except (ValueError, OSError) as exc:
                raise RuntimeError(str(exc)) from None
        return self._client.complete(messages, tools)


CONFIG_NAMES = {'FREELLMAPI_API_KEY', 'FREELLMAPI_BASE_URL', 'FREELLMAPI_MODEL',
                'ANTHROPIC_API_KEY', 'CLAUDE_MODEL', 'CLAUDE_EFFORT'}


def read_config():
    config_file = Path(__file__).with_name('.env')
    config = {}
    if config_file.is_file():
        for line in config_file.read_text(encoding='utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            if separator and name.strip() in CONFIG_NAMES:
                config[name.strip()] = value.strip()
    return config


def setting(name, default=''):
    return os.getenv(name) or read_config().get(name, default)


def claude_configured():
    """Whether the web/terminal may ask Claude to read unclear questions."""
    if os.getenv('CITRUS_LOCAL_ONLY') == '1':
        return False
    return bool(setting('ANTHROPIC_API_KEY').strip())


def make_client():
    """Claude when an Anthropic key is configured, otherwise the FreeLLMAPI/OpenAI path."""
    if setting('ANTHROPIC_API_KEY').strip():
        return ClaudeClient()
    return FreeLLMClient()


class ClaudeClient:
    """Claude via the official Anthropic SDK, answering in the OpenAI-style shape callers expect."""
    REFUSAL = "모델이 이 질문에 답하지 않았습니다. 질문을 바꿔 다시 시도하세요."

    def __init__(self):
        try:
            import anthropic
        except ImportError:
            raise ValueError("Claude 연결에는 anthropic 패키지가 필요합니다: pip install anthropic") from None
        key = setting('ANTHROPIC_API_KEY').strip()
        if not key or not key.isascii() or any(c.isspace() for c in key):
            raise ValueError("ANTHROPIC_API_KEY에 Claude API 키를 설정하세요.")
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=key, timeout=120, max_retries=2)
        self.model = setting('CLAUDE_MODEL', 'claude-haiku-5-5')
        # Intent parsing and tool selection are short structured tasks.
        self.effort = setting('CLAUDE_EFFORT', 'low')
        self.routed_via = None

    @staticmethod
    def convert(messages):
        system, converted = [], []
        for message in messages:
            role = message.get('role')
            if role == 'system':
                system.append(message.get('content') or '')
            elif role == 'tool':
                block = {'type': 'tool_result', 'tool_use_id': message['tool_call_id'],
                         'content': message.get('content') or ''}
                if converted and converted[-1]['role'] == 'user' and isinstance(converted[-1]['content'], list):
                    converted[-1]['content'].append(block)
                else:
                    converted.append({'role': 'user', 'content': [block]})
            elif role == 'assistant' and message.get('_claude_content') is not None:
                # Replay Claude's own blocks unchanged (thinking blocks must survive a tool loop).
                converted.append({'role': 'assistant', 'content': message['_claude_content']})
            elif role == 'assistant':
                blocks = [{'type': 'text', 'text': message['content']}] if message.get('content') else []
                for call in message.get('tool_calls') or []:
                    blocks.append({'type': 'tool_use', 'id': call['id'], 'name': call['function']['name'],
                                   'input': json.loads(call['function'].get('arguments') or '{}')})
                converted.append({'role': 'assistant', 'content': blocks or message.get('content') or ''})
            else:
                converted.append({'role': 'user', 'content': message.get('content') or ''})
        return '\n\n'.join(system), converted

    def complete(self, messages, tools=None):
        anthropic = self.anthropic
        system, converted = self.convert(messages)
        request = {'model': self.model, 'max_tokens': 16000, 'messages': converted,
                   'output_config': {'effort': self.effort}}
        if system:
            request['system'] = system
        if tools:
            request['tools'] = [{'name': t['function']['name'], 'description': t['function'].get('description', ''),
                                 'input_schema': t['function']['parameters']} for t in tools]
            request['tool_choice'] = {'type': 'auto'}
        try:
            response = self.client.messages.create(**request)
        except anthropic.AuthenticationError:
            raise RuntimeError("Claude API 키 인증에 실패했습니다. .env의 ANTHROPIC_API_KEY를 확인하세요.") from None
        except anthropic.PermissionDeniedError:
            raise RuntimeError("이 키로는 요청한 Claude 모델을 쓸 수 없습니다. 키 권한과 CLAUDE_MODEL을 확인하세요.") from None
        except anthropic.NotFoundError:
            raise RuntimeError("Claude 모델 이름을 찾지 못했습니다. CLAUDE_MODEL을 확인하세요.") from None
        except anthropic.RateLimitError:
            raise RuntimeError("Claude API 사용 한도에 도달했습니다. 잠시 뒤 다시 질문하세요.") from None
        except anthropic.BadRequestError:
            raise RuntimeError("Claude가 요청 형식을 거절했습니다. 크레딧 잔액과 설정을 확인하세요.") from None
        except anthropic.APITimeoutError:
            raise RuntimeError("모델 응답 시간이 초과됐습니다. 잠시 뒤 다시 질문하세요. 대화 조건은 유지됩니다.") from None
        except anthropic.APIStatusError:
            raise RuntimeError("Claude 서버에서 오류가 발생했습니다. 잠시 뒤 다시 질문하세요.") from None
        except anthropic.APIConnectionError:
            raise RuntimeError("Claude API에 연결할 수 없습니다. 인터넷 연결을 확인하세요.") from None
        self.routed_via = response.model
        if response.stop_reason == 'refusal':
            raise RuntimeError(self.REFUSAL)
        text = ''.join(b.text for b in response.content if b.type == 'text').strip()
        calls = [{'id': b.id, 'type': 'function',
                  'function': {'name': b.name, 'arguments': json.dumps(b.input, ensure_ascii=False)}}
                 for b in response.content if b.type == 'tool_use']
        if not text and not calls:
            raise RuntimeError("Claude 답변이 비어 있습니다. 다시 질문하세요.")
        reply = {'role': 'assistant', 'content': text or None,
                 '_claude_content': [b.to_dict() for b in response.content]}
        if calls:
            reply['tool_calls'] = calls
        return reply


class FreeLLMClient:
    def __init__(self):
        config = read_config()
        self.key = os.getenv("FREELLMAPI_API_KEY", config.get("FREELLMAPI_API_KEY", "")).strip()
        self.base = os.getenv("FREELLMAPI_BASE_URL", config.get("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")).rstrip("/")
        self.model = os.getenv("FREELLMAPI_MODEL", config.get("FREELLMAPI_MODEL", "auto"))
        parsed = urlparse(self.base)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("FREELLMAPI_BASE_URL에 올바른 서버 주소를 입력하세요.")
        if not self.key or not self.key.isascii() or any(c.isspace() for c in self.key):
            raise ValueError("FREELLMAPI_API_KEY에 연결할 서비스의 API 키를 설정하세요.")
        self.direct_openai = parsed.hostname == "api.openai.com"
        if self.direct_openai and parsed.scheme != "https":
            raise ValueError("OpenAI 연결 주소는 https://api.openai.com/v1을 사용하세요.")
        if self.direct_openai and self.model == "auto":
            raise ValueError("OpenAI 직접 연결에는 FREELLMAPI_MODEL에 사용할 모델 이름을 설정하세요.")
        self.routed_via = None

    def complete(self, messages, tools=None):
        payload = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        try:
            response = requests.post(
                self.base + "/chat/completions", json=payload,
                headers={"Authorization": "Bearer " + self.key},
                timeout=(10, 120), allow_redirects=False,
            )
        except requests.Timeout:
            raise RuntimeError("모델 응답 시간이 초과됐습니다. 잠시 뒤 다시 질문하세요. 대화 조건은 유지됩니다.") from None
        except requests.RequestException:
            raise RuntimeError("서버에 연결할 수 없습니다. citrus_freellm 폴더의 start-agent.cmd로 실행하거나 서버 주소를 확인하세요.") from None
        if response.status_code != 200:
            # Do not echo server bodies or credentials into terminal/logs.
            messages = {
                401: "통합 API 키 인증에 실패했습니다. 대시보드 키와 에이전트 설정을 확인하세요.",
                403: "키 또는 모델 사용 권한을 확인하세요.",
                404: "요청한 모델 또는 서버 경로를 찾지 못했습니다. 모델 설정과 서버 주소를 확인하세요.",
                429: "공급자 사용 한도에 도달했습니다. 잠시 뒤 다시 질문하거나 대시보드에서 다른 모델을 선택하세요.",
                503: "현재 사용할 공급자 모델이 없습니다. 대시보드에서 공급자 키·모델 상태를 확인하세요."
            }
            if self.direct_openai:
                messages.update({
                    401: "OpenAI API 키 인증에 실패했습니다. .env의 키를 확인하세요.",
                    429: "OpenAI API 사용 한도에 도달했습니다. API 결제·크레딧과 요청 한도를 확인하세요.",
                    503: "OpenAI 모델을 현재 사용할 수 없습니다. 잠시 뒤 다시 시도하세요.",
                })
            raise RuntimeError(f"HTTP {response.status_code}: " + messages.get(response.status_code, "모델 서버에서 오류가 발생했습니다. 잠시 뒤 다시 질문하세요."))
        self.routed_via = response.headers.get("X-Routed-Via")
        try:
            body = response.json()
            message = body["choices"][0]["message"]
            if self.direct_openai:
                self.routed_via = body.get("model") or self.model
            if message.get("role") != "assistant":
                raise ValueError
            if not message.get("content") and not message.get("tool_calls"):
                raise ValueError
            return {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise RuntimeError("FreeLLMAPI 응답 형식이 올바르지 않거나 답변이 비어 있습니다.") from None
