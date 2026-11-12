"""FreeLLMAPI chat transport, independent of the legacy agents."""
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
                self._client = FreeLLMClient()
            except (ValueError, OSError) as exc:
                raise RuntimeError(str(exc)) from None
        return self._client.complete(messages, tools)


class FreeLLMClient:
    def __init__(self):
        config_file = Path(__file__).with_name('.env')
        if config_file.is_file():
            for line in config_file.read_text(encoding='utf-8-sig').splitlines():
                name, separator, value = line.partition('=')
                if separator and name.strip() in {'FREELLMAPI_API_KEY', 'FREELLMAPI_BASE_URL', 'FREELLMAPI_MODEL'}:
                    os.environ.setdefault(name.strip(), value.strip())
        self.key = os.getenv("FREELLMAPI_API_KEY", "").strip()
        self.base = os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1").rstrip("/")
        self.model = os.getenv("FREELLMAPI_MODEL", "auto")
        parsed = urlparse(self.base)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("FREELLMAPI_BASE_URL에 올바른 서버 주소를 입력하세요.")
        if not self.key or not self.key.isascii() or any(c.isspace() for c in self.key):
            raise ValueError("FREELLMAPI_API_KEY에 대시보드의 통합 키를 설정하세요.")
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
            raise RuntimeError(f"HTTP {response.status_code}: " + messages.get(response.status_code, "모델 서버에서 오류가 발생했습니다. 잠시 뒤 다시 질문하세요."))
        self.routed_via = response.headers.get("X-Routed-Via")
        try:
            message = response.json()["choices"][0]["message"]
            if message.get("role") != "assistant":
                raise ValueError
            if not message.get("content") and not message.get("tool_calls"):
                raise ValueError
            return {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise RuntimeError("FreeLLMAPI 응답 형식이 올바르지 않거나 답변이 비어 있습니다.") from None
