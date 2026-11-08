"""[FR-104] 유통처리 통합 엑셀(raw/distribution_analysis.xlsx) → processed CSV 5종.

시트 이름과 출력 파일 이름의 대응은 ``SHEET_TO_DATASET``에서만 관리한다.
"""

import pandas as pd

from jeju_citrus.config import DEFAULT_ENCODING, PROCESSED_DIR, RAW_DISTRIBUTION_XLSX

SHEET_TO_DATASET = {
    "노지온주_연도별": "noji_yearly",
    "노지온주_2025_월별": "noji_monthly_2025",
    "노지온주_2025_도매시장별": "noji_market_2025",
    "노지온주_크기별가격": "noji_size",
    "품종별_유통처리비교": "varieties_summary",
}


def extract_distribution(path=RAW_DISTRIBUTION_XLSX) -> dict[str, pd.DataFrame]:
    """엑셀의 시트 5개를 읽어 {데이터셋 이름: DataFrame}으로 돌려준다."""
    sheets = pd.read_excel(path, sheet_name=list(SHEET_TO_DATASET))
    return {SHEET_TO_DATASET[name]: df.dropna(how="all") for name, df in sheets.items()}


def main() -> None:
    for name, df in extract_distribution().items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False, encoding=DEFAULT_ENCODING)
        print(f"[저장] processed/{name}.csv ({len(df)}행)")


if __name__ == "__main__":
    main()
