"""jasdc 화면에서 수동으로 받은 표(data/raw/jasdc_manual/) → 분석용 데이터.

입력 파일 이름 규칙
- price_daily/price_whole_{품종}_{시작}-{끝}.xlsx : 총괄가격(도매시장/직거래) 일별, 엑셀 다운로드
- price_daily/price_whole_{품종}_{시즌}.txt       : 같은 표를 복사-붙여넣기 (시즌 = 시작 연도)
- price_monthly_box/price_monthly_box_{품종}_{시즌}.txt : 단위별(월별)가격, 상자 규격별

생성 파일
- citrus_price_daily.csv          : 일별 출하량·평균가 (합계/도매시장/직거래)
- citrus_price_monthly_box.csv    : 월별·상자규격별 거래량·최고/최저/평균가 (long 형식)

규칙
- 시즌(산지연도)은 날짜로 정한다: 9월~12월 → 그해, 1월~8월 → 전년도 (예: 2025-02 → 2024 시즌)
- 같은 날짜가 여러 파일에 있으면 엑셀 > 텍스트 순으로 하나만 남긴다(파일 경계 날짜가 겹침)
- 텍스트 표의 칸 구분은 탭 또는 공백 2칸 이상('최저 7,200'처럼 셀 안 공백 1칸은 유지)
"""

import re
from pathlib import Path

import openpyxl
import pandas as pd

from jeju_citrus.config import DEFAULT_ENCODING, JASDC_MANUAL_DIR, PROCESSED_DIR
from jeju_citrus.data.clean_jasdc import to_number

DAILY_SUBDIR = "price_daily"  # jasdc_manual/ 아래 일별 파일 폴더
MONTHLY_BOX_SUBDIR = "price_monthly_box"  # 월별 상자규격 파일 폴더

CELL_SEP = re.compile(r"\t+|\s{2,}")
DATE_ROW = re.compile(r"^\d{4}-\d{2}-\d{2}\s")
DATE_CELL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_ROW = re.compile(r"^\d{2}월\s")
FILE_NAME = re.compile(
    r"^price_(?:whole|monthly_box)_(?P<variety>.+?)_(?P<period>\d{4}|\d{8}-\d{8})\.(?:txt|xlsx)$"
)
SEASON_START_MONTH = 9

DAILY_COLUMNS = [
    "합계_출하량_톤",
    "합계_평균가_원_5kg",
    "도매_출하량_톤",
    "도매_평균가_원_5kg",
    "직거래_출하량_톤",
    "직거래_평균가_원_5kg",
]
BOX_METRICS = ["거래량_톤", "최고가_원", "최저가_원", "평균가_원"]


def _split(line: str) -> list[str]:
    return CELL_SEP.split(line.strip())


def _meta_from_name(path: Path) -> tuple[str, int]:
    """파일 이름에서 (품종, 시작 연도)를 읽는다."""
    m = FILE_NAME.match(path.name)
    if not m:
        raise ValueError(f"파일 이름 규칙 위반: {path.name}")
    return m["variety"], int(m["period"][:4])


def season_of(dates: pd.Series) -> pd.Series:
    """날짜 → 시즌(산지연도). 9~12월은 그해, 1~8월은 전년도."""
    return (dates.dt.year - (dates.dt.month < SEASON_START_MONTH)).astype(int)


# ------------------------------------------------------------------ 일별 총괄가격
def _daily_frame(rows: list[list[str]], variety: str) -> pd.DataFrame:
    """[일자, 6개 값] 행 목록 → 정제된 일별 DataFrame."""
    df = pd.DataFrame([r[:7] for r in rows], columns=["일자", *DAILY_COLUMNS])
    df = df.apply(lambda c: c.astype(str).str.replace(r"\s+", " ", regex=True).str.strip())

    # '최저 7,200' / '최고 27,200' : 기간 최저·최고 표시 → 표시는 별도 컬럼, 값은 숫자로
    df["시즌_최저최고"] = df["합계_평균가_원_5kg"].str.extract(r"^(최저|최고)\s", expand=False)
    df["합계_평균가_원_5kg"] = df["합계_평균가_원_5kg"].str.replace(
        r"^(최저|최고)\s", "", regex=True
    )
    for col in DAILY_COLUMNS:
        df[col] = to_number(df[col])

    # 존재하지 않는 날짜(예: 2025-02-29)는 제거
    df["일자"] = pd.to_datetime(df["일자"], format="%Y-%m-%d", errors="coerce")
    df = df.dropna(subset=["일자"])

    df.insert(0, "품종", variety)
    df.insert(1, "시즌", season_of(df["일자"]))
    return df.reset_index(drop=True)


