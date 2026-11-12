"""Data definitions backed by local files; document coverage never implies availability."""
import argparse
import calendar
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
DOCUMENTED_ONLY = {
    "noji_yearly": ("2021~2025", "연도별 처리량·단가·조수입"),
    "noji_monthly_2025": ("2025년산", "월별 출하량·가격"),
    "noji_market_2025": ("2025년산", "시장별 거래량·가격"),
    "noji_size": ("2023~2025", "규격별 가격·거래비율"),
    "varieties_summary": ("2024~2025", "품종별 유통 비교"),
    "citrus_production_yearly": ("2004~2025", "8개 품종 재배면적·생산량·조수입"),
    "citrus_processing_yearly": ("2004~2025", "가공 처리량·가공률"),
    "citrus_processing_by_company": ("2004~2025", "업체별 가공 처리량"),
    "citrus_export_yearly": ("2003~2025", "국가별 수출량·수출액"),
    "citrus_price_daily": ("2021-10~2026-11 (문서 기준)", "일별 출하량·가격"),
    "citrus_price_monthly_box": ("2024 시즌 (문서 기준)", "월별 상자규격 가격")
}

# Explicit subjects, not "all documented files minus one".
PRICE_DATASETS = {"noji_yearly", "noji_monthly_2025", "noji_market_2025", "noji_size",
                  "varieties_summary", "citrus_production_yearly", "citrus_price_daily", "citrus_price_monthly_box"}
PRODUCTION_DATASETS = {"fruit_production", "jeju_special_crops", "citrus_production_yearly"}
FRUIT_DATASETS = {"fruit_production", "citrus_production_yearly"}


def definitions():
    return json.loads((FOLDER / "data_definitions.json").read_text(encoding="utf-8"))


def profile(root, name, spec):
    import pandas as pd
    result = dict(spec, name=name)
    path = root / spec["path"]
    result["available"] = path.is_file()
    result["observed_period"] = None
    if not result["available"]:
        result["status"] = "파일 없음"
        return result
    try:
        raw = path.read_bytes()
        import io
        frame = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
        result.update(status="파일 확인", source_sha256=hashlib.sha256(raw).hexdigest(), row_count=len(frame))
        result["columns"] = [{"name": column, **spec.get("fields", {}).get(column, {
            "unit": None, "definition": "미등록 열. 의미와 단위 미확인", "status": "미확인"}),
            "null_count": int(frame[column].isna().sum())} for column in frame.columns]
        time_col, kind = spec.get("time_column"), spec.get("time_kind")
        if time_col in frame:
            if kind == "year":
                times = pd.to_numeric(frame[time_col].astype(str).str.extract(r"((?:19|20)\d{2})")[0], errors="coerce").dropna().astype(int)
                if len(times):
                    values = sorted(int(v) for v in times.unique())
                    result["observed_period"] = {"start": values[0], "end": values[-1], "kind": kind,
                                                  "values": values, "invalid_time_rows": len(frame) - len(times)}
            elif kind in {"date", "month"}:
                times = pd.to_datetime(frame[time_col], errors="coerce")
                valid = times.dropna()
                if len(valid):
                    result["observed_period"] = {"start": valid.min().strftime("%Y-%m-%d"),
                        "end": valid.max().strftime("%Y-%m-%d"), "kind": kind,
                        "invalid_time_rows": int(times.isna().sum())}
        keys = spec.get("keys", [])
        result["duplicate_key_rows"] = int(frame.duplicated(keys, keep=False).sum()) if keys and all(c in frame for c in keys) else None
        result["identical_duplicate_rows"] = int(frame.duplicated(keep=False).sum())
        if "지점명" in frame:
            result["stations"] = sorted(str(v) for v in frame["지점명"].dropna().unique())
        if name == "fruit_production":
            result["variety_count"] = int(frame["품종소분류"].nunique())
        if name == "weather_monthly" and "관측일수" in frame:
            short = []
            for _, row in frame.iterrows():
                date = pd.to_datetime(row["연월"], errors="coerce")
                if pd.notna(date) and pd.notna(row["관측일수"]) and row["관측일수"] < calendar.monthrange(date.year, date.month)[1]:
                    short.append({"station": row["지점명"], "month": date.strftime("%Y-%m"),
                                  "observed_days": int(row["관측일수"]), "calendar_days": calendar.monthrange(date.year, date.month)[1]})
            result["short_months"] = short
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="검사 실패", error_type=type(exc).__name__, observed_period=None)
    return result


