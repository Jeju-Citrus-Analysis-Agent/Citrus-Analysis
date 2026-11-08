import pandas as pd

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
