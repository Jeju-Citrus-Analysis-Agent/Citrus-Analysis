"""jasdc 원본 표(data/raw/jasdc) → 분석용 데이터(data/processed) 정제.

생성 파일
- citrus_production_yearly.csv     : 8개 품종 연도별 재배면적·생산량·조수입·농가수·단가 (long 형식)
- citrus_processing_yearly.csv     : 연도별 총처리량·가공처리량·가공률·수매단가
- citrus_processing_by_company.csv : 연도별·가공업체별 가공처리량 (long 형식)
- citrus_export_yearly.csv         : 연도별·국가별 수출량·수출액 (long 형식)
"""

import re

import pandas as pd

from jeju_citrus.config import DEFAULT_ENCODING, JASDC_RAW_DIR, PROCESSED_DIR

VARIETIES = ["노지온주", "하우스온주", "월동온주", "한라봉", "천혜향", "레드향", "황금향", "카라향"]
VARIETY_GROUP = {
    "노지온주": "온주밀감",
    "하우스온주": "온주밀감",
    "월동온주": "온주밀감",
    "한라봉": "만감류",
    "천혜향": "만감류",
    "레드향": "만감류",
    "황금향": "만감류",
    "카라향": "만감류",
}
EOK_TO_MILLION = 100  # 1억원 = 100백만원


# ------------------------------------------------------------------ 변환 함수
def to_number(s: pd.Series) -> pd.Series:
    """'1,463.0', '-', '' 같은 문자열을 숫자로 바꾼다. '-'와 빈 칸은 결측(NaN)."""
    cleaned = s.astype(str).str.replace(",", "", regex=False).str.strip()
    cleaned = cleaned.replace({"-": None, "": None, "nan": None})
    return pd.to_numeric(cleaned, errors="coerce")


def fix_thousands_typo(s: pd.Series) -> pd.Series:
    """천 단위 쉼표를 마침표로 잘못 쓴 값(예: '6.375' → '6,375')을 바로잡는다.

    정수만 들어가야 하는 컬럼(단가 등)에만 사용한다.
    """
    return s.astype(str).str.replace(r"^(\d{1,3})\.(\d{3})$", r"\1,\2", regex=True)


def parse_short_year(s: pd.Series) -> pd.Series:
    """ "'25" → 2025, "'03" → 2003 (수출현황 표의 연도 표기)."""
    yy = s.astype(str).str.extract(r"(\d{2})\s*$", expand=False).astype(int)
    return (2000 + yy).astype("Int64")


