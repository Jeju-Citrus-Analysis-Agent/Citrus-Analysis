"""CSV 데이터 로더.

사용 예::

    from jeju_citrus.data import load_processed
    df = load_processed("noji_yearly")
"""

from pathlib import Path

import pandas as pd

from jeju_citrus.config import (
    DEFAULT_ENCODING,
    PROCESSED_DIR,
    RAW_DIR,
    RAW_ENCODINGS,
)

# 분석용 데이터셋 이름 → 설명
PROCESSED_DATASETS = {
    "jeju_special_crops": "제주 특용작물 생산현황 (전국 데이터에서 제주만 추출)",
    "noji_yearly": "노지온주 5개년 연도별 처리량·단가·조수입",
    "noji_monthly_2025": "2025년산 노지온주 월별 출하량·가격",
    "noji_market_2025": "2025년산 노지온주 도매시장별 거래량·가격",
    "noji_size": "최근 3개년 노지온주 규격(2S~2L)별 가격·비율",
    "varieties_summary": "품종별(하우스/월동/만감류) 유통처리 비교",
    # 제주농산물수급관리센터 수집 데이터 (python scripts/collect_jasdc.py 로 생성)
    "citrus_production_yearly": "8개 품종 연도별 재배면적·생산량·조수입·농가수·단가 (2004~2025)",
    "citrus_processing_yearly": "연도별 총처리량·가공처리량·가공률·수매단가 (2004~2025)",
    "citrus_processing_by_company": "연도별·가공업체별 가공처리량 (2004~2025)",
    "citrus_export_yearly": "연도별·국가별 수출량·수출액 (2003~2025)",
    # 수동 수집(data/raw/jasdc_manual) → clean_jasdc_manual
    "citrus_price_daily": "노지온주 일별 출하량·평균가 (합계/도매시장/직거래), 2021-10~",
    "citrus_price_monthly_box": "월별·상자규격별 도매 거래량·가격, 시즌별",
    # 기상청 ASOS (data/external/weather) → clean_weather
    "weather_daily": "제주·고산·성산·서귀포 일별 기온·강수·습도·일조·일사 (2004~)",
    "weather_monthly": "지점별 월별 기상 요약 + 폭염·열대야·영하·호우 일수 (2004~)",
}


def find_raw(filename: str) -> Path:
    """``data/raw`` 아래 하위 폴더까지 뒤져서 파일 경로를 찾는다.

    ``"public/crop_production.csv"``처럼 폴더를 붙여도 되고, 파일 이름만 줘도 된다.
    """
    path = RAW_DIR / filename
    if path.exists():
        return path
    matches = sorted(RAW_DIR.rglob(Path(filename).name))
    if len(matches) != 1:
        raise FileNotFoundError(f"data/raw에서 {filename!r}을(를) 하나로 찾지 못함: {matches}")
    return matches[0]


def load_raw(filename: str) -> pd.DataFrame:
    """``data/raw``의 원본 CSV를 파일별 인코딩에 맞춰 읽는다."""
    path = find_raw(filename)
    filename = path.name
    encoding = RAW_ENCODINGS.get(filename, DEFAULT_ENCODING)
    return pd.read_csv(path, encoding=encoding)


def load_processed(name: str) -> pd.DataFrame:
    """``data/processed``의 데이터셋을 이름(확장자 제외)으로 읽는다."""
    if name not in PROCESSED_DATASETS:
        available = ", ".join(PROCESSED_DATASETS)
        raise KeyError(f"알 수 없는 데이터셋: {name!r} (사용 가능: {available})")
    return pd.read_csv(PROCESSED_DIR / f"{name}.csv", encoding=DEFAULT_ENCODING)


def load_standard_income(year: int | None = None) -> pd.DataFrame:
    """감귤 표준소득표 (원·만원/10a). ``year``를 주면 그 산지연도만 돌려준다.

    ``python scripts/extract_standard_income.py``로 보고서 PDF에서 생성한다.
    """
    from jeju_citrus.config import STANDARD_INCOME

    df = pd.read_csv(STANDARD_INCOME, encoding=DEFAULT_ENCODING)
    if year is not None:
        df = df[df["산지연도"] == year].reset_index(drop=True)
    return df


def load_cpi() -> pd.DataFrame:
    """연평균 소비자물가지수 (2020=100)."""
    from jeju_citrus.config import CPI_ANNUAL

    return pd.read_csv(CPI_ANNUAL, encoding=DEFAULT_ENCODING)


def load_farm_purchase_index(freq: str = "annual") -> pd.DataFrame:
    """KOSIS 농가구입가격지수(2020=100)를 항목별 열로 돌려준다.

    - ``freq="quarter"``: 행 = 분기(``"2025.4/4"``), 열 = 항목
    - ``freq="annual"``: 4개 분기가 모두 있는 연도만, 분기 단순평균. 공식 연평균은 계절 가중치를
      쓰므로 0.1 정도 다를 수 있다 (2024년 120.2 vs 공표 120.1, 2025년 121.6 일치).

    원본에서 같은 이름이 두 번 나오는 항목(``노무비``: 대분류와 소분류, 값 동일)은 첫 행만 쓴다.
    ``-``(미조사)는 NaN.
    """
    from jeju_citrus.config import FARM_PURCHASE_INDEX_RAW

    raw = pd.read_csv(FARM_PURCHASE_INDEX_RAW, encoding=DEFAULT_ENCODING).iloc[1:]  # 2행: 반복 제목
    raw = raw.rename(columns={raw.columns[0]: "항목"}).drop_duplicates("항목")
    quarter = raw.set_index("항목").T.apply(pd.to_numeric, errors="coerce")
    quarter.index.name = "분기"
    quarter.columns.name = None
    if freq == "quarter":
        return quarter
    if freq != "annual":
        raise ValueError(f"freq는 'annual' 또는 'quarter': {freq!r}")
    year = quarter.index.str[:4].astype(int)
    n_quarters = pd.Series(year).value_counts()
    annual = quarter.groupby(year).mean()
    annual = annual.loc[sorted(n_quarters[n_quarters == 4].index)]
    annual.index.name = "연도"
    return annual


def load_standard_income_items() -> pd.DataFrame:
    """표준소득표 경영비 세부 항목 (원/10a). 텍스트 추출이 되는 2017·2022~2024년산만."""
    from jeju_citrus.config import STANDARD_INCOME

    return pd.read_csv(STANDARD_INCOME.parent / "standard_income_items.csv", encoding=DEFAULT_ENCODING)
