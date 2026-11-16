"""CLI 진입점. 웹과 동일한 Agent를 사용하며 연결 오류 후에도 입력을 받는다."""
import argparse
import json
import sys

from .agent import Agent
from .tools import catalog


def main():
    # Model replies can contain Unicode spaces and symbols outside Windows cp949.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="API 키 없이 사용하는 제주 감귤 분석 도우미")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--offline", action="store_true", help="모델 연결 없이 원자료 조회·분석·가정 계산 실행")
    parser.add_argument("--diagnose", action="store_true", help="로컬 자료와 실행 환경 확인")
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
            from .local_tools import TOOL_GUIDE
            print(f"API 키 없이 실행합니다. 사용 가능한 추가 도구: {len(TOOL_GUIDE)}개")
            print("생산 원자료:", "확인됨" if any(r['name'] == 'fruit_production' and r['available'] for r in catalog()['datasets']) else "없음")
            return
        agent = Agent(local_only=True)
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
