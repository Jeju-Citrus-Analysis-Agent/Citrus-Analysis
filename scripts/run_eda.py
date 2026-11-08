"""탐색적 데이터 분석(EDA) 실행 스크립트.

실행: python scripts/run_eda.py
"""

from jeju_citrus.data import load_processed, load_raw
from jeju_citrus.visualization import set_style


def main() -> None:
    set_style()

    print("=== 1. 데이터 로드 및 확인 ===")
    # 1. 과수 생산량 통계 로드
    df_fruit = load_raw("fruit_production.csv")
    print("과수 생산량 통계 샘플:")
    print(df_fruit.head(3))

    # 2. 제주 특용작물 생산현황 로드
    df_crop_jeju = load_processed("jeju_special_crops")
    print("\n제주 특용작물 데이터 샘플:")
    print(df_crop_jeju.head(3))

    # 3. 노지온주 유통처리/연도별 데이터 로드
    df_noji_yearly = load_processed("noji_yearly")
    print("\n노지온주 연도별 처리량/조수입 샘플:")
    print(df_noji_yearly)

    print("\n=== 2. 기초 통계 및 EDA 분석 기본 뼈대 완료 ===")


if __name__ == "__main__":
    main()
