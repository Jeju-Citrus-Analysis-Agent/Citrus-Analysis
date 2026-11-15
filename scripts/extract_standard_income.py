"""감귤유통처리분석 PDF의 '표준소득 분석표' → data/external/cost/standard_income.csv

입력: data/raw/jasdc_manual/reports/distribution_analysis_{산지연도}.pdf
      (jasdc.or.kr > 알림공간 > 센터간행물에서 받은 원본, git 제외)
필요 패키지: pypdf  (pip install pypdf)

표 하나는 각주 "주) 자가노동비는 …"로 끝나므로 그 각주로 표를 나눈다.
표 안의 "계" 줄 4개는 순서대로 총수입 · 중간재비 · 경영비 · 생산비다.
2023년산은 품종명 글꼴이 깨져 있어 다른 연도와 같은 표 순서로 품종을 붙이고
`분류근거` 컬럼에 '표 순서'로 표시한다. 소득 = 총수입 - 경영비 검산(±2원)을 통과한 표만 쓴다.

텍스트를 읽을 수 없는 연도 (2016·2018·2019년산은 스캔 이미지, 2020·2021년산은 글꼴이
글리프 코드로만 추출됨)는 쪽 이미지를 보고 손으로 옮긴
data/external/cost/standard_income_transcribed.csv 를 합친다. 손으로 옮긴 표는
소득 = 총수입 - 경영비, 생산비 = 경영비 + 자가노동비 + 자본용역비 두 검산을 모두 통과해야 한다.
원문 오기 2건(2020년산 시설감귤·하우스월동감귤의 경영비 '계')은 구성항목 합으로 정정하고 `비고`에 적었다.

텍스트를 읽을 수 있는 연도(2017·2022~2024년산)는 경영비 세부 항목(비료·농약·수도광열비 등)도
data/external/cost/standard_income_items.csv 로 저장한다 (품종별 경영비 물가지수 가중치용).
"""

import logging
import re

import pandas as pd
import pypdf

from jeju_citrus.config import DEFAULT_ENCODING, JASDC_MANUAL_DIR, STANDARD_INCOME

logging.disable(logging.WARNING)  # pypdf 글꼴 경고

REPORT_DIR = JASDC_MANUAL_DIR / "reports"
ORDER = ["노지감귤", "시설감귤", "하우스월동감귤", "한라봉", "천혜향", "레드향", "황금향"]
TO_PROJECT = {
    "노지감귤": "노지온주",
    "시설감귤": "하우스온주",
    "하우스월동감귤": "월동온주",
    "한라봉": "한라봉",
    "천혜향": "천혜향",
    "레드향": "레드향",
    "황금향": "황금향",
}
NUM = r"(\d[\d,.]*)"

# 경영비 세부 항목: 저장 키 → 표에 적힌 이름 (글자 사이 공백·가운뎃점 변형은 무시)
COST_ITEMS = {
    "보통비료비": "보통(무기질)비료비",
    "부산물비료비": "부산물(유기질)비료비",
    "농약비": "농약비",
    "수도광열비": "수도광열비",
    "기타재료비": "기타재료비",
    "소농구비": "소농구비",
    "대농구상각비": "대농구상각비",
    "영농시설상각비": "영농시설상각비",
    "수리유지비": "수리·유지비",
    "과수원조성비": "과수원조성비",
    "기타비용": "기타비용",
    "농기계시설임차료": "농기계·시설임차료",
    "토지임차료": "토지임차료",
    "위탁영농비": "위탁영농비",
    "고용노동비": "고용노동비",
}
DOTS = "·․ㆍ・"


def _label_pattern(label: str) -> str:
    parts = ["[" + DOTS + "]?" if c in DOTS else re.escape(c) for c in label if not c.isspace()]
    return r"\s*".join(parts)


def parse_cost_items(seg: str) -> dict[str, int]:
    """표 한 개의 경영비 세부 항목(원/10a). 비어 있거나 '-'이면 0."""
    out = {}
    for key, label in COST_ITEMS.items():
        m = re.search(_label_pattern(label) + r"\s*(?:[\d.]+\s*시간\s*)?(\d[\d,]*|-)", seg)
        out[key] = 0 if m is None or m.group(1) == "-" else int(m.group(1).replace(",", ""))
    return out


def _int(s: str) -> int:
    # 원 단위 정수. 원문 오타(예: 4,222.438)도 정수로 읽는다.
    return int(s.replace(",", "").replace(".", ""))


