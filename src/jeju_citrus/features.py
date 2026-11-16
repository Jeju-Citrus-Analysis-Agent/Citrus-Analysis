"""분석용 파생 지표(feature) 생성.

- season_weather_features : 산지연도(시즌)별 기상 지표 (4개 지점 평균)
- monthly_weighted_price  : 일별 가격 → 시즌·월별 출하량 가중평균 가격
- deflate                 : 명목 금액 → CPI 기준 실질 금액
- income_per_ha           : 표준소득표(만원/10a) → 백만원/ha 환산·순위
- cost_weights / cost_price_index : 표준소득표 경영비 구성으로 가중한 '경영비 물가지수'
"""

import numpy as np
import pandas as pd

# 시즌 Y의 생육·숙기 구간 (같은 해 Y의 월)
SUMMER_MONTHS = [6, 7, 8, 9]  # 여름 (과실 비대기)
RIPENING_MONTHS = [9, 10, 11]  # 숙기
BLOOM_MONTHS = [4, 5]  # 개화기
WINTER_MONTHS = [12, 1, 2]  # 시즌 직전 겨울: 전년 12월 ~ 당해 2월


def season_weather_features(weather_monthly: pd.DataFrame) -> pd.DataFrame:
    """지점별 월 기상 → 연도(시즌)별 기상 지표. 지점 4곳의 평균을 쓴다.

    반환 컬럼
    - 여름폭염일수, 여름강수_mm, 여름평균기온_c : 6~9월
    - 숙기일조_hr, 숙기강수_mm : 9~11월
    - 개화기평균기온_c : 4~5월
    - 연평균기온_c
    - 겨울영하일수 : 전년 12월 ~ 당해 2월
    - 관측월수 : 해당 연도 관측된 달 수 (12 미만이면 진행 중)
    """
    wm = weather_monthly.copy()
    wm["연월"] = pd.to_datetime(wm["연월"])
    wm["연"] = wm["연월"].dt.year
    wm["월"] = wm["연월"].dt.month
    avg = wm.groupby(["연", "월"]).mean(numeric_only=True).reset_index()

    def by_year(months, col, how):
        return avg[avg["월"].isin(months)].groupby("연")[col].agg(how)

    feat = pd.DataFrame(
        {
            "여름폭염일수": by_year(SUMMER_MONTHS, "폭염일수", "sum"),
            "여름강수_mm": by_year(SUMMER_MONTHS, "강수량_mm", "sum"),
            "여름평균기온_c": by_year(SUMMER_MONTHS, "평균기온_c", "mean"),
            "숙기일조_hr": by_year(RIPENING_MONTHS, "일조시간_hr", "sum"),
            "숙기강수_mm": by_year(RIPENING_MONTHS, "강수량_mm", "sum"),
            "개화기평균기온_c": by_year(BLOOM_MONTHS, "평균기온_c", "mean"),
            "연평균기온_c": by_year(range(1, 13), "평균기온_c", "mean"),
            "관측월수": avg.groupby("연")["월"].nunique(),
        }
    )
    winter = avg[avg["월"].isin(WINTER_MONTHS)].copy()
    winter["시즌"] = np.where(winter["월"] == 12, winter["연"] + 1, winter["연"])
    feat["겨울영하일수"] = winter.groupby("시즌")["영하일수"].sum()
    feat.index.name = "연도"
    return feat.round(2)


def monthly_weighted_price(
    daily: pd.DataFrame,
    price_col: str = "도매_평균가_원_5kg",
    volume_col: str = "도매_출하량_톤",
) -> pd.DataFrame:
    """일별 가격 → 시즌·월별 출하량 가중평균 가격과 총 출하량.

    가격이나 출하량이 비어 있는 날(일요일·휴장일)은 제외한다.
    """
    d = daily.dropna(subset=[price_col, volume_col])
    d = d[d[volume_col] > 0].copy()
    d["월"] = pd.to_datetime(d["일자"]).dt.month
    d["_가중"] = d[price_col] * d[volume_col]
    g = d.groupby(["시즌", "월"]).agg(_가중합=("_가중", "sum"), 출하량_톤=(volume_col, "sum"))
    g["가중평균가"] = g["_가중합"] / g["출하량_톤"]
    return g.drop(columns="_가중합").reset_index()


