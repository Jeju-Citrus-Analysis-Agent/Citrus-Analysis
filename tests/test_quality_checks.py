import pandas as pd

from jeju_citrus.data.quality_checks import (
    monthly_box_vs_daily,
    shipment_coverage,
    structural_break,
)


def _daily():
    return pd.DataFrame(
        {
            "시즌": [2025, 2025, 2025],
            "일자": ["2025-10-01", "2025-10-02", "2025-11-01"],
            "합계_출하량_톤": [120.0, 80.0, 100.0],
            "도매_출하량_톤": [100.0, 60.0, 80.0],
            "직거래_출하량_톤": [20.0, 20.0, 20.0],
            "도매_평균가_원_5kg": [10000.0, None, 12000.0],  # 가격 없는 날은 가중평균에서 제외
        }
    )


def test_shipment_coverage():
    yearly = pd.DataFrame({"연도": ["2025년산"], "처리량_톤": [600]})
    out = shipment_coverage(_daily(), yearly)
    assert out["출하량_합계_톤"].iloc[0] == 300
    assert out["출하비율"].iloc[0] == 0.5


def test_monthly_box_vs_daily():
    box = pd.DataFrame(
        {
            "시즌": [2025, 2025],
            "거래월": ["2025-10-01", "2025-10-01"],
            "상자규격": ["총계(5kg환산)", "5kg"],
            "거래량_톤": [80.0, 70.0],
            "평균가_원": [10000.0, 9900.0],
        }
    )
    out = monthly_box_vs_daily(box, _daily())
    assert len(out) == 1
    assert out["물량비율"].iloc[0] == 0.5  # 80 / (100+60)
    assert out["가격비율"].iloc[0] == 1.0  # 가격 있는 날(10/1)만 가중평균


def test_structural_break():
    prod = pd.DataFrame(
        {
            "품종": ["황금향", "황금향"],
            "연도": [2016, 2017],
            "재배면적_ha": [100.0, 350.0],
            "생산량_톤": [3600.0, 3600.0],
            "재배농가_호": [300, 800],
        }
    )
    out = structural_break(prod, 2017)
    assert out["재배면적_ha_변화율"].iloc[0] == 2.5
    assert out["생산량_톤_변화율"].iloc[0] == 0.0
