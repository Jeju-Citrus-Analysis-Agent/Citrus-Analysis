# ruff: noqa: E501  (붙여넣기 원문 형식을 그대로 재현한 테스트 데이터)
import pandas as pd
import pytest

from jeju_citrus.data.clean_jasdc_manual import parse_price_monthly_box, parse_price_whole

DAILY_TEXT = """노지온주
일자    합계    도매시장    직거래(대형마트 등)
출하량    평균가    출하량    평균가    출하량    평균가
2024-10-17    942.8    최저 7,200    816.1    7,200    126.7    -
2024-11-04    1,653.6    10,600    1,338.3    9,800    315.3    14,000
2025-02-29    -    -    -    -    -    -
"""

BOX_TEXT = """거래월    노지온주(5kg 상자) 총계    노지온주(0.5Kg상자)    노지온주(10Kg상자)
거래량    최고가    최저가    평균가    거래량    최고가    최저가    평균가    거래량    최고가    최저가    평균가
합계    100.0    9,000    3,000    5,000    1.0    2,000    1,000    1,500    9.0    20,000    9,000    15,000
12월    60.0    9,000    3,000    5,500    -    -    -    -    9.0    20,000    9,000    15,000
01월    40.0    8,000    3,000    4,000    1.0    2,000    1,000    1,500    -    -    -    -
"""


@pytest.fixture
def daily_file(tmp_path):
    p = tmp_path / "price_whole_노지온주_2024.txt"
    p.write_text(DAILY_TEXT, encoding="utf-8")
    return p


@pytest.fixture
def box_file(tmp_path):
    p = tmp_path / "price_monthly_box_노지온주_2024.txt"
    p.write_text(BOX_TEXT, encoding="utf-8")
    return p


def test_parse_price_whole(daily_file):
    df = parse_price_whole(daily_file)
    assert len(df) == 2  # 2025-02-29(없는 날짜) 제거
    first = df.iloc[0]
    assert first["합계_평균가_원_5kg"] == 7200
    assert first["시즌_최저최고"] == "최저"
    assert pd.isna(first["직거래_평균가_원_5kg"])
    assert df.iloc[1]["합계_출하량_톤"] == 1653.6
    assert (df["품종"] == "노지온주").all() and (df["시즌"] == 2024).all()


def test_parse_price_monthly_box(box_file):
    df = parse_price_monthly_box(box_file)
    assert "합계" not in df["거래월"].astype(str).tolist()
    # 12월은 시즌 시작 연도, 1월은 다음 해
    assert set(df["거래월"].dt.year) == {2024, 2025}
    # 거래 없는 월·규격 제거: 12월 0.5kg, 1월 10kg
    assert len(df) == 4
    total_jan = df[(df["상자규격"] == "총계(5kg환산)") & (df["거래월"].dt.month == 1)]
    assert total_jan["평균가_원"].item() == 4000


def test_bad_file_name(tmp_path):
    p = tmp_path / "whatever.txt"
    p.write_text(DAILY_TEXT, encoding="utf-8")
    with pytest.raises(ValueError):
        parse_price_whole(p)


def _write_xlsx(path, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["총괄가격"])
    ws.append([])
    ws.append(["일자", "합계", None, "도매시장", None, "직거래(대형마트 등)", None])
    ws.append([None, "출하량", "평균가", "출하량", "평균가", "출하량", "평균가"])
    for r in rows:
        ws.append(r)
    ws.append(["제주농산물수급관리센터 (064-749-2015)"])
    wb.save(path)


def test_parse_price_whole_xlsx(tmp_path):
    p = tmp_path / "price_whole_노지온주_20250901-20251001.xlsx"
    _write_xlsx(
        p,
        [
            ["2025-09-30", "137.6", " \n\n\t\t최저 10,000\n\t", "120.5", "10,000", "17.1", "-"],
            ["2025-10-01", "115.4", " \n\t9,800\n", "100.1", "9,800", "15.3", "-"],
        ],
    )
    df = parse_price_whole(p)
    assert df["합계_평균가_원_5kg"].tolist() == [10000, 9800]
    assert df.loc[0, "시즌_최저최고"] == "최저"
    assert df["시즌"].tolist() == [2025, 2025]  # 9월부터 새 시즌


def test_season_of():
    from jeju_citrus.data.clean_jasdc_manual import season_of

    dates = pd.Series(pd.to_datetime(["2025-08-31", "2025-09-01", "2026-02-01"]))
    assert season_of(dates).tolist() == [2024, 2025, 2025]


def test_build_daily_dedupes_with_xlsx_priority(tmp_path):
    from jeju_citrus.data.clean_jasdc_manual import DAILY_SUBDIR, build_daily

    daily_dir = tmp_path / DAILY_SUBDIR
    daily_dir.mkdir()
    _write_xlsx(
        daily_dir / "price_whole_노지온주_20241001-20241002.xlsx",
        [["2024-10-17", "1.0", "999", "1.0", "999", "-", "-"]],
    )
    (daily_dir / "price_whole_노지온주_2024.txt").write_text(DAILY_TEXT, encoding="utf-8")
    df = build_daily(tmp_path)
    assert df["일자"].is_unique
    assert df.loc[df["일자"] == "2024-10-17", "합계_평균가_원_5kg"].item() == 999  # 엑셀 우선