def deflate(values: pd.Series, years: pd.Series, cpi: pd.DataFrame, base_year: int = 2020) -> pd.Series:
    """명목 금액을 ``base_year`` 물가 기준 실질 금액으로 바꾼다.

    실질 = 명목 ÷ CPI(연도) × CPI(base_year). ``cpi``는 ``연도``, ``CPI_2020_100`` 컬럼을 가진다.
    CPI가 없는 연도는 오류를 낸다 (조용히 NaN이 되지 않도록).
    """
    index = cpi.set_index("연도")["CPI_2020_100"]
    missing = sorted(set(years) - set(index.index))
    if missing:
        raise KeyError(f"CPI가 없는 연도: {missing}")
    factor = index.loc[base_year] / years.map(index)
    return values * factor.to_numpy()


# 1 ha = 10 × 10a, 만원 → 백만원 = ÷100  →  만원/10a × 0.1 = 백만원/ha
MANWON_PER_10A_TO_MILLION_PER_HA = 10 / 100


def income_per_ha(standard_income: pd.DataFrame) -> pd.DataFrame:
    """표준소득표(만원/10a)를 백만원/ha로 바꾸고 경영비 비율과 산지연도별 순위를 붙인다."""
    t = standard_income.copy()
    for col in ["총수입", "경영비", "소득", "생산비", "순수익"]:
        t[f"{col}_백만원_ha"] = t[f"{col}_만원_10a"] * MANWON_PER_10A_TO_MILLION_PER_HA
    t["경영비율_퍼센트"] = t["경영비_만원_10a"] / t["총수입_만원_10a"] * 100
    by_year = t.groupby("산지연도")
    t["총수입_순위"] = by_year["총수입_만원_10a"].rank(ascending=False).astype(int)
    t["소득_순위"] = by_year["소득_만원_10a"].rank(ascending=False).astype(int)
    return t


# 표준소득표 경영비 세부 항목 → 농가구입가격지수 하위 지수
# (농작업위탁비 지수는 2015년부터라 위탁영농비는 '경비'로 대신한다)
COST_ITEM_GROUPS = {
    "비료비": ["보통비료비", "부산물비료비"],
    "농약비": ["농약비"],
    "영농자재비": ["기타재료비", "소농구비"],
    "노무비": ["고용노동비"],
    "영농광열비": ["수도광열비"],
    "임차료": ["농기계시설임차료", "토지임차료"],
    "경비": ["수리유지비", "기타비용", "위탁영농비"],
    "자산구입비": ["대농구상각비", "영농시설상각비", "과수원조성비"],
}


def cost_weights(items: dict[str, float]) -> dict[str, float]:
    """표준소득표 경영비 세부 금액(원/10a) → 농가구입가격지수 하위 지수별 가중치(합 1).

    ``items`` 키는 ``COST_ITEM_GROUPS``의 세부 항목 이름. 빠진 항목은 0으로 본다.
    """
    unknown = set(items) - {i for g in COST_ITEM_GROUPS.values() for i in g}
    if unknown:
        raise KeyError(f"모르는 경영비 항목: {sorted(unknown)}")
    totals = {g: sum(items.get(i, 0) for i in members) for g, members in COST_ITEM_GROUPS.items()}
    whole = sum(totals.values())
    return {g: v / whole for g, v in totals.items()}


def cost_price_index(farm_index: pd.DataFrame, weights: dict[str, float], base_year: int = 2020) -> pd.Series:
    """농가구입가격지수 항목을 ``weights``로 가중평균한 경영비 물가지수 (``base_year`` = 100)."""
    idx = sum(farm_index[g] * w for g, w in weights.items())
    return idx / idx.loc[base_year] * 100