def _read_raw(name: str) -> pd.DataFrame:
    return pd.read_csv(
        JASDC_RAW_DIR / f"{name}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )


# ------------------------------------------------------------------ 데이터셋별 정제
def clean_production(variety: str, raw: pd.DataFrame) -> pd.DataFrame:
    """품종 하나의 생산정보 표를 표준 컬럼으로 정제한다. 조수입은 백만원으로 통일."""
    revenue_col = next(c for c in raw.columns if c.startswith("조수입"))
    revenue_scale = EOK_TO_MILLION if "억원" in revenue_col else 1

    df = pd.DataFrame(
        {
            "품종": variety,
            "품종그룹": VARIETY_GROUP[variety],
            "연도": to_number(raw["연도별"]).astype("Int64"),
            "재배면적_ha": to_number(raw["재배면적(ha)"]),
            "생산량_톤": to_number(raw["생산량(톤)"]),
            "조수입_백만원": to_number(raw[revenue_col]) * revenue_scale,
            "재배농가_호": to_number(raw["재배농가(호)"]).astype("Int64"),
            "단가_원_kg": to_number(fix_thousands_typo(raw["kg당 가격(원)"])),
        }
    )
    return df


def build_production() -> pd.DataFrame:
    frames = [clean_production(v, _read_raw(f"production_{v}")) for v in VARIETIES]
    df = pd.concat(frames, ignore_index=True).sort_values(["품종", "연도"]).reset_index(drop=True)
    # 파생 지표: 면적당 생산량·조수입
    df["ha당_생산량_톤"] = df["생산량_톤"] / df["재배면적_ha"]
    df["ha당_조수입_백만원"] = df["조수입_백만원"] / df["재배면적_ha"]
    return add_price_basis(df)


PRICE_MATCH_TOL = 0.05  # 단가 ≈ 조수입/생산량 으로 보는 허용 오차
PRICE_BASIS_MAX = 1.5  # 처리량이 생산량의 2/3보다 작다고 나오면 처리량 기준으로도 설명 불가


def add_price_basis(df: pd.DataFrame) -> pd.DataFrame:
    """[Q8·Q9] 단가의 기준 물량을 밝히는 컬럼을 덧붙인다.

    jasdc 단가는 ``조수입 ÷ 생산량``이 아니라 ``조수입 ÷ 유통 처리량``이다
    (2024년 7개 품종 모두 유통처리 엑셀의 처리량으로 나누면 단가와 1원 단위까지 일치).

    - ``처리량_추정_톤`` = 조수입 ÷ 단가 : 단가에서 거꾸로 구한 처리량
    - ``단가_검증``
        - ``일치``       : 단가 ≈ 조수입/생산량 (±5%) → 그 해는 생산량 = 처리량으로 집계
        - ``처리량기준`` : 처리량이 생산량의 67~95% → 단가는 정상, 생산량과 물량 기준만 다름
        - ``확인불가``   : 처리량 > 생산량이거나 생산량의 2/3 미만
          → 원본 값 오류 가능성, 단가 분석에서 제외 권장
    """
    implied_volume = df["조수입_백만원"] * 1e3 / df["단가_원_kg"]
    ratio = df["생산량_톤"] / implied_volume  # = 단가 / (조수입/생산량)
    basis = pd.Series("확인불가", index=df.index)
    basis = basis.mask((ratio > 1 + PRICE_MATCH_TOL) & (ratio <= PRICE_BASIS_MAX), "처리량기준")
    basis = basis.mask((ratio - 1).abs() <= PRICE_MATCH_TOL, "일치")
    basis = basis.where(ratio.notna())
    return df.assign(처리량_추정_톤=implied_volume.round(0), 단가_검증=basis)


def build_processing() -> pd.DataFrame:
    raw = _read_raw("processing")
    return (
        pd.DataFrame(
            {
                "연도": to_number(raw["연도별"]).astype("Int64"),
                "총처리량_톤": to_number(raw["총처리량(톤)"]),
                "가공처리량_톤": to_number(raw["가공처리량(톤)"]),
                "가공률_퍼센트": to_number(raw["가 공 율(%)"]),
                "수매단가_원_kg": to_number(raw["수매단가(원/kg)"]),
                "비고": raw["비 고"].str.strip(),
            }
        )
        .sort_values("연도")
        .reset_index(drop=True)
    )


def build_processing_by_company() -> pd.DataFrame:
    raw = _read_raw("processing_by_company").rename(columns={"구 분": "연도"})
    raw = raw.drop(columns=["계"])
    long = raw.melt(id_vars="연도", var_name="가공업체", value_name="가공처리량_톤")
    long["연도"] = to_number(long["연도"]).astype("Int64")
    long["가공업체"] = long["가공업체"].map(lambda c: re.sub(r"\s+", "", c))
    long["가공처리량_톤"] = to_number(long["가공처리량_톤"])
    return long.sort_values(["연도", "가공업체"]).reset_index(drop=True)


def build_export() -> pd.DataFrame:
    raw = _read_raw("export").rename(columns={"구 분": "연도", "구 분.1": "항목"})
    raw = raw.drop(columns=["계"])
    long = raw.melt(id_vars=["연도", "항목"], var_name="국가", value_name="값")
    long["값"] = to_number(long["값"])
    wide = long.pivot_table(
        index=["연도", "국가"], columns="항목", values="값", aggfunc="first"
    ).reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={"수출량": "수출량_톤", "수출액": "수출액_천달러"})
    wide["연도"] = parse_short_year(wide["연도"])
    return wide.sort_values(["연도", "국가"]).reset_index(drop=True)


# ------------------------------------------------------------------ 검증
def validate_production(df: pd.DataFrame, tolerance: float = 0.05) -> pd.DataFrame:
    """단가 ≈ 조수입 / 생산량 인지 확인하고, 5% 넘게 어긋나는 행을 돌려준다."""
    implied = df["조수입_백만원"] * 1e6 / (df["생산량_톤"] * 1e3)
    gap = (implied - df["단가_원_kg"]).abs() / df["단가_원_kg"]
    return df.assign(계산단가_원_kg=implied.round(0), 차이율=gap.round(3))[gap > tolerance]


# ------------------------------------------------------------------ 실행
OUTPUTS = {
    "citrus_production_yearly": build_production,
    "citrus_processing_yearly": build_processing,
    "citrus_processing_by_company": build_processing_by_company,
    "citrus_export_yearly": build_export,
}


def main() -> None:
    for name, builder in OUTPUTS.items():
        df = builder()
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False, encoding=DEFAULT_ENCODING)
        print(f"[저장] processed/{name}.csv ({len(df)}행)")

    bad = validate_production(build_production())
    if len(bad):
        print(f"\n⚠️ 단가 ≠ 조수입/생산량 (5% 초과) {len(bad)}건:")
        print(
            bad[["품종", "연도", "단가_원_kg", "계산단가_원_kg", "차이율"]].to_string(index=False)
        )


if __name__ == "__main__":
    main()
