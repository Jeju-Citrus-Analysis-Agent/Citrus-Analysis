"""데이터 품질 이슈(요구사항 정의서 §4) 중 '원천 확인' 항목의 근거 표를 만드는 함수.

모든 함수는 processed 데이터만 받아서 비교표(DataFrame)를 돌려준다. 실행 결과는
``python scripts/check_quality.py``로 한 번에 볼 수 있다.
"""

import pandas as pd

from jeju_citrus.data.preprocess import drop_total_rows, parse_crop_year


def _weighted_price(df: pd.DataFrame, price: str, volume: str) -> float:
    """가격이 있는 날만 골라 출하량 가중평균 가격을 구한다."""
    has_price = df[price].notna()
    total = df.loc[has_price, volume].sum()
    if total == 0:  # 출하가 없는 달
        return float("nan")
    return (df.loc[has_price, price] * df.loc[has_price, volume]).sum() / total


def shipment_coverage(daily: pd.DataFrame, yearly: pd.DataFrame) -> pd.DataFrame:
    """[Q7] 시즌별 일별 출하량 합계(도매+직거래)가 연간 처리량의 몇 %인지 계산한다.

    ``daily``: citrus_price_daily, ``yearly``: noji_yearly
    """
    season = daily.groupby("시즌").agg(
        시작일=("일자", "min"),
        종료일=("일자", "max"),
        출하량_합계_톤=("합계_출하량_톤", "sum"),
        도매_출하량_톤=("도매_출하량_톤", "sum"),
        직거래_출하량_톤=("직거래_출하량_톤", "sum"),
    )
    vol = yearly.assign(시즌=parse_crop_year(yearly["연도"])).set_index("시즌")["처리량_톤"]
    out = season.join(vol, how="inner")
    out["출하비율"] = (out["출하량_합계_톤"] / out["처리량_톤"]).round(3)
    return out.reset_index()


def monthly_table_vs_daily(monthly: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """[Q7] 월별 표(noji_monthly_2025)의 합계와 같은 시즌 일별 출하량 합계를 비교한다."""
    total = monthly.loc[monthly["월구분"] == "계", "출하량_톤"].iloc[0]
    season = int(parse_crop_year(monthly["산지연도"]).iloc[0])
    body = drop_total_rows(monthly, "월구분")
    d = daily[daily["시즌"] == season]
    return pd.DataFrame(
        {
            "항목": ["월별 표 합계", "일별 합계(도매+직거래)", "일별 도매시장만"],
            "출하량_톤": [
                body["출하량_톤"].sum(),
                d["합계_출하량_톤"].sum(),
                d["도매_출하량_톤"].sum(),
            ],
        }
    ).assign(월별표_대비=lambda x: (x["출하량_톤"] / total).round(4))


def monthly_box_vs_daily(box: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """[Q11] 월별 상자규격 표(총계)와 일별 도매시장 출하를 월 단위로 비교한다.

    가격 비율이 1에 가까우면 같은 경락가격에서 나온 표이고, 물량 비율은 월별 표가
    전체 도매시장 출하 중 얼마를 담고 있는지(집계 대상 시장 범위)를 보여준다.
    """
    b = box[box["상자규격"].str.startswith("총계")].copy()
    b["월"] = pd.to_datetime(b["거래월"]).dt.to_period("M")
    d = daily.copy()
    d["월"] = pd.to_datetime(d["일자"]).dt.to_period("M")
    rows = []
    for (season, month), g in d.groupby(["시즌", "월"]):
        rows.append(
            {
                "시즌": season,
                "월": month,
                "일별_도매_출하량_톤": g["도매_출하량_톤"].sum(),
                "일별_도매_가중평균가_원_5kg": _weighted_price(
                    g, "도매_평균가_원_5kg", "도매_출하량_톤"
                ),
            }
        )
    out = b[["시즌", "월", "거래량_톤", "평균가_원"]].merge(pd.DataFrame(rows), on=["시즌", "월"])
    out["물량비율"] = (out["거래량_톤"] / out["일별_도매_출하량_톤"]).round(3)
    out["가격비율"] = (out["평균가_원"] / out["일별_도매_가중평균가_원_5kg"]).round(3)
    return out


def market_coverage(market: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """[Q11] 9대 도매시장 거래량 합계가 같은 시즌 일별 도매 출하량의 몇 %인지 계산한다."""
    season = int(parse_crop_year(market["산지연도"]).iloc[0])
    d = daily[daily["시즌"] == season]
    return pd.DataFrame(
        {
            "시즌": [season],
            "9대시장_거래량_톤": [market["거래량_톤"].sum()],
            "일별_도매_출하량_톤": [d["도매_출하량_톤"].sum()],
            "9대시장_가중평균가": [_weighted_price(market, "평균가_원_5kg", "거래량_톤")],
            "일별_도매_가중평균가": [_weighted_price(d, "도매_평균가_원_5kg", "도매_출하량_톤")],
        }
    ).assign(
        물량비율=lambda x: (x["9대시장_거래량_톤"] / x["일별_도매_출하량_톤"]).round(3),
        가격비율=lambda x: (x["9대시장_가중평균가"] / x["일별_도매_가중평균가"]).round(3),
    )


def structural_break(production: pd.DataFrame, year: int = 2017) -> pd.DataFrame:
    """[Q9] ``year - 1`` → ``year`` 품종별 재배면적·생산량·농가수 변화율.

    재배면적·농가수만 크게 바뀌고 생산량은 그대로라면 실제 변화가 아니라
    통계 기준(재조사·품종 재분류)이 바뀐 것으로 본다.
    """
    cols = ["재배면적_ha", "생산량_톤", "재배농가_호"]
    p = production[production["연도"].isin([year - 1, year])]
    wide = p.pivot(index="품종", columns="연도", values=cols)
    out = pd.DataFrame(index=wide.index)
    for c in cols:
        out[f"{c}_{year - 1}"] = wide[(c, year - 1)]
        out[f"{c}_{year}"] = wide[(c, year)]
        out[f"{c}_변화율"] = (wide[(c, year)] / wide[(c, year - 1)] - 1).round(3)
    return out.dropna().reset_index()
