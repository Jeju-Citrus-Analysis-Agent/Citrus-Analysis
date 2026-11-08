import pandas as pd

from jeju_citrus.data.clean_weather import load_daily, to_monthly

HEADER = (
    "지점,지점명,일시,평균기온(°C),최저기온(°C),최고기온(°C),일강수량(mm),평균 상대습도(%),"
    "가조시간(hr),합계 일조시간(hr),1시간 최다일사 시각(hhmi),1시간 최다일사량(MJ/m2),"
    "합계 일사량(MJ/m2)"
)
ROWS_A = [
    "184,제주,2013-08-01,29.0,26.0,34.0,,80,14,10,1200,3.0,25.0",
    "184,제주,2013-08-02,28.0,24.0,31.0,90.5,85,14,2,1200,1.0,10.0",
    "187,성산,2013-08-01,27.0,23.0,30.0,,80,14,9,,,",  # 옛 지점 → 제외
]
ROWS_B = [
    "184,제주,2013-08-02,28.0,24.0,31.0,90.5,85,14,2,1200,1.0,10.0",  # 겹치는 날 → 중복 제거
    "189,서귀포,2013-08-01,28.5,25.5,33.0,0,82,14,8,,,",
]


def _write(tmp_path):
    for name, rows in {"asos_daily_a.csv": ROWS_A, "asos_daily_b.csv": ROWS_B}.items():
        (tmp_path / name).write_text("\n".join([HEADER, *rows]) + "\n", encoding="cp949")
    return tmp_path


def test_load_daily(tmp_path):
    df = load_daily(_write(tmp_path))
    assert set(df["지점명"]) == {"제주", "서귀포"}
    assert len(df) == 3
    jeju_0801 = df[(df["지점명"] == "제주") & (df["일자"] == pd.Timestamp("2013-08-01"))]
    assert jeju_0801["강수량_mm"].item() == 0.0  # 빈칸 → 0


def test_to_monthly_extreme_days(tmp_path):
    m = to_monthly(load_daily(_write(tmp_path)))
    jeju = m[m["지점명"] == "제주"].iloc[0]
    assert jeju["폭염일수"] == 1  # 34℃
    assert jeju["열대야일수"] == 1  # 최저 26℃
    assert jeju["호우일수"] == 1  # 90.5mm
    assert jeju["강수량_mm"] == 90.5
    seogwipo = m[m["지점명"] == "서귀포"].iloc[0]
    assert seogwipo["폭염일수"] == 1  # 33.0℃ (경계값 포함)
    assert pd.isna(seogwipo["일사량_mj_m2"])  # 일사 미관측 지점
