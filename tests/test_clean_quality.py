import pandas as pd
import pytest

from jeju_citrus.config import RAW_DISTRIBUTION_XLSX, RAW_FRUIT_PRODUCTION
from jeju_citrus.data import load_raw
from jeju_citrus.data.clean_jasdc import add_price_basis
from jeju_citrus.data.clean_quality import (
    clean_fruit_production,
    clean_special_crops,
    fix_varieties_growth,
    validate_fruit_hierarchy,
)
from jeju_citrus.data.extract_distribution import SHEET_TO_DATASET, extract_distribution


# ------------------------------------------------------------------ Q3
def test_fix_varieties_growth_converts_ratio_to_change():
    df = pd.DataFrame(
        {
            "처리량_2025_톤": [27280.0],
            "조수입_2025_백만원": [98804],
            "처리량_2024_톤": [27036.0],
            "조수입_2024_백만원": [92725],
            "처리량_증감률_퍼센트": [101],
            "조수입_증감률_퍼센트": [107],
        }
    )
    out = fix_varieties_growth(df)
    assert out["처리량_전년비_퍼센트"].iloc[0] == 101  # 원본 값은 이름만 바뀜
    assert out["처리량_증감률_퍼센트"].iloc[0] == pytest.approx(0.9)
    assert out["조수입_증감률_퍼센트"].iloc[0] == pytest.approx(6.6)


# ------------------------------------------------------------------ Q4
def _fruit(rows):
    return pd.DataFrame(
        rows, columns=["기준연도", "품종대분류", "품종소분류", "생산면적(ha)", "생산량(톤)"]
    )


def test_clean_fruit_production_fixes_swapped_categories():
    raw = _fruit(
        [
            [2015, "만감류", "기타", 72, 1902],
            [2016, "기타", "레드향", 167, 6460],
            [2016, "만감류", "단감", 65, 379],
        ]
    )
    out = clean_fruit_production(raw).set_index(["연도", "품종"])
    assert out.loc[(2015, "만감류기타"), "대분류"] == "만감류"
    assert out.loc[(2016, "레드향"), "대분류"] == "만감류"
    assert out.loc[(2016, "단감"), "대분류"] == "기타"
    assert out["대분류_보정"].sum() == 2


def test_clean_fruit_production_rejects_unknown_variety():
    with pytest.raises(ValueError, match="없는 품종"):
        clean_fruit_production(_fruit([[2015, "기타", "아보카도", 1, 1]]))


def test_fruit_hierarchy_matches_on_real_data():
    if not RAW_FRUIT_PRODUCTION.exists():
        pytest.skip("fruit_production.csv 없음")
    check = validate_fruit_hierarchy(clean_fruit_production(load_raw(RAW_FRUIT_PRODUCTION.name)))
    assert check["통과"].all()


# ------------------------------------------------------------------ Q5
def _crops(rows):
    cols = ["기준 연도", "시도", "품명", "농가수[호]", "재배면적[ha]", "수확면적[ha]",
            "단수[kg/10a]", "생산량[M/T]"]  # fmt: skip
    return pd.DataFrame([[r[0], "제주특별자치도", *r[1:]] for r in rows], columns=cols)


def test_clean_special_crops():
    raw = _crops(
        [
            [2017, "기타", 0, 0, 0, 0.0, 0.0],  # 미재배 + 중복
            [2017, "기타", 0, 0, 0, 0.0, 0.0],
            [2023, "유지작물", 1855, 438, 434, None, 266.0],  # 소계
            [2023, "유채", 246, 94, 90, 146.0, 132.0],  # 정상
            [2023, "들깨", 0, 6, 6, 0.0, 7.0],  # 단수 0인데 생산량 있음
            [2010, "기타", 5, 2, 2, 21008.0, 446.0],  # 소면적
            [2010, "기타", 331, 162, 161, 806.0, 1294.0],
            [2014, "느타리", 10, 5, 5, 1.0, 49.0],  # 버섯
        ]
    )
    out = clean_special_crops(raw).set_index(["연도", "품명"])
    assert len(out) == 5
    assert "유지작물" not in out.index.get_level_values("품명")
    assert out.loc[(2023, "유채"), "단수_계산_kg_10a"] == pytest.approx(146.7)
    assert pd.isna(out.loc[(2023, "유채"), "단수_이상"])
    assert pd.isna(out.loc[(2023, "들깨"), "단수_kg_10a"])
    assert out.loc[(2010, "기타_1"), "단수_이상"] == "소면적"
    assert pd.isna(out.loc[(2010, "기타_2"), "단수_이상"])
    assert out.loc[(2014, "느타리"), "단수_이상"] == "버섯(단위 다름)"


# ------------------------------------------------------------------ Q8·Q9
def test_add_price_basis():
    df = pd.DataFrame(
        {
            "생산량_톤": [27036, 28145, 2465, 17996],
            "조수입_백만원": [92725, 112267, 6300, 86700],
            "단가_원_kg": [3430, 4432, 6375, 4181],
        }
    )
    out = add_price_basis(df)
    assert out["단가_검증"].tolist() == ["일치", "처리량기준", "확인불가", "확인불가"]
    assert out["처리량_추정_톤"].iloc[1] == 25331  # 유통처리 엑셀의 2024 월동온주 처리량


# ------------------------------------------------------------------ FR-104
@pytest.mark.skipif(not RAW_DISTRIBUTION_XLSX.exists(), reason="distribution_analysis.xlsx 없음")
def test_extract_distribution_reproduces_processed():
    from jeju_citrus.data import load_processed

    tables = extract_distribution()
    assert set(tables) == set(SHEET_TO_DATASET.values())
    for name, df in tables.items():
        pd.testing.assert_frame_equal(df, load_processed(name), check_dtype=False)
