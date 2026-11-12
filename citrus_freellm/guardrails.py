"""Evidence-only rendering for annual production and area queries.

Model prose never enters the user-visible answer. Request matching and evidence
validation fail closed; no second model is treated as a factuality oracle.
"""
import math
import re

SOURCE = "data/raw/public/fruit_production.csv"
QUALITY_NOTE = (
    "2017년 면적 통계에는 단절이 있습니다. 이를 데이터 누락으로 해석하지 않습니다. "
    "2016년 이전과 2017년 이후의 면적·면적당 지표를 직접 비교하지 않습니다."
)
CLARIFY = "품종 하나와 조회 연도를 명시해 주세요. 예: 2019년과 2020년 천혜향 생산량 비교."
UNSUPPORTED = "이 질문의 원인·미래값·실제 수익을 확정할 근거 또는 계산 조건이 부족합니다. 근거 없는 원인 단정·미래 예측·합계 분석은 지원하지 않습니다. 기존 분석의 연관성 설명과 입력 가정의 이익·손익분기 계산은 가능합니다."

# Longest-first matching keeps 만감류하우스 distinct from 온주밀감하우스.
ALIASES = {
    "온주밀감노지": ("온주밀감노지", "노지온주"),
    "온주밀감하우스": ("온주밀감하우스", "하우스온주"),
    "온주밀감월동": ("온주밀감월동", "월동온주"),
}


