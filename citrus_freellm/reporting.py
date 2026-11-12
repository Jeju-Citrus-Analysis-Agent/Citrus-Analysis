"""Export only successful, recorded results; no model invocation or arbitrary paths."""
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

OUTPUT = Path(__file__).resolve().parent / "reports" / "exported"


def inline(text):
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    # Source links are HTTPS only; escaped arbitrary HTML remains inert.
    return re.sub(r"\[([^\]\n]+)\]\((https://[^\s)]+)\)",
                  lambda m: '<a href="' + m[2] + '" rel="noopener noreferrer">' + m[1] + '</a>', escaped)


def html_body(markdown):
    result, in_table = [], False
    for line in markdown.splitlines():
        if line.startswith("|"):
            if re.fullmatch(r"[| :\-]+", line):
                continue
            if not in_table:
                result.append("<table>")
                in_table = True
            cells = line.strip("|").split("|")
            result.append("<tr>" + "".join("<td>" + html.escape(c.strip()) + "</td>" for c in cells) + "</tr>")
        else:
            if in_table:
                result.append("</table>")
                in_table = False
            if line.startswith("#"):
                result.append("<h2>" + html.escape(line.lstrip("# ")) + "</h2>")
            elif line:
                result.append("<p>" + inline(line) + "</p>")
    if in_table:
        result.append("</table>")
    return "\n".join(result)


def save_report(records, all_results=False):
    """성공 기록을 세 형식으로 내보낸다. UI도 이 함수를 직접 재사용한다."""
    if not records:
        raise ValueError("저장할 성공한 분석 결과가 없습니다. 먼저 조회·분석·가정 계산을 실행해 주세요.")
    chosen = records if all_results else records[-1:]
    now = datetime.now(timezone(timedelta(hours=9)))
    name = "citrus_" + now.strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    markdown = ["# 제주 감귤 분석 리포트", "", "작성 시각: " + now.isoformat(),
                "", "실측 조회·기존 분석 요약·사용자 가정 계산을 구분한 로컬 리포트입니다.",
                "모든 결과가 최신 자료이거나 실제 농가 실적이라는 뜻은 아닙니다."]
    for index, record in enumerate(chosen, 1):
        label = {"verified_lookup": "원자료 조회", "verified_calculation": "원자료 기반 계산",
                 "user_scenario": "사용자 가정 계산", "analysis_explanation": "기존 분석 근거 설명"}[record["kind"]]
        markdown += ["", f"## 결과 {index} — {label}", "질문: " + record["question"],
                     "", record["text"]]
        if record.get("recorded_at"):
            markdown += ["", "결과 작성 시각: " + record["recorded_at"]]
        if record.get("validation"):
            markdown += ["확인 범위: " + record["validation"]]
    markdown += ["", "세부 계산 조건과 출처의 파일 버전 기록은 함께 저장된 JSON 파일에 있습니다."]
    body = "\n".join(markdown)
    payload = {"generated_at": now.isoformat(), "results": chosen}
    paths = []
    for extension, content in (("md", body), ("json", json.dumps(payload, ensure_ascii=False, indent=2, default=str)),
                               ("html", '<!doctype html><html lang="ko"><meta charset="utf-8"><title>감귤 분석 리포트</title>'
                                '<style>body{max-width:1000px;margin:32px auto;padding:16px;font-family:sans-serif;line-height:1.6}table{border-collapse:collapse}td{border:1px solid #aaa;padding:8px}p{overflow-wrap:anywhere}</style>'
                                + html_body(body) + "</html>")):
        path = (OUTPUT / (name + "." + extension)).resolve()
        if not path.is_relative_to(OUTPUT.resolve()):
            raise ValueError("리포트 저장 경로 오류")
        path.write_text(content, encoding="utf-8")
        paths.append(str(path))
    return paths
