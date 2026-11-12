"""CLI 진입점. 웹과 동일한 Agent를 사용하며 연결 오류 후에도 입력을 받는다."""
import argparse
import json
import sys

from .agent import Agent
from .client import FreeLLMClient, LazyFreeLLMClient
from .tools import catalog


def main():
    # Model replies can contain Unicode spaces and symbols outside Windows cp949.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="FreeLLMAPI 제주 감귤 분석 에이전트")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--diagnose", action="store_true", help="실제 서버 연결 확인")
    parser.add_argument("--catalog", action="store_true", help="API 없이 로컬 데이터 확인")
    parser.add_argument("--data-guide", action="store_true", help="API 없이 자료 정의·기간 안내")
    args = parser.parse_args()
    try:
        if args.data_guide:
            from .data_catalog import markdown
            print(markdown(catalog()))
            return
        if args.catalog:
            print(json.dumps(catalog(), ensure_ascii=False, indent=2))
            return
        if args.diagnose:
            client = FreeLLMClient()
            print(client.complete([{"role": "user", "content": "Reply only OK."}])["content"])
            print("실제 처리 모델:", client.routed_via or "헤더 정보 없음")
            return
        agent = Agent(LazyFreeLLMClient())
        if args.question:
            print(agent.ask(args.question))
            return
        while True:
            question = input("질문 (/help 도움말, /exit 종료, /reset 초기화): ").strip()
            if question == "/exit":
                return
            if question == "/reset":
                agent.reset()
            elif question:
                try:
                    print(agent.ask(question))
                except RuntimeError as exc:
                    print(str(exc))
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    except (KeyboardInterrupt, EOFError):
        return


if __name__ == "__main__":
    main()
