"""분석용 파생 지표(feature) 생성.

- season_weather_features : 산지연도(시즌)별 기상 지표 (4개 지점 평균)
- monthly_weighted_price  : 일별 가격 → 시즌·월별 출하량 가중평균 가격
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
