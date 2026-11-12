"""Explicit multi-variety calculations with source and independent arithmetic checks."""
import math
import re
from decimal import Decimal

from .guardrails import ALIASES, QUALITY_NOTE, validate_evidence
from .reference_check import verify_reference
from .tools import production


class AnalysisUnavailable(ValueError):
    """A known missing source value; safe to explain without hiding the reason."""


def categories():
    from .tools import ROOT
    from .repository import cleaning_rules
    return cleaning_rules(ROOT).FRUIT_CATEGORY_MAP


def plan_analysis(question):
    compact = re.sub(r"\s+", "", question)
    mapping = categories()
    names = {alias: name for name in mapping for alias in ALIASES.get(name, (name,))}
    # Group labels must not be read as the variety named 기타.
    name_text = compact.replace("기타과수", "")
    found = list(dict.fromkeys(names[m.group()] for m in re.finditer("|".join(map(re.escape, sorted(names, key=len, reverse=True))), name_text)))
    ranking = bool(re.search(r"순위|상위|하위|가장많|가장적", compact))
    average = "평균" in compact
    if len(found) < 2 and not ranking and not average:
        return None, None
    if re.search(r"왜|원인|예측|전망|이익|수익|조수입|가격|단가|합계|총합|면적당|ha당|헥타르당", compact, re.I):
        return None, "현재 분석은 생산량·생산면적의 품종 비교, 순위, 연도 평균을 지원합니다. 원인·예측·합계 등은 지원하지 않습니다."
    if ranking and average:
        return None, "기간 평균과 순위는 나누어 질문해 주세요."
    explicit_years = [int(y) for y in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", compact)]
    years = sorted(set(explicit_years))
    if not years:
        return None, "분석할 연도를 알려주세요. 예: 2020년 한라봉과 천혜향 생산량 비교."
    range_requested = bool(re.search(r"부터|까지|[~～–—]|연도별|매년", compact))
    if range_requested and len(years) != 2:
        return None, "기간 분석은 시작 연도와 종료 연도 두 개를 명시해 주세요."
    if range_requested:
        if explicit_years[0] > explicit_years[-1]:
            return None, "기간은 시작 연도부터 종료 연도 순서로 알려주세요."
        years = list(range(min(years), max(years) + 1))
    if len(years) > 30:
        return None, "분석 기간은 30년 이내로 좁혀 주세요."
    metrics = (["생산량_톤"] if "생산량" in compact else []) + (["생산면적_ha"] if "면적" in compact else [])
    if len(metrics) != 1:
        return None, "비교할 지표 하나를 알려주세요. 생산량 또는 생산면적을 지원합니다."
    if "수확면적" in compact or "재배면적" in compact:
        return None, "이 계산의 면적 지표는 원자료의 생산면적입니다. 수확·재배면적과 동일 정의인지 확인되지 않아 해당 지표로 계산하지 않습니다."
    if ranking and not found:
        group = ("만감류_품종" if "만감류" in compact else "감귤_재배형태" if "재배형태" in compact
                 else "기타과수" if "기타과수" in compact else None)
        if not group:
            return None, "순위의 비교 대상을 알려주세요. 예: 2020년 만감류 생산량 순위, 또는 품종 이름을 나열해 주세요. 집계수준이 다른 행은 섞지 않습니다."
        found = [name for name, (_, level) in mapping.items() if level == group]
    elif ranking and found and re.search(r"(?:만감류|재배형태|기타과수)중", compact):
        return None, "집단 전체 순위인지 나열한 품종끼리의 순위인지 확인해 주세요. 예: 2020년 만감류 생산량 순위."
    if not found:
        return None, "평균을 계산할 품종을 알려주세요."
    if len({mapping[name][1] for name in found}) != 1:
        return None, "선택한 항목의 집계수준이 달라 비교·순위를 보류했습니다. 같은 수준의 품종을 선택해 주세요."
    if not average and len(years) != 1:
        return None, "여러 품종의 비교·순위는 연도 하나를 지정해 주세요. 기간 평균은 별도로 지원합니다."
    if average and len(years) < 2:
        return None, "연도 평균은 두 개 이상의 연도 또는 기간을 알려주세요."
    if average and metrics[0] == "생산면적_ha" and min(years) < 2017 <= max(years):
        return None, "2017년 통계 단절을 가로지르는 생산면적 평균은 계산하지 않습니다."
    top = re.search(r"(?:상위|하위)(\d+)", compact)
    limit = int(top.group(1)) if top else 1 if re.search(r"가장많|가장적", compact) else len(found)
    if limit < 1:
        return None, "표시할 순위 개수는 1 이상이어야 합니다."
    return {"operation": "average" if average else "rank" if ranking else "compare",
            "varieties": found, "years": years, "metric": metrics[0],
            "ascending": bool(re.search(r"하위|가장적", compact)), "limit": limit}, None


def calculate(plan):
    """Tool calculation. Return evidence as well as values for validation."""
    validate_plan(plan)
    import pandas as pd
    evidence, values = {}, {}
    for name in plan["varieties"]:
        data = production(name, min(plan["years"]), max(plan["years"]))
        evidence[name] = data
        selected = {r["연도"]: r[plan["metric"]] for r in data["rows"] if r["연도"] in plan["years"]}
        if len(selected) != len(plan["years"]) or any(v is None for v in selected.values()):
            missing = [str(year) for year in plan["years"] if selected.get(year) is None]
            raise AnalysisUnavailable(f"{name}: {', '.join(missing)}년 자료가 없거나 결측이어서 분석을 보류합니다. 해당 연도를 제외한 평균·순위는 만들지 않았습니다.")
        series = pd.Series(list(selected.values()), dtype=float)
        values[name] = float(series.mean()) if plan["operation"] == "average" else float(series.iloc[0])
    return {"plan": plan, "evidence": evidence, "values": values}


def validate_calculation(result, plan):
    validate_plan(plan)
    if result.get("plan") != plan or set(result["evidence"]) != set(plan["varieties"]) or set(result["values"]) != set(plan["varieties"]):
        raise ValueError("분석 조건 또는 품종 목록 불일치")
    expected = {}
    for name in plan["varieties"]:
        request = {"variety": name, "start_year": min(plan["years"]), "end_year": max(plan["years"])}
        data = result["evidence"][name]
        validate_evidence(data, request)
        raw = verify_reference(data, request)
        position = 1 if plan["metric"] == "생산량_톤" else 0
        numbers = [raw.get(year, (None, None))[position] for year in plan["years"]]
        if any(n is None for n in numbers):
            raise ValueError("원자료에 요청 연도 값이 없습니다.")
        expected[name] = sum(numbers, Decimal(0)) / len(numbers) if plan["operation"] == "average" else numbers[0]
        actual = result["values"][name]
        if type(actual) not in (int, float) or not math.isfinite(actual) or not math.isclose(actual, float(expected[name]), rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("계산 결과가 독립 재계산과 다릅니다.")
    return expected


def validate_plan(plan):
    mapping = categories()
    if set(plan) != {"operation", "varieties", "years", "metric", "ascending", "limit"} or plan["operation"] not in {"compare", "rank", "average"}:
        raise ValueError("지원하지 않는 분석 조건")
    names, years = plan["varieties"], plan["years"]
    if not names or len(set(names)) != len(names) or any(n not in mapping for n in names) or len({mapping[n][1] for n in names}) != 1:
        raise ValueError("품종 또는 집계수준 불일치")
    if not years or len(years) > 30 or any(type(y) is not int or not 1900 <= y <= 2099 for y in years) or years != sorted(set(years)):
        raise ValueError("분석 연도 조건 오류")
    if plan["metric"] not in {"생산량_톤", "생산면적_ha"} or type(plan["ascending"]) is not bool or type(plan["limit"]) is not int or plan["limit"] < 1:
        raise ValueError("지표·순위 조건 오류")
    if plan["operation"] != "average" and len(years) != 1:
        raise ValueError("비교·순위는 단일 연도만 지원")
    if plan["operation"] == "average" and (len(years) < 2 or plan["metric"] == "생산면적_ha" and min(years) < 2017 <= max(years)):
        raise ValueError("평균 기간 또는 면적 단절 조건 오류")


def render_analysis(result, plan):
    values = validate_calculation(result, plan)
    ranking = plan["operation"] == "rank"
    order = sorted(values, key=lambda n: (values[n] if plan["ascending"] else -values[n], n)) if ranking else plan["varieties"]
    unit = "톤" if plan["metric"] == "생산량_톤" else "ha"
    label = "생산량" if unit == "톤" else "생산면적"
    years = ", ".join(map(str, plan["years"]))
    lines = [f"{years}년 · {label}" + (" 연도 산술평균" if plan["operation"] == "average" else " 순위" if ranking else " 품종 비교"), "",
             f"| {'순위 | ' if ranking else ''}품종 | {label} ({unit}) |", "|" + "---|" * (3 if ranking else 2)]
    rank, last = 0, None
    for index, name in enumerate(order, 1):
        value = values[name]
        if value != last:
            rank = index
        last = value
        # Include all ties at the cutoff; ranks use 1,1,3 competition ranking.
        if ranking and rank > plan["limit"]:
            continue
        formatted = f"{value:,.2f}".rstrip("0").rstrip(".")
        lines.append(f"| {str(rank) + ' | ' if ranking else ''}{name} | {formatted} |")
    if plan["operation"] == "compare" and len(order) == 2:
        before, after = values[order[0]], values[order[1]]
        delta = after - before
        percentage = f"{delta / before * 100:+.2f}%" if before else "기준값이 0이므로 계산하지 않음"
        lines.append(f"\n비교 기준: {order[0]} → {order[1]} / 품종 간 차이: {delta:+,.2f} {unit} / 기준 품종 대비 차이율: {percentage}")
    if plan["operation"] == "average":
        lines.append(f"\n품종별 {len(plan['years'])}개 연도의 산술평균입니다. 품종 간 합산·면적 가중평균이 아닙니다. 누락 연도는 제외 계산하지 않습니다.")
    if ranking:
        lines.append("\n명시한 비교 대상 안에서만 산정한 순위입니다. 동률은 공동 순위(1, 1, 3)이며 경계의 동률은 모두 표시합니다.")
    if unit == "ha":
        lines.append("\n품질 주의: " + QUALITY_NOTE)
    lines.append("\n출처: data/raw/public/fruit_production.csv (값·연도·계산 독립 대조 통과)")
    return "\n".join(lines)