def parse_pdf(path, year: int) -> list[dict]:
    rows = []
    seen = set()
    for pno, page in enumerate(pypdf.PdfReader(path).pages, 1):
        text = (page.extract_text() or "").replace("\x00", " ")
        for seg in re.split(r"주\)\s*자가\s*노동비", text):
            if "상품화율" not in seg or not re.search(r"자\s*가\s*노\s*동\s*비", seg):
                continue
            sums = [_int(x) for x in re.findall(r"^\s*계\s*" + NUM + r"\s*$", seg, re.M)]
            if len(sums) != 4 or tuple(sums) in seen:  # 2023년산은 같은 표가 두 쪽에 반복 추출됨
                continue
            seen.add(tuple(sums))
            title = re.search(r"[❏□■]\s*(\S+?)\s*표준\s*소득\s*분석표", seg)
            inc = re.search(r"^\s*소\s*득\s*" + NUM + r"\s*$", seg, re.M)
            own = re.search(r"자\s*가\s*노\s*동\s*비\s*([\d.]+)\s*시간\s*" + NUM, seg)
            qty = re.search(r"([\d,]+)\s*kg\s+([\d,]+)\s+([\d,]+)", seg)
            idx = len(rows)
            name = title.group(1) if title else ORDER[idx]
            base = re.sub(r"\(.*\)", "", name)  # 레드향(감평) → 레드향
            rows.append(
                {
                    **{f"항목_{k}": v for k, v in parse_cost_items(seg).items()},
                    "산지연도": year,
                    "원문분류": base,
                    "대응품종": TO_PROJECT.get(base),
                    "분류근거": "제목" if title else "표 순서",
                    "총수입_원_10a": sums[0],
                    "중간재비_원_10a": sums[1],
                    "경영비_원_10a": sums[2],
                    "생산비_원_10a": sums[3],
                    "소득_원_10a": _int(inc.group(1)) if inc else None,
                    "자가노동시간_10a": float(own.group(1)) if own else None,
                    "자가노동비_원_10a": _int(own.group(2)) if own else None,
                    "수량_kg_10a": _int(qty.group(1)) if qty else None,
                    "단가_원_kg": _int(qty.group(2)) if qty else None,
                    "PDF쪽": pno,
                }
            )
    return rows


TRANSCRIBED = STANDARD_INCOME.parent / "standard_income_transcribed.csv"


def load_transcribed() -> pd.DataFrame:
    t = pd.read_csv(TRANSCRIBED, encoding=DEFAULT_ENCODING)
    capital = t["유동자본"] + t["고정자본"] + t["토지자본"]
    gap = (t["경영비"] + t["자가노동비"] + capital - t["생산비"]).abs()
    if (gap > 2).any():
        raise ValueError(f"판독본 생산비 검산 실패:\n{t[gap > 2]}")
    return pd.DataFrame(
        {
            "산지연도": t["산지연도"],
            "원문분류": t["원문분류"],
            "대응품종": t["원문분류"].map(TO_PROJECT),
            "분류근거": "제목 (쪽 이미지 판독)",
            "총수입_원_10a": t["총수입"],
            "중간재비_원_10a": t["중간재비"],
            "경영비_원_10a": t["경영비"],
            "생산비_원_10a": t["생산비"],
            "소득_원_10a": t["소득"],
            "자가노동시간_10a": t["자가노동시간"],
            "자가노동비_원_10a": t["자가노동비"],
            "수량_kg_10a": t["수량_kg_10a"],
            "단가_원_kg": t["단가_원_kg"],
            "PDF쪽": t["PDF쪽"],
            "비고": t["비고"],
        }
    )


def main() -> None:
    rows = []
    for path in sorted(REPORT_DIR.glob("distribution_analysis_*.pdf")):
        year = int(re.search(r"(\d{4})", path.stem).group(1))
        got = parse_pdf(path, year)
        print(f"{path.name}: 표 {len(got)}개")
        rows += got
    parsed = pd.DataFrame(rows)
    item_cols = [c for c in parsed.columns if c.startswith("항목_")]
    items = parsed[["산지연도", "원문분류", "대응품종", *item_cols, "경영비_원_10a"]].copy()
    items.columns = [c.removeprefix("항목_") for c in items.columns]
    items["항목합"] = items[list(COST_ITEMS)].sum(axis=1)
    items["차이"] = items["항목합"] - items["경영비_원_10a"]
    for _, r in items[items["차이"].abs() > 2].iterrows():
        print(f"  주의: {r['산지연도']} {r['원문분류']} 항목합 - 경영비 계 = {r['차이']:+,}원 (원문 표 안의 불일치)")
    items.to_csv(STANDARD_INCOME.parent / "standard_income_items.csv", index=False, encoding=DEFAULT_ENCODING)
    parsed = parsed.drop(columns=item_cols)
    transcribed = load_transcribed()
    overlap = set(parsed["산지연도"]) & set(transcribed["산지연도"])
    if overlap:
        raise ValueError(f"PDF 추출과 판독본 연도가 겹침: {overlap}")
    print(f"판독본: 표 {len(transcribed)}개 ({sorted(transcribed['산지연도'].unique())})")
    df = pd.concat([parsed, transcribed], ignore_index=True).sort_values(["산지연도", "PDF쪽"])
    df = df.reset_index(drop=True)
    df["순수익_원_10a"] = df["총수입_원_10a"] - df["생산비_원_10a"]
    gap = (df["총수입_원_10a"] - df["경영비_원_10a"] - df["소득_원_10a"]).abs()
    bad = df[gap > 2]
    if len(bad):
        raise ValueError(f"소득 검산 실패:\n{bad}")
    for col in ["총수입", "경영비", "소득", "생산비", "순수익"]:
        df[f"{col}_만원_10a"] = (df[f"{col}_원_10a"] / 10_000).round(1)
    df["출처"] = "제주농산물수급관리센터(감귤출하연합회), " + df["산지연도"].astype(str) + "년산 감귤유통처리 분석"
    STANDARD_INCOME.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(STANDARD_INCOME, index=False, encoding=DEFAULT_ENCODING)
    print(f"저장: {STANDARD_INCOME} ({len(df)}행)")


if __name__ == "__main__":
    main()
