"""프로젝트 경로 및 공통 설정.

모든 경로는 이 파일에서만 정의합니다. 코드 어디서든 ``from jeju_citrus.config import ...``로
가져다 쓰면 실행 위치(cwd)와 무관하게 동일한 파일을 찾습니다.
"""

from pathlib import Path

# src/jeju_citrus/config.py → 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"  # 원본 데이터 (수정 금지)
INTERIM_DIR = DATA_DIR / "interim"  # 중간 가공 데이터
PROCESSED_DIR = DATA_DIR / "processed"  # 분석용 최종 데이터
EXTERNAL_DIR = DATA_DIR / "external"  # 외부 참고 데이터 (기상·병해충 등)

REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# 원본 폴더 (출처별)
PUBLIC_RAW_DIR = RAW_DIR / "public"  # 공공데이터 CSV
DISTRIBUTION_RAW_DIR = RAW_DIR / "distribution"  # 감귤 유통처리 통합 엑셀

# 원본 파일
RAW_CROP_PRODUCTION = PUBLIC_RAW_DIR / "crop_production.csv"  # 전국 특용작물 생산현황 (cp949)
RAW_FRUIT_PRODUCTION = PUBLIC_RAW_DIR / "fruit_production.csv"  # 제주 과수 생산량 통계
RAW_DISTRIBUTION_XLSX = DISTRIBUTION_RAW_DIR / "distribution_analysis.xlsx"  # 유통처리 통합 엑셀

RAW_ENCODINGS = {RAW_CROP_PRODUCTION.name: "cp949"}
DEFAULT_ENCODING = "utf-8-sig"

JEJU_REGION_NAME = "제주특별자치도"

# 제주농산물수급관리센터(jasdc.or.kr) 수집 원본
JASDC_RAW_DIR = RAW_DIR / "jasdc"
JASDC_MANUAL_DIR = RAW_DIR / "jasdc_manual"  # 화면 복사·엑셀 수동 수집
WEATHER_DIR = EXTERNAL_DIR / "weather"  # 기상청 ASOS 일자료 (asos_daily_*.csv, cp949)

# 경영비·물가 보정용 외부 자료 (data/external/README_cost_cpi.md 참고)
STANDARD_INCOME = EXTERNAL_DIR / "cost" / "standard_income.csv"  # 감귤 표준소득표 (2017·2022~2024년산)
CPI_ANNUAL = EXTERNAL_DIR / "cpi" / "cpi_annual.csv"  # 연평균 CPI (2020=100)
# KOSIS 농가판매 및 구입가격조사 > 농가구입가격지수 (2020=100, 분기) 원본 다운로드
FARM_PURCHASE_INDEX_RAW = EXTERNAL_DIR / "cpi" / "kosis_farm_purchase_price_quarterly.csv"