def catalog(root=None):
    if root is None:
        from .tools import ROOT
        root = ROOT
    root = Path(root)
    specs = definitions()
    for name, (period, title) in DOCUMENTED_ONLY.items():
        specs.setdefault(name, {"path": f"data/processed/{name}.csv", "title": title,
            "documented_period": period, "chat_support": "분석 미지원", "origin": "프로젝트 README 및 요구사항 명세",
            "references": ["README.md: 데이터 목록", "docs/requirements_spec.md §2.1"],
            "quality": ["문서상 기간이며 현재 파일 보유 또는 실제 관측 기간을 의미하지 않음"], "fields": {}})
    # Newly added local files are visible but their semantics are never guessed.
    for path in (root / "data/processed").glob("*.csv"):
        specs.setdefault(path.stem, {"path": path.relative_to(root).as_posix(), "title": path.stem,
            "chat_support": "정의 미등록 / 분석 미지원", "fields": {}, "quality": ["지표 정의·기간·집계수준 확인 필요"]})
    records = [profile(root, name, spec) for name, spec in specs.items()]
    return {"generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
            "scope": "현재 생산 조회 원본 및 processed 분석 자료. upstream 원본·정제 코드는 출처 연결로 표시",
            "definition_basis": "로컬 열 이름·생성 코드·프로젝트 명세. 외부 원기관 정의 대조는 미완료",
            "datasets": records, "production_source": specs["fruit_production"]["path"]}


def period_text(record):
    period = record.get("observed_period")
    if period and period["kind"] == "month":
        return f"{period['start'][:7]}~{period['end'][:7]} (월 식별자)"
    return f"{period['start']}~{period['end']}" if period else "실제 기간 확인 안 됨"


def markdown(data, selected=None):
    records = [r for r in data["datasets"] if selected is None or r["name"] in selected]
    lines = ["# 데이터 안내", "", f"확인 시각: {data['generated_at']}", "",
             data["definition_basis"], "", "파일 보유·실제 기간·지표 정의·분석 지원 여부를 구분합니다.", ""]
    for record in records:
        lines += [f"## {record['title']} ({record['name']})", "", f"- 파일: `{record['path']}`",
                  f"- 상태: {record['status']}", f"- 문서상 기간: {record.get('documented_period', '미확인')}",
                  f"- 실제 파일 기간: {period_text(record)}", f"- 채팅 지원: {record['chat_support']}"]
        if "row_count" in record:
            lines += [f"- 행 수: {record['row_count']:,} / 중복 키 행 수: {record['duplicate_key_rows']}"]
        if record.get("grain"):
            lines.append("- 한 행의 집계 단위: " + record["grain"])
        if record.get("stations"):
            lines.append("- 지점: " + ", ".join(record["stations"]))
        lines += ["- 출처 연결: " + record.get("origin", "미확인"), "- 확인 근거: " + "; ".join(record.get("references", []))]
        for note in record.get("quality", []):
            lines.append("- 주의: " + note)
        if record.get("short_months"):
            lines.append("- 월 전체 관측이 아닌 기록: " + "; ".join(f"{v['station']} {v['month']} {v['observed_days']}/{v['calendar_days']}일" for v in record["short_months"]))
        if record.get("columns"):
            lines += ["", "| 지표 | 단위 | 정의·해석 | 확인 수준 | 결측 행 수 |", "|---|---|---|---|---|"]
            for col in record["columns"]:
                lines.append(f"| {col['name']} | {col['unit'] or '해당 없음/미확인'} | {col['definition']} | {col['status']} | {col['null_count']} |")
        lines.append("")
    return "\n".join(lines)


