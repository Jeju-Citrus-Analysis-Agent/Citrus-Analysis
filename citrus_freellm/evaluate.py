"""Explicit opt-in live conversation evaluation, with expected slots and report."""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .agent import Agent
from .client import FreeLLMClient
from .guardrails import lookup_request, render, request_for
from .tools import production

FOLDER = Path(__file__).resolve().parent


def run_case(case, client):
    agent = Agent(client)
    seed = None
    if case["seed"]:
        seed, blocked = request_for(case["seed"])
        if blocked:
            raise ValueError("평가용 초기 조건이 올바르지 않습니다.")
        # Establish context only after a genuine local source check.
        render(production(**lookup_request(seed)), seed, case["seed"])
        agent.previous_request = seed
    try:
        answer = agent.ask(case["question"])
        actual = agent.previous_request
        has_table = "| 연도 |" in answer
        if case.get("blocked"):
            passed = not has_table and actual == seed
        else:
            passed = bool(has_table and actual and actual["variety"] == "천혜향"
                          and actual["years"] == case["years"] and actual["metrics"] == case["metrics"])
        return {"id": case["id"], "question": case["question"], "passed": passed,
                "expected": {k: case[k] for k in ("years", "metrics", "blocked") if k in case},
                "actual": actual, "answer": answer, "routed_via": client.routed_via}
    except (RuntimeError, ValueError, OSError) as exc:
        return {"id": case["id"], "passed": False, "error": str(exc)}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="질문 해석의 실제 모델 평가")
    parser.add_argument("--live", action="store_true", help="질문과 직전 조건을 외부 모델로 전송")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--interval", type=float, default=8, help="사례 간 대기 초 (기본 8)")
    args = parser.parse_args()
    if not args.live:
        parser.exit(0, "실제 공급자에게 질문·직전 조건을 보내려면 --live를 지정하세요.\n")
    if not 1 <= args.repeats <= 5:
        parser.error("--repeats는 1~5 범위입니다.")
    if not 0 <= args.interval <= 30:
        parser.error("--interval은 0~30 범위입니다.")
    cases = json.loads((FOLDER / "evaluation_cases.json").read_text(encoding="utf-8"))
    client = FreeLLMClient()
    results = []
    for repeat in range(args.repeats):
        for case in cases:
            if results:
                time.sleep(args.interval)
            result = run_case(case, client)
            result["repeat"] = repeat + 1
            results.append(result)
            print(f"{'PASS' if result['passed'] else 'FAIL'} {repeat+1}: {case['id']}", flush=True)
    report = {"time": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "passed": sum(r["passed"] for r in results), "total": len(results), "results": results}
    directory = FOLDER / "reports"
    directory.mkdir(exist_ok=True)
    report["connection_errors"] = sum("error" in r for r in results)
    report["interpretation_failures"] = sum(not r["passed"] and "error" not in r for r in results)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    timestamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d_%H%M%S")
    (directory / f"intent_evaluation_{timestamp}.json").write_text(serialized, encoding="utf-8")
    (directory / "intent_evaluation_latest.json").write_text(serialized, encoding="utf-8")
    print(f"Result: {report['passed']}/{report['total']}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