def request_for(question, previous=None):
    """질문에서 품종·연도·지표를 확인하고 조회 조건과 표시 조건을 분리한다."""
    from .tools import ROOT
    from .repository import cleaning_rules
    FRUIT_CATEGORY_MAP = cleaning_rules(ROOT).FRUIT_CATEGORY_MAP
    compact = re.sub(r"\s+", "", question)
    if re.search(r"왜|원인|예측|전망|이익|수익|조수입|가격|단가|합계|총합|평균|순위|면적당|ha당|헥타르당", compact, re.I):
        return None, UNSUPPORTED
    names = {alias: name for name in FRUIT_CATEGORY_MAP
             for alias in ALIASES.get(name, (name,))}
    pattern = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    varieties = {names[m.group()] for m in re.finditer(pattern, compact)}
    if len(varieties) > 1:
        return None, CLARIFY
    explicit_years = [int(y) for y in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", compact)]
    years = sorted(set(explicit_years))
    metrics = []
    if "생산량" in compact:
        metrics.append("생산량_톤")
    if "면적" in compact:
        metrics.append("생산면적_ha")
    if "생산량말고" in compact and "면적" in compact:
        metrics = ["생산면적_ha"]
    elif "면적말고" in compact and "생산량" in compact:
        metrics = ["생산량_톤"]
    if re.search(r"둘다|둘모두", compact):
        metrics = ["생산량_톤", "생산면적_ha"]
    if not explicit_years and re.search(r"올해|금년|내년|최근|최신|작년|지난해", compact):
        return None, "상대적인 기간 대신 조회할 기준 연도를 숫자로 명시해 주세요."
    if not varieties and not years and not metrics:
        return None, CLARIFY
    variety = next(iter(varieties), None)
    if previous:
        variety = variety or previous["variety"]
        if not years:
            years = previous.get("years", [previous["start_year"], previous["end_year"]])
        metrics = metrics or previous.get("metrics", ["생산량_톤"])
    metrics = metrics or ["생산량_톤"]
    if not variety or not years:
        return None, CLARIFY
    if re.search(r"전년|작년|지난해", compact):
        if len(set(years)) != 1:
            return None, "전년 비교의 기준 연도 하나를 명시해 주세요."
        years = [years[0] - 1, years[0]]
    elif len(years) == 1 and re.search(r"비교|대비|증감|증가|감소", compact):
        return None, CLARIFY
    is_range = bool(re.search(r"부터|까지|[~～〜–—-]|연도별|매년", compact))
    if is_range and len(explicit_years) > 1 and explicit_years[0] > explicit_years[-1]:
        return None, "조회 기간은 시작 연도부터 종료 연도 순서로 입력해 주세요."
    if is_range and len(years) > 2:
        return None, "기간 조회는 시작 연도와 종료 연도 두 개로 지정해 주세요."
    if not explicit_years and previous and not is_range:
        mode = previous.get("mode", "selected")
    else:
        mode = "range" if is_range else "selected"
    years = list(range(min(years), max(years) + 1)) if mode == "range" else sorted(set(years))
    plan = {"variety": variety, "start_year": min(years), "end_year": max(years),
            "years": years, "metrics": metrics, "mode": mode}
    area_terms = [term for term in ("수확면적", "재배면적") if term in compact]
    if not area_terms and "생산면적" not in compact and previous:
        area_terms = previous.get("requested_area_terms", [])
    if area_terms and "생산면적_ha" in metrics:
        plan["requested_area_terms"] = area_terms
    return plan, None


def lookup_request(plan):
    """Only lookup arguments enter the tool; display intent stays local."""
    return {key: plan[key] for key in ("variety", "start_year", "end_year")}


def validate_evidence(data, request):
    request = lookup_request(request)
    from jeju_citrus.data.clean_quality import FRUIT_CATEGORY_MAP
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("조회 실패")
    if data.get("request") != request or data.get("source") != SOURCE:
        raise ValueError("조회 조건 또는 출처 불일치")
    if data.get("units") != {"생산면적_ha": "ha", "생산량_톤": "톤"}:
        raise ValueError("단위 불일치")
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise ValueError("행 형식 오류")
    years = set()
    for row in rows:
        year = row["연도"]
        if type(year) is not int or year in years or not request["start_year"] <= year <= request["end_year"]:
            raise ValueError("기간 또는 중복 오류")
        if row["품종"] != request["variety"]:
            raise ValueError("품종 불일치")
        if row["집계수준"] != FRUIT_CATEGORY_MAP[request["variety"]][1]:
            raise ValueError("집계수준 불일치")
        years.add(year)
        for metric in ("생산량_톤", "생산면적_ha"):
            value = row[metric]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError("유효하지 않은 수치")
    expected_missing = sorted(set(range(request["start_year"], request["end_year"] + 1)) - years)
    if data.get("missing_years") != expected_missing:
        raise ValueError("누락 연도 불일치")
    if len({r["집계수준"] for r in rows}) > 1:
        raise ValueError("집계수준 혼합")
    from .reference_check import verify_reference
    verify_reference(data, request)
    return sorted(rows, key=lambda r: r["연도"])


def number(value):
    return "자료 없음" if value is None else f"{value:,.2f}".rstrip("0").rstrip(".")


def render(data, request, question):
    rows = validate_evidence(data, request)
    compact = re.sub(r"\s+", "", question)
    definitions = {"생산량_톤": ("생산량_톤", "생산량", "톤"),
                   "생산면적_ha": ("생산면적_ha", "생산면적", "ha")}
    keys = request.get("metrics")
    if keys is None:
        keys = (["생산량_톤"] if "면적" not in compact or "생산량" in compact else [])
        if "면적" in compact:
            keys.append("생산면적_ha")
    metrics = [definitions[key] for key in keys]
    display_years = request.get("years", list(range(request["start_year"], request["end_year"] + 1)))
    title = (f"{min(display_years)}~{max(display_years)}년" if request.get("mode") == "range" and len(display_years) > 1
             else ", ".join(map(str, display_years)) + "년")
    lines = [f"{request['variety']} · {title}", ""]
    area_terms = request.get("requested_area_terms", [])
    if area_terms and "생산면적_ha" in keys:
        lines += ["요청 지표: " + "·".join(area_terms) + ". 해당 구분의 통계는 현재 조회 자료에서 확인할 수 없습니다.",
                  "아래 면적 값은 참고용으로 제공하는 원자료의 ‘생산면적(ha)’입니다. "
                  "요청한 지표와 정의가 같은지 확인되지 않았으며, 그 지표의 확정값으로 대체하지 않습니다.", ""]
    lines += ["| 연도 | " + " | ".join(f"{label} ({unit})" for _, label, unit in metrics) + " |",
              "|---|" + "---|" * len(metrics)]
    by_year = {r["연도"]: r for r in rows}
    for year in display_years:
        lines.append(f"| {year} | " + " | ".join(number(by_year.get(year, {}).get(key)) for key, _, _ in metrics) + " |")
    first, last = by_year.get(request["start_year"]), by_year.get(request["end_year"])
    if first and last and request["start_year"] != request["end_year"] and (len(display_years) == 2 or request.get("mode", "range") == "range"):
        lines.append(f"\n비교 기준: {request['start_year']}년 → {request['end_year']}년")
        for key, label, unit in metrics:
            if key == "생산면적_ha" and request["start_year"] < 2017 <= request["end_year"]:
                lines.append("\n면적 통계 단절을 가로지르는 면적 변화량·변화율은 제공하지 않습니다.")
                continue
            before, after = first[key], last[key]
            if before is None or after is None:
                continue
            delta = after - before
            percent = f"{delta / before * 100:+.2f}%" if before else "기준값이 0이어서 계산하지 않음"
            lines.append(f"\n{label} 변화: {delta:+,.2f} {unit} / 변화율: {percent}")
    displayed_missing = sorted(set(data["missing_years"]) & set(display_years))
    if displayed_missing:
        lines.append("\n자료 없는 연도: " + ", ".join(map(str, displayed_missing)) + ". 보간하거나 추정하지 않았습니다.")
    if any(key == "생산면적_ha" for key, _, _ in metrics):
        lines.append("\n품질 주의: " + QUALITY_NOTE)
    lines.append("\n출처: " + SOURCE)
    return "\n".join(lines)