def parse_price_whole(path: Path) -> pd.DataFrame:
    """복사-붙여넣기 텍스트(.txt) 또는 화면 엑셀 다운로드(.xlsx)를 읽는다."""
    variety, _ = _meta_from_name(path)
    if path.suffix == ".xlsx":
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
        rows = [
            [str(c) for c in r]
            for r in ws.iter_rows(values_only=True)
            if r and isinstance(r[0], str) and DATE_CELL.match(r[0])
        ]
    else:
        lines = path.read_text(encoding="utf-8").splitlines()
        rows = [_split(line) for line in lines if DATE_ROW.match(line)]
    df = _daily_frame(rows, variety)
    df["원본파일"] = path.name
    return df


# ------------------------------------------------------------------ 월별·상자규격별
def _month_to_date(month_label: str, season: int) -> pd.Timestamp:
    month = int(month_label.rstrip("월"))
    year = season if month >= 7 else season + 1  # 10~12월은 시즌 시작 연도, 1~6월은 다음 해
    return pd.Timestamp(year=year, month=month, day=1)


def parse_price_monthly_box(path: Path) -> pd.DataFrame:
    variety, season = _meta_from_name(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    header = next(line for line in lines if line.startswith("거래월"))
    boxes = []
    for cell in _split(header)[1:]:
        if "총계" in cell:
            boxes.append("총계(5kg환산)")
        else:
            boxes.append(re.search(r"\(([\d.]+)Kg상자\)", cell, re.I)[1] + "kg")

    records = []
    for line in lines:
        if not MONTH_ROW.match(line):
            continue
        cells = _split(line)
        month = _month_to_date(cells[0], season)
        values = cells[1:]
        for i, box in enumerate(boxes):
            chunk = values[i * 4 : i * 4 + 4]
            if len(chunk) < 4:
                continue
            records.append(
                {"거래월": month, "상자규격": box, **dict(zip(BOX_METRICS, chunk, strict=True))}
            )

    df = pd.DataFrame(records)
    for col in BOX_METRICS:
        df[col] = to_number(df[col])
    df = df.dropna(subset=["거래량_톤"])  # 거래 없는 월·규격 제거
    df.insert(0, "품종", variety)
    df.insert(1, "시즌", season)
    return df.reset_index(drop=True)


# ------------------------------------------------------------------ 실행
def build_daily(manual_dir: Path = JASDC_MANUAL_DIR) -> pd.DataFrame | None:
    """모든 일별 파일을 합치고 겹치는 날짜는 엑셀 우선으로 하나만 남긴다."""
    d = manual_dir / DAILY_SUBDIR
    files = sorted(d.glob("price_whole_*.xlsx")) + sorted(d.glob("price_whole_*.txt"))
    if not files:
        return None
    df = pd.concat([parse_price_whole(p) for p in files], ignore_index=True)
    df = df.drop_duplicates(subset=["품종", "일자"], keep="first")
    return df.sort_values(["품종", "일자"]).reset_index(drop=True)


def build_all(manual_dir: Path = JASDC_MANUAL_DIR) -> dict[str, pd.DataFrame]:
    daily = build_daily(manual_dir)
    box_files = sorted((manual_dir / MONTHLY_BOX_SUBDIR).glob("price_monthly_box_*.txt"))
    box = [parse_price_monthly_box(p) for p in box_files]
    out = {}
    if daily is not None:
        out["citrus_price_daily"] = daily
    if box:
        out["citrus_price_monthly_box"] = pd.concat(box, ignore_index=True)
    return out


def main() -> None:
    for name, df in build_all().items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False, encoding=DEFAULT_ENCODING)
        print(f"[저장] processed/{name}.csv ({len(df)}행)")


if __name__ == "__main__":
    main()
