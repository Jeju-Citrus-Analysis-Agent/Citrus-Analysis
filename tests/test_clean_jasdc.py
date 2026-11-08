import pandas as pd
import pytest

from jeju_citrus.config import JASDC_RAW_DIR
from jeju_citrus.data.clean_jasdc import (
    build_production,
    clean_production,
    fix_thousands_typo,
    parse_short_year,
    to_number,
)

needs_raw = pytest.mark.skipif(
    not (JASDC_RAW_DIR / "manifest.json").exists(),
    reason="jasdc 원본 없음 (python scripts/collect_jasdc.py 먼저 실행)",
)


def test_to_number():
    s = pd.Series(["1,463.0", "-", "", "37,205"])
    result = to_number(s)
    assert result[0] == 1463.0
    assert result[1:3].isna().all()
    assert result[3] == 37205


def test_fix_thousands_typo_only_touches_typo_pattern():
    s = pd.Series(["6.375", "3,657", "1463.0", "12.5"])
    assert fix_thousands_typo(s).tolist() == ["6,375", "3,657", "1463.0", "12.5"]


def test_parse_short_year():
    assert parse_short_year(pd.Series(["'25", "'03"])).tolist() == [2025, 2003]


def test_clean_production_converts_eok_to_million():
    raw = pd.DataFrame(
        {
            "연도별": ["2025"],
            "재배면적(ha)": ["1,463.0"],
            "생산량(톤)": ["37,205"],
            "조수입(억원)": ["1,361"],
            "재배농가(호)": ["3,275"],
            "kg당 가격(원)": ["3,657"],
        }
    )
    df = clean_production("한라봉", raw)
    assert df.loc[0, "조수입_백만원"] == 136_100
    assert df.loc[0, "품종그룹"] == "만감류"


@needs_raw
def test_build_production_has_all_varieties():
    df = build_production()
    assert df["품종"].nunique() == 8
    assert not df.duplicated(["품종", "연도"]).any()
    assert df[["재배면적_ha", "생산량_톤", "조수입_백만원", "단가_원_kg"]].notna().all().all()
