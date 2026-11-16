import pandas as pd
import pytest

from jeju_citrus.config import STANDARD_INCOME

# 표준소득표는 jasdc 간행물에서 나온 값이라 git에 없음 → scripts/extract_standard_income.py 로 만든 뒤 실행
needs_standard_income = pytest.mark.skipif(
    not STANDARD_INCOME.exists(), reason="data/external/cost/standard_income.csv 없음 (git 제외 데이터)"
)

from jeju_citrus.features import monthly_weighted_price, season_weather_features


def _weather_monthly():
    rows = []
    for station in ["제주", "서귀포"]:
        for ym in ["2024-12-01", "2025-01-01", "2025-07-01", "2025-08-01"]:
            rows.append(
                {
                    "지점명": station,
                    "연월": ym,
                    "폭염일수": 4 if station == "제주" else 2,
                    "영하일수": 1,
                    "강수량_mm": 100.0,
                    "평균기온_c": 20.0,
                    "일조시간_hr": 150.0,
                }
            )
    return pd.DataFrame(rows)


def test_season_weather_features():
    f = season_weather_features(_weather_monthly())
    # 7·8월 각각 지점 평균 3일 → 합 6일
    assert f.loc[2025, "여름폭염일수"] == 6
    # 2025 시즌 겨울 = 2024-12 + 2025-01 → 2일
    assert f.loc[2025, "겨울영하일수"] == 2
    assert f.loc[2025, "여름강수_mm"] == 200


def test_monthly_weighted_price():
    daily = pd.DataFrame(
        {
            "시즌": [2024, 2024, 2024],
            "일자": ["2024-12-01", "2024-12-02", "2024-12-03"],
            "도매_평균가_원_5kg": [10000, 20000, None],  # 휴장일 제외
            "도매_출하량_톤": [300.0, 100.0, 50.0],
        }
    )
    m = monthly_weighted_price(daily)
    row = m[(m["시즌"] == 2024) & (m["월"] == 12)].iloc[0]
    assert row["가중평균가"] == 12500  # (10000*300 + 20000*100) / 400
    assert row["출하량_톤"] == 400


def test_deflate_to_base_year():
    from jeju_citrus.features import deflate

    cpi = pd.DataFrame({"연도": [2004, 2020, 2025], "CPI_2020_100": [72.418, 100.0, 116.61]})
    real = deflate(pd.Series([833.0, 1701.0]), pd.Series([2004, 2025]), cpi)
    # 보고서: 2004→2025 실질 단가 +26.8%
    assert round((real.iloc[1] / real.iloc[0] - 1) * 100, 1) == 26.8


def test_deflate_missing_year_raises():
    import pytest

    from jeju_citrus.features import deflate

    cpi = pd.DataFrame({"연도": [2020], "CPI_2020_100": [100.0]})
    with pytest.raises(KeyError):
        deflate(pd.Series([1.0]), pd.Series([1999]), cpi)


@needs_standard_income
def test_income_per_ha_units_and_rank():
    from jeju_citrus.data import load_standard_income
    from jeju_citrus.features import income_per_ha

    t = income_per_ha(load_standard_income(2024)).set_index("대응품종")
    assert abs(t.loc["노지온주", "총수입_백만원_ha"] - 45.36) < 1e-9
    # 소득 = 총수입 − 경영비 (원문 값이 이 관계를 지키는지)
    assert ((t["총수입_만원_10a"] - t["경영비_만원_10a"] - t["소득_만원_10a"]).abs() < 0.11).all()
    assert t["소득_순위"].idxmin() == "천혜향"
    assert t["총수입_순위"].idxmin() == "하우스온주"


@needs_standard_income
def test_standard_income_years_and_net_profit():
    from jeju_citrus.data import load_standard_income

    d = load_standard_income()
    assert sorted(d["산지연도"].unique()) == list(range(2016, 2025))
    assert d.groupby("산지연도").size().sum() == 53
    # 2024년산: 중간 보고서의 생산비 차감 순수익과 일치
    net = load_standard_income(2024).set_index("대응품종")["순수익_만원_10a"]
    assert net["노지온주"] == 64.2 and net["천혜향"] == 1090.4 and net["하우스온주"] == 793.4


def test_farm_purchase_index_annual_matches_published():
    from jeju_citrus.data import load_farm_purchase_index

    a = load_farm_purchase_index()
    assert a.index.min() == 2005 and 2026 not in a.index  # 2026은 3개 분기뿐
    assert round(a.loc[2025, "총지수"], 1) == 121.6  # 공표 연평균
    assert abs(a.loc[2024, "총지수"] - 120.1) < 0.2  # 공표 120.1 (계절 가중치 차이)
    assert round(a.loc[2020, "노무비"], 1) == 100.0


def test_cost_weights_and_index():
    import pytest

    from jeju_citrus.features import COST_ITEM_GROUPS, cost_price_index, cost_weights

    w = cost_weights({"농약비": 3, "고용노동비": 1})
    assert w["농약비"] == 0.75 and w["노무비"] == 0.25 and sum(w.values()) == 1
    idx = pd.DataFrame({g: [100.0, 100.0] for g in COST_ITEM_GROUPS}, index=[2020, 2021])
    idx.loc[2021, "농약비"], idx.loc[2021, "노무비"] = 120.0, 140.0
    assert cost_price_index(idx, w).loc[2021] == pytest.approx(125.0)
    with pytest.raises(KeyError):
        cost_weights({"없는항목": 1})


@needs_standard_income
def test_standard_income_items_sum_to_cost():
    from jeju_citrus.data import load_standard_income_items
    from jeju_citrus.features import COST_ITEM_GROUPS

    d = load_standard_income_items()
    items = [i for g in COST_ITEM_GROUPS.values() for i in g]
    gap = (d[items].sum(axis=1) - d["경영비_원_10a"]).abs()
    # 2022년산 황금향만 원문 표 안에서 541원 어긋남
    assert (gap <= 2).sum() == len(d) - 1 and gap.max() == 541
