"""Export only successful, recorded results as Markdown and PDF; no model invocation or arbitrary paths."""
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

OUTPUT = Path(__file__).resolve().parent / "reports" / "exported"

# Korean TrueType fonts, first match wins. CITRUS_PDF_FONT(_BOLD) overrides.
FONT_CANDIDATES = (
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
    ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf"),
    ("/mnt/c/Windows/Fonts/malgun.ttf", "/mnt/c/Windows/Fonts/malgunbd.ttf"),
    ("/Library/Fonts/NanumGothic.ttf", "/Library/Fonts/NanumGothicBold.ttf"),
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", None),
)
LABELS = {"verified_lookup": "원자료 조회", "verified_calculation": "원자료 기반 계산",
          "user_scenario": "사용자 가정 계산", "analysis_explanation": "기존 분석 근거 설명",
          "local_tool": "도구 실행 결과", "consultation": "맞춤 상담 (검증 결과 요약)"}


class PdfUnavailable(RuntimeError):
    """PDF could not be produced (library or Korean font missing); Markdown is still saved."""


def korean_font():
    configured = os.getenv("CITRUS_PDF_FONT")
    if configured:
        return configured, os.getenv("CITRUS_PDF_FONT_BOLD") or None
    for regular, bold in FONT_CANDIDATES:
        if Path(regular).is_file():
            return regular, bold if bold and Path(bold).is_file() else None
    return None, None


def source_lines(record):
    """Provenance kept in the report itself: original links and the exact file versions used."""
    lines = []
    for source in record.get("sources", []):
        origin = source.get("data_origin") or {}
        title = origin.get("title") or source.get("title") or source.get("id") or source.get("type") or "출처"
        url = origin.get("url") or source.get("url")
        parts = [f"[{title}]({url})" if url else title]
        if source.get("path"):
            parts.append(f"파일 {source['path']}")
        if source.get("sha256"):
            parts.append(f"sha256 {source['sha256']}")
        if source.get("note"):
            parts.append(source["note"])
        lines.append("- " + " · ".join(parts))
    return lines


def markdown_report(chosen, now):
    markdown = ["# 제주 감귤 분석 리포트", "", "작성 시각: " + now.isoformat(),
                "", "실측 조회·기존 분석 요약·사용자 가정 계산을 구분한 로컬 리포트입니다.",
                "모든 결과가 최신 자료이거나 실제 농가 실적이라는 뜻은 아닙니다."]
    for index, record in enumerate(chosen, 1):
        markdown += ["", f"## 결과 {index} — {LABELS.get(record['kind'], '결과')}", "질문: " + record["question"],
                     "", record["text"]]
        if record.get("recorded_at"):
            markdown += ["", "결과 작성 시각: " + record["recorded_at"]]
        if record.get("validation"):
            markdown += ["확인 범위: " + record["validation"]]
    markdown += ["", "## 출처 기록", "결과마다 사용한 원문 출처와 파일 버전(sha256)입니다."]
    for index, record in enumerate(chosen, 1):
        markdown += ["", f"결과 {index}:"] + (source_lines(record) or ["- 사용자 입력 (외부 자료 없음)"])
    return "\n".join(markdown)


EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")
LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")


def pdf_text(text):
    # Korean fonts lack emoji and a few math glyphs; keep the meaning in plain characters.
    text = EMOJI.sub("", text).replace("\u2212", "-").replace("`", "")
    return LINK.sub(lambda m: f"{m[1]} ({m[2]})", text)


def write_rich(pdf, text, height, bold_available):
    """Write one paragraph, honouring **bold** spans."""
    for index, part in enumerate(pdf_text(text).split("**")):
        if not part:
            continue
        pdf.set_font("ko", "B" if index % 2 and bold_available else "")
        pdf.write(height, part)
    pdf.set_font("ko", "")
    pdf.ln(height)


def pdf_report(markdown, path):
    try:
        from fpdf import FPDF
        from fpdf.fonts import FontFace
    except ImportError:
        raise PdfUnavailable("PDF 변환 도구(fpdf2)가 설치되지 않았습니다. requirements-ui.txt를 설치해 주세요.") from None
    import logging
    # fontTools reports every hinting table it drops while subsetting; that is not an error.
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    regular, bold = korean_font()
    if not regular:
        raise PdfUnavailable("PDF에 쓸 한글 글꼴을 찾지 못했습니다. CITRUS_PDF_FONT에 .ttf 경로를 지정해 주세요.")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_font("ko", "", regular)
    if bold:
        pdf.add_font("ko", "B", bold)
    pdf.add_page()
    pdf.set_font("ko", "", 10)
    lines = markdown.splitlines() + [""]
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if line.startswith("|"):
            block = []
            while index < len(lines) and lines[index].startswith("|"):
                block.append(lines[index])
                index += 1
            rows = [[pdf_text(c.strip()).replace("**", "") for c in row.strip().strip("|").split("|")]
                    for row in block if not re.fullmatch(r"[| :\-]+", row.strip())]
            if rows:
                pdf.set_font("ko", "", 8 if len(rows[0]) > 4 else 9)
                heading = FontFace(emphasis="BOLD" if bold else None, fill_color=(255, 224, 178))
                with pdf.table(headings_style=heading, line_height=5, padding=1.2) as table:
                    for row in rows:
                        cells = table.row()
                        for value in row + [""] * (len(rows[0]) - len(row)):
                            cells.cell(value)
                pdf.set_font("ko", "", 10)
                pdf.ln(2)
            continue
        index += 1
        if line.startswith("# "):
            pdf.set_font("ko", "B" if bold else "", 17)
            pdf.multi_cell(0, 9, pdf_text(line[2:]))
            pdf.set_font("ko", "", 10)
            pdf.ln(1)
        elif line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("ko", "B" if bold else "", 13)
            pdf.multi_cell(0, 7, pdf_text(line[3:]))
            pdf.set_draw_color(242, 116, 5)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.set_font("ko", "", 10)
            pdf.ln(2)
        elif re.match(r"\s*[-*] ", line):
            pdf.set_x(pdf.l_margin + 4)
            write_rich(pdf, "· " + re.sub(r"^\s*[-*] ", "", line), 5.5, bool(bold))
        elif line.strip():
            write_rich(pdf, line, 5.5, bool(bold))
        else:
            pdf.ln(2)
    pdf.output(str(path))


def save_report(records, all_results=False):
    """성공 기록을 Markdown과 PDF로 내보낸다. PDF를 만들 수 없으면 Markdown만 돌려준다."""
    if not records:
        raise ValueError("저장할 성공한 분석 결과가 없습니다. 먼저 조회·분석·가정 계산을 실행해 주세요.")
    chosen = records if all_results else records[-1:]
    now = datetime.now(timezone(timedelta(hours=9)))
    name = "citrus_" + now.strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    body = markdown_report(chosen, now)
    paths = []
    for extension in ("md", "pdf"):
        path = (OUTPUT / (name + "." + extension)).resolve()
        if not path.is_relative_to(OUTPUT.resolve()):
            raise ValueError("리포트 저장 경로 오류")
        if extension == "md":
            path.write_text(body, encoding="utf-8")
        else:
            try:
                pdf_report(body, path)
            except PdfUnavailable:
                continue
        paths.append(str(path))
    return paths
