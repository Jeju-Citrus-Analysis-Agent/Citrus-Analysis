"""분석 전 공통 전처리 함수."""

import pandas as pd

# 합계 행으로 쓰이는 라벨 (분석 시 개별 항목과 섞이지 않도록 제외)
TOTAL_LABELS = ("계", "소계", "합계")


def parse_crop_year(s: pd.Series) -> pd.Series:
    """'2025년산' 같은 산지연도 문자열을 정수 연도(2025)로 변환한다."""
    return s.astype(str).str.extract(r"(\d{4})", expand=False).astype("Int64")


def drop_total_rows(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """``col`` 값이 '계'/'소계'/'합계'인 합계 행을 제거한다."""
    return df[~df[col].isin(TOTAL_LABELS)].reset_index(drop=True)
