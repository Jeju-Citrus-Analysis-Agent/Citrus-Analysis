"""제주농산물수급관리센터 감귤 통계 수집 → 정제.

1) 정적 표 자동 수집 → data/raw/jasdc/            (collect_jasdc)
2) 자동 수집 원본 정제 → data/processed/citrus_*   (clean_jasdc)
3) 수동 복사·다운로드 정제 → data/processed/citrus_price_* (clean_jasdc_manual)

실행: python scripts/collect_jasdc.py [--skip-download]
"""

import sys

from jeju_citrus.data import clean_jasdc, clean_jasdc_manual, collect_jasdc

if __name__ == "__main__":
    if "--skip-download" not in sys.argv:
        collect_jasdc.main()
    clean_jasdc.main()
    clean_jasdc_manual.main()
