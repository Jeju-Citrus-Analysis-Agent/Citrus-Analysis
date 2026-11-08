"""데이터 품질 이슈(Q3~Q11) 점검 결과를 출력한다.

실행: python scripts/check_quality.py   (먼저 python scripts/make_dataset.py)
"""

import pandas as pd

from jeju_citrus.config import INTERIM_DIR
from jeju_citrus.data import load_processed
from jeju_citrus.data.clean_quality import validate_fruit_hierarchy
from jeju_citrus.data.quality_checks import (
    market_coverage,
    monthly_box_vs_daily,
    monthly_table_vs_daily,
    shipment_coverage,
    structural_break,
)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def section(title: str, df: pd.DataFrame) -> None:
    print(f"\n=== {title} ===")
    print(df.to_string(index=False))


def main() -> None:
    daily = load_processed("citrus_price_daily")
    production = load_processed("citrus_production_yearly")

    fruit = pd.read_csv(INTERIM_DIR / "fruit_production_clean.csv", encoding="utf-8-sig")
    section("Q4 만감류 품종 합계 vs 만감류노지+하우스", validate_fruit_hierarchy(fruit))

    crops = pd.read_csv(INTERIM_DIR / "jeju_special_crops_clean.csv", encoding="utf-8-sig")
    section(
        "Q5 단수 이상 표시 건수",
        crops["단수_이상"].fillna("정상").value_counts().rename_axis("구분").reset_index(),
    )

    section(
        "Q7 월별 표 vs 일별 출하 (2025년산)",
        monthly_table_vs_daily(load_processed("noji_monthly_2025"), daily),
    )
    section(
        "Q7 시즌별 출하비율 (일별 출하 합계 / 연간 처리량)",
        shipment_coverage(daily, load_processed("noji_yearly")),
    )

    section(
        "Q8 단가 기준 판정",
        production.groupby("단가_검증").size().rename("건수").reset_index(),
    )
    cols = ["품종", "연도", "생산량_톤", "처리량_추정_톤", "단가_원_kg", "단가_검증"]
    section("Q8·Q9 처리량기준·확인불가 행", production.loc[production["단가_검증"] != "일치", cols])

    section("Q9 2016→2017 통계 단절", structural_break(production, 2017))

    section(
        "Q11 월별 상자규격 표 vs 일별 도매",
        monthly_box_vs_daily(load_processed("citrus_price_monthly_box"), daily),
    )
    section(
        "Q11 9대 도매시장 vs 일별 도매 (2025년산)",
        market_coverage(load_processed("noji_market_2025"), daily),
    )


if __name__ == "__main__":
    main()
