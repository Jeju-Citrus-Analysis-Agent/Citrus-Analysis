"""Read-only tools using the reference repository's cleaning rules."""
import json
import hashlib
import io
from .repository import repository_root, cleaning_rules

ROOT = repository_root()


def schema(name, description, properties):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(properties), "additionalProperties": False}}}


TOOLS = [
    schema("catalog", "실제로 존재하는 분석용 CSV와 열 이름을 확인한다. 먼저 호출 권장.", {}),
    schema("production", "품종별 연도 범위 생산량·면적·변화를 조회. 품종 이름은 원본 표 기준.", {
        "variety": {"type": "string"}, "start_year": {"type": "integer"},
        "end_year": {"type": "integer"}}),
]


def catalog():
    from .data_catalog import catalog as data_catalog
    return data_catalog(ROOT)


FRUIT_SOURCE = "data/raw/public/fruit_production.csv"
FRUIT_YEARS = range(2015, 2021)
# Citrus series from 제주농산물수급관리센터 (2004~2025). Used only when a request leaves the
# 2015~2020 fruit table, and never mixed with it inside one answer.
JASDC_SOURCE = "data/processed/citrus_production_yearly.csv"
JASDC_NAMES = {"온주밀감노지": "노지온주", "온주밀감하우스": "하우스온주", "온주밀감월동": "월동온주",
               "한라봉": "한라봉", "천혜향": "천혜향", "레드향": "레드향", "황금향": "황금향"}


def uses_jasdc(variety, start_year, end_year):
    outside = not (start_year in FRUIT_YEARS and end_year in FRUIT_YEARS)
    return outside and variety in JASDC_NAMES and (ROOT / JASDC_SOURCE).is_file()


def jasdc_production(variety, start_year, end_year):
    import pandas as pd
    path = ROOT / JASDC_SOURCE
    raw = path.read_bytes()
    frame = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    selected = frame[(frame["품종"] == JASDC_NAMES[variety]) & frame["연도"].between(start_year, end_year)].sort_values("연도")
    if selected["연도"].duplicated().any():
        raise ValueError("중복 연도가 있어 단일 통계로 확정할 수 없습니다.")
    rows = [{"연도": int(r["연도"]), "품종": variety, "집계수준": "감귤_품종별(수급관리센터)",
             "생산면적_ha": None if pd.isna(r["재배면적_ha"]) else float(r["재배면적_ha"]),
             "생산량_톤": None if pd.isna(r["생산량_톤"]) else float(r["생산량_톤"])}
            for _, r in selected.iterrows()]
    return {"rows": rows, "source": JASDC_SOURCE, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "request": {"variety": variety, "start_year": start_year, "end_year": end_year},
            "units": {"생산면적_ha": "ha", "생산량_톤": "톤"}, "area_label": "재배면적",
            "missing_years": sorted(set(range(start_year, end_year + 1)) - {r["연도"] for r in rows}),
            "warning": "2017년 재배면적 통계 단절. 2016년 이전과 이후의 면적을 바로 비교하지 마세요."}


def production(variety, start_year, end_year):
    import pandas as pd
    if type(start_year) is not int or type(end_year) is not int or not 1900 <= start_year <= end_year <= 2100:
        raise ValueError("연도 범위를 확인하세요.")
    rules = cleaning_rules(ROOT)
    if variety not in rules.FRUIT_CATEGORY_MAP:
        raise ValueError("원본에 없는 품종입니다.")
    if uses_jasdc(variety, start_year, end_year):
        result = jasdc_production(variety, start_year, end_year)
        add_change(result, start_year, end_year)
        return result
    path = ROOT / "data/raw/public/fruit_production.csv"
    raw = path.read_bytes()
    frame = rules.clean_fruit_production(pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig"))
    selected = frame[(frame["품종"] == variety) & frame["연도"].between(start_year, end_year)]
    selected = selected.sort_values("연도")
    if selected["연도"].duplicated().any():
        raise ValueError("중복 연도가 있어 단일 통계로 확정할 수 없습니다.")
    rows = json.loads(selected.to_json(orient="records", force_ascii=False))
    result = {"rows": rows, "source": path.relative_to(ROOT).as_posix(),
              "source_sha256": hashlib.sha256(raw).hexdigest(),
              "request": {"variety": variety, "start_year": start_year, "end_year": end_year},
              "units": {"생산면적_ha": "ha", "생산량_톤": "톤"},
              "missing_years": sorted(set(range(start_year, end_year + 1)) - set(selected["연도"])),
              "warning": "2017년 면적 통계 단절. 집계수준이 다른 행을 합산하지 마세요."}
    add_change(result, start_year, end_year)
    return result


def add_change(result, start_year, end_year):
    rows = result["rows"]
    if len(rows) > 1 and rows[0]["연도"] == start_year and rows[-1]["연도"] == end_year:
        result["change"] = {}
        for col in ("생산면적_ha", "생산량_톤"):
            if col == "생산면적_ha" and start_year < 2017 <= end_year:
                continue
            before, after = rows[0][col], rows[-1][col]
            if before is not None and after is not None:
                result["change"][col] = {"difference": after - before,
                    "percent": (after / before - 1) * 100 if before else None}
    return result


FUNCTIONS = {f.__name__: f for f in (catalog, production)}


def execute(call):
    try:
        name = call["name"]
        args = json.loads(call["arguments"])
        spec = next(s["function"]["parameters"] for s in TOOLS if s["function"]["name"] == name)
        if not isinstance(args, dict) or set(args) != set(spec["required"]):
            raise ValueError("도구 인자를 확인하세요.")
        for key, value in args.items():
            kind = spec["properties"][key]["type"]
            if (kind == "string" and not isinstance(value, str)) or (kind == "integer" and type(value) is not int) or (kind == "object" and not isinstance(value, dict)):
                raise ValueError("도구 인자 타입을 확인하세요.")
        return FUNCTIONS[name](**args)
    except (ValueError, KeyError, TypeError, StopIteration):
        return {"error": "도구 이름·입력값·데이터 열을 확인하세요."}
    except (OSError, ImportError):
        return {"error": "참조 데이터 또는 의존성이 없습니다. 저장소 경로와 설치 상태를 확인하세요."}