def select_metadata_names(compact):
    """Apply explicit subject scopes before broad metric scopes."""
    if re.search(r"기상|날씨|weather", compact, re.I):
        return {"weather_daily", "weather_monthly"}
    if "수출" in compact:
        return {"citrus_export_yearly"}
    if re.search(r"가공|수매", compact):
        return {"citrus_processing_yearly", "citrus_processing_by_company"}
    if re.search(r"가격|단가", compact):
        return PRICE_DATASETS
    if re.search(r"유통|출하", compact):
        return {"noji_yearly", "noji_monthly_2025", "noji_market_2025", "noji_size",
                "varieties_summary", "citrus_price_daily", "citrus_price_monthly_box"}
    if re.search(r"특용|특작|special_crops", compact, re.I):
        return {"jeju_special_crops"}
    if re.search(r"과수|감귤|품종|한라봉|천혜향|레드향|황금향|온주|만감류|과일|fruit", compact, re.I):
        return FRUIT_DATASETS
    if "생산량" in compact:
        return PRODUCTION_DATASETS
    if "생산면적" in compact:
        return FRUIT_DATASETS
    return None


def source_lines(records):
    """Only successfully opened files qualify as inspected evidence."""
    inspected = [r["path"] for r in records if r.get("available") and r.get("status") == "파일 확인"]
    absent = [r["path"] for r in records if not r.get("available")]
    unreadable = [r["path"] for r in records if r.get("available") and r.get("status") != "파일 확인"]
    lines = ["실제 확인한 파일: " + (", ".join(inspected) or "없음")]
    if absent:
        lines.append("문서에만 기재된 미보유 파일: " + ", ".join(absent))
    if unreadable:
        lines.append("존재하지만 검사에 실패한 파일: " + ", ".join(unreadable))
    lines.append("정의·문서상 목록의 근거: 프로젝트 README, docs/requirements_spec.md 및 생성·정제 코드. 미보유 파일을 읽은 근거로 사용하지 않습니다. 원기관의 상세 정의 대조는 미완료입니다.")
    return lines


def compact_metadata(records, selected, question):
    """Answer first; keep long inventories and provenance tables behind details."""
    lines = ["현재 로컬 파일 기준 안내입니다."]
    valid = [r for r in records if r.get("status") == "파일 확인"]
    if selected == PRICE_DATASETS and not any(r.get("available") for r in records):
        lines.append("가격 관련 자료는 현재 로컬에 없습니다. (파일 없음)")
    else:
        for record in valid:
            lines.append(f"- {record['title']}: {period_text(record)} / {record['chat_support']}")
        if not valid:
            lines.append("현재 읽어서 확인할 수 있는 해당 자료가 없습니다.")
    absent = sum(not r.get("available") for r in records)
    failed = sum(r.get("available") and r.get("status") != "파일 확인" for r in records)
    if absent:
        lines.append(f"문서에만 기재된 미보유 자료는 {absent}개입니다.")
    if failed:
        lines.append(f"파일은 있지만 검사에 실패한 자료는 {failed}개입니다.")
    for record in valid:
        short = record.get("short_months", [])
        if short:
            parts = sorted({f"{r['month']} {r['observed_days']}/{r['calendar_days']}일" for r in short})
            lines.append("주의: 월 전체가 아닌 관측 분량입니다 (" + "; ".join(parts) + ").")
        if re.search(r"정의|단위|뜻|의미", question):
            for col in record.get("columns", []):
                if col["unit"] and (col["name"].startswith("생산량") if "생산량" in question else True):
                    lines.append(f"- {col['name']}: {col['unit']} ({col['status']})")
    lines.append("실제 확인한 파일: " + (", ".join(r["path"] for r in valid) or "없음"))
    lines.append("‘자세히’라고 입력하면 파일 목록·정의·주의사항을 볼 수 있습니다.")
    return "\n".join(lines)


