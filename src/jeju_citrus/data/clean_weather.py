"""기상청 ASOS 일자료(data/external/weather/asos_daily_*.csv) → 분석용 기상 데이터.

입력: 기상자료개방포털 > 지상 > 종관기상관측(ASOS) > 일자료 CSV (cp949)
      10년 단위로 나눠 받은 파일들

생성 파일
- weather_daily.csv   : 지점별 일별 기온·강수·습도·일조·일사
- weather_monthly.csv : 지점별 월별 요약 + 극한기상 일수(폭염·열대야·영하·호우)

처리 규칙
- 현재 운영 중인 4개 지점(제주·고산·성산·서귀포)만 사용. 옛 지점(187 성산, 265 성산포)은 제외
- 파일 간 겹치는 기간은 중복 제거(값 동일 확인됨)
- 일강수량 빈칸 = 강수 없음 → 0 (기상청 표기 규칙)
- 일사량은 제주·고산 지점에만 관측값이 있음
"""

from pathlib import Path

import pandas as pd

from jeju_citrus.config import DEFAULT_ENCODING, PROCESSED_DIR, WEATHER_DIR

STATIONS = {184: "제주", 185: "고산", 188: "성산", 189: "서귀포"}
RAW_ENCODING = "cp949"

COLUMN_MAP = {
    "지점": "지점코드",
    "지점명": "지점명",
    "일시": "일자",
    "평균기온(°C)": "평균기온_c",
    "최저기온(°C)": "최저기온_c",
    "최고기온(°C)": "최고기온_c",
    "일강수량(mm)": "강수량_mm",
    "평균 상대습도(%)": "상대습도_퍼센트",
    "합계 일조시간(hr)": "일조시간_hr",
    "합계 일사량(MJ/m2)": "일사량_mj_m2",
}

# 극한기상 기준 (기상청 정의)
HEATWAVE_C = 33.0  # 폭염일: 일 최고기온 33℃ 이상
TROPICAL_NIGHT_C = 25.0  # 열대야(근사): 일 최저기온 25℃ 이상
FREEZING_C = 0.0  # 영하일: 일 최저기온 0℃ 미만
HEAVY_RAIN_MM = 80.0  # 호우(근사): 일강수량 80mm 이상


def load_daily(weather_dir: Path = WEATHER_DIR) -> pd.DataFrame:
    files = sorted(weather_dir.glob("asos_daily_*.csv"))
    if not files:
        raise FileNotFoundError(f"기상 원본 없음: {weather_dir}/asos_daily_*.csv")
    raw = pd.concat([pd.read_csv(f, encoding=RAW_ENCODING) for f in files], ignore_index=True)

    df = raw[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    df = df[df["지점코드"].isin(STATIONS)]
    df["지점명"] = df["지점코드"].map(STATIONS)  # 지점명 표기 통일
    df["일자"] = pd.to_datetime(df["일자"], format="%Y-%m-%d")
    df = df.drop_duplicates(subset=["지점코드", "일자"]).sort_values(["지점코드", "일자"])
    df["강수량_mm"] = df["강수량_mm"].fillna(0.0)
    return df.reset_index(drop=True)


def to_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.assign(
        연월=daily["일자"].dt.to_period("M").dt.to_timestamp(),
        폭염일수=daily["최고기온_c"] >= HEATWAVE_C,
        열대야일수=daily["최저기온_c"] >= TROPICAL_NIGHT_C,
        영하일수=daily["최저기온_c"] < FREEZING_C,
        호우일수=daily["강수량_mm"] >= HEAVY_RAIN_MM,
        강수일수=daily["강수량_mm"] > 0,
    )
    monthly = (
        d.groupby(["지점코드", "지점명", "연월"])
        .agg(
            관측일수=("일자", "count"),
            평균기온_c=("평균기온_c", "mean"),
            평균최고기온_c=("최고기온_c", "mean"),
            평균최저기온_c=("최저기온_c", "mean"),
            극값최고기온_c=("최고기온_c", "max"),
            극값최저기온_c=("최저기온_c", "min"),
            강수량_mm=("강수량_mm", "sum"),
            일조시간_hr=("일조시간_hr", "sum"),
            일사량_mj_m2=("일사량_mj_m2", lambda s: s.sum(min_count=1)),
            평균상대습도_퍼센트=("상대습도_퍼센트", "mean"),
            폭염일수=("폭염일수", "sum"),
            열대야일수=("열대야일수", "sum"),
            영하일수=("영하일수", "sum"),
            호우일수=("호우일수", "sum"),
            강수일수=("강수일수", "sum"),
        )
        .reset_index()
    )
    return monthly.round(2)


def main() -> None:
    daily = load_daily()
    monthly = to_monthly(daily)
    for name, df in {"weather_daily": daily, "weather_monthly": monthly}.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False, encoding=DEFAULT_ENCODING)
        print(f"[저장] processed/{name}.csv ({len(df)}행)")
    span = f"{daily['일자'].min().date()} ~ {daily['일자'].max().date()}"
    print(f"  기간 {span}, 지점 {daily['지점명'].nunique()}곳")


if __name__ == "__main__":
    main()
