"""원본(raw) → 분석용(processed) 데이터 정제 파이프라인.

[FR-101] 전국 특용작물 데이터에서 '제주특별자치도'만 추출한다.
"""

import pandas as pd

from jeju_citrus.config import (
    DEFAULT_ENCODING,
    JEJU_REGION_NAME,
    PROCESSED_DIR,
    RAW_CROP_PRODUCTION,
)
from jeju_citrus.data.loader import load_raw


def filter_jeju(df: pd.DataFrame, region_col: str = "시도") -> pd.DataFrame:
    """시도 컬럼 기준으로 제주 데이터만 남긴다."""
    return df[df[region_col] == JEJU_REGION_NAME].reset_index(drop=True)


def build_jeju_special_crops() -> pd.DataFrame:
    """전국 특용작물 생산현황 → 제주 특용작물 데이터 생성 후 저장."""
    df = filter_jeju(load_raw(RAW_CROP_PRODUCTION.name))
    out = PROCESSED_DIR / "jeju_special_crops.csv"
    df.to_csv(out, index=False, encoding=DEFAULT_ENCODING)
    print(f"[저장] {out.relative_to(PROCESSED_DIR.parents[1])} ({len(df)}행)")
    return df


def main() -> None:
    """원본이 있는 데이터셋을 모두 processed로 다시 만든다(다운로드는 하지 않음)."""
    from jeju_citrus.config import JASDC_RAW_DIR, WEATHER_DIR
    from jeju_citrus.data import (
        clean_jasdc,
        clean_jasdc_manual,
        clean_quality,
        clean_weather,
        extract_distribution,
    )

    build_jeju_special_crops()
    extract_distribution.main()
    if (JASDC_RAW_DIR / "manifest.json").exists():
        clean_jasdc.main()
    else:
        print("[건너뜀] jasdc 원본 없음 → python scripts/collect_jasdc.py")
    clean_jasdc_manual.main()
    if any(WEATHER_DIR.glob("asos_daily_*.csv")):
        clean_weather.main()
    clean_quality.main()  # 품질 이슈 Q3~Q5 정제 → interim/


if __name__ == "__main__":
    main()