def metadata_answer(question):
    compact = re.sub(r"\s+", "", question)
    area_terms = {term for term in ("수확면적", "생산면적", "재배면적") if term in compact}
    area_definition = len(area_terms) >= 2 and bool(re.search(r"차이|같아|같은|다르|뜻|정의|의미", compact))
    has_year = bool(re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", compact))
    definition = bool(re.search(r"정의|뜻|의미|단위|출처", compact)) and not has_year
    metadata = definition or bool(re.search(r"어떤데이터|어떤자료|데이터목록|자료목록|데이터종류|자료종류|데이터.*(?:기간|있어|없어)|자료.*(?:기간|있어|없어)|조회가능기간|몇년(?:부터|까지)", compact))
    if not (metadata or area_definition):
        return None
    data = catalog()
    if area_definition:
        explanation = ("정의 사전 기준으로 과수 자료는 생산면적(ha), 특용작물 자료는 재배면적[ha]·수확면적[ha]를 각각 제공합니다. "
                "생산면적과 수확·재배면적의 정의가 같다는 근거는 확인되지 않았습니다. 서로 다른 자료의 값을 같은 지표로 합치지 않습니다.\n"
                "과수 수확면적 질문에는 생산면적을 참고값으로 구분해 안내합니다.\n")
        area_records = [r for r in data["datasets"] if r["name"] in {"fruit_production", "jeju_special_crops"}]
        return explanation + "\n".join(source_lines(area_records))
    selected = select_metadata_names(compact)
    records = [r for r in data["datasets"] if selected is None or r["name"] in selected]
    if not re.search(r"자세|상세|전체목록", compact):
        return compact_metadata(records, selected, compact)
    lines = ["현재 로컬 파일 기준 안내입니다. 보유 여부와 분석 지원 여부는 별개입니다.", "",
             "| 자료 | 파일 상태 | 실제 파일 기간 | 문서상 기간 | 채팅 지원 |",
             "|---|---|---|---|---|"]
    summary = []
    if selected == PRODUCTION_DATASETS:
        for name, label in (("fruit_production", "과수 품종별 생산량"), ("jeju_special_crops", "특용작물 생산량")):
            record = next((r for r in records if r["name"] == name), None)
            if record and record.get("status") == "파일 확인":
                summary.append(f"{label}은 {period_text(record)} 자료를 보유합니다.")
        summary.append("현재 검증된 수치 조회는 과수 자료만 지원하며, 특용작물은 자료 안내만 지원합니다.")
    if selected == PRICE_DATASETS and not any(r.get("available") for r in records):
        summary.append("가격 관련 자료는 현재 로컬에 없습니다. 아래는 프로젝트 문서에 기재된 파일 목록입니다.")
    if summary:
        lines = lines[:2] + summary + [""] + lines[2:]
    for record in records:
        lines.append(f"| {record['title']} | {record['status']} | {period_text(record)} | {record.get('documented_period', '미확인')} | {record['chat_support']} |")
    if selected:
        for record in records:
            if record.get("available") and record.get("status") == "파일 확인":
                lines += ["", record["name"] + ":", *["- " + note for note in record.get("quality", [])]]
                if record.get("short_months"):
                    lines.append("- 월 전체가 아닌 관측 기록: " + "; ".join(f"{v['station']} {v['month']} {v['observed_days']}/{v['calendar_days']}일" for v in record["short_months"]))
                if re.search(r"정의|단위|뜻|의미", compact):
                    for column in record.get("columns", []):
                        if column["unit"]:
                            lines.append(f"- {column['name']}: {column['unit']} — {column['definition']} ({column['status']})")
    lines += ["", *source_lines(records)]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="로컬 자료 정의·보유 기간 안내 생성")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = catalog()
    text = markdown(data)
    if args.write:
        directory = FOLDER / "docs"
        directory.mkdir(exist_ok=True)
        (directory / "data_catalog.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        (directory / "DATA_GUIDE.md").write_text(text, encoding="utf-8")
        print("Saved citrus_freellm/docs/DATA_GUIDE.md and data_catalog.json")
    else:
        import sys
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(text)


if __name__ == "__main__":
    main()
