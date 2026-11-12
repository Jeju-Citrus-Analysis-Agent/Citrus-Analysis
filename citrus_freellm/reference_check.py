"""Independent CSV/Decimal audit; never calls the pandas lookup or cleaner."""
import csv
import hashlib
import io
from decimal import Decimal, InvalidOperation

SOURCE = "data/raw/public/fruit_production.csv"
FIELDS = ("기준연도", "품종대분류", "품종소분류", "생산면적(ha)", "생산량(톤)")


def numeric(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("불리언 수치")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("수치 형식 오류") from None
    if not number.is_finite() or number < 0:
        raise ValueError("원자료 수치 오류")
    return number


def verify_reference(data, request):
    from . import tools
    # Read fresh bytes, not data supplied by the model or lookup function.
    raw = (tools.ROOT / SOURCE).read_bytes()
    if data.get("source_sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("조회 시점과 검증 시점의 원자료가 다릅니다.")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != list(FIELDS):
        raise ValueError("원자료 열 또는 단위 변경")
    expected = {}
    for row in reader:
        # Independent implementation of the documented 기타 normalization.
        variety = row["품종소분류"]
        if row["품종대분류"] == "만감류" and variety == "기타":
            variety = "만감류기타"
        if variety != request["variety"]:
            continue
        year = int(row["기준연도"])
        if not request["start_year"] <= year <= request["end_year"]:
            continue
        if year in expected:
            raise ValueError("원자료의 품종·연도가 중복됩니다.")
        expected[year] = (numeric(row["생산면적(ha)"]), numeric(row["생산량(톤)"]))
    actual = {r["연도"]: (numeric(r["생산면적_ha"]), numeric(r["생산량_톤"])) for r in data["rows"]}
    if actual != expected:
        raise ValueError("원자료와 조회 값 또는 연도 행이 다릅니다.")
    missing = sorted(set(range(request["start_year"], request["end_year"] + 1)) - expected.keys())
    if data["missing_years"] != missing:
        raise ValueError("원자료와 자료 없음 표시가 다릅니다.")
    return expected
