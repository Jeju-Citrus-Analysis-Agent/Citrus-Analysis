"""Local-only, explicit-assumption profit and break-even calculations."""
import re
from decimal import Decimal, InvalidOperation

D = Decimal
NUMBER = r"-?\d[\d,]*(?:\.\d+)?"
MONEY = rf"({NUMBER})\s*(억|만|천)?\s*원"


def number(text, scale=None):
    value = D(text.replace(",", "")) * {None: 1, "천": 1000, "만": 10000, "억": 100000000}[scale]
    if not value.is_finite() or abs(value) > D("1e15"):
        raise ValueError("입력 금액·수량의 범위를 확인해 주세요.")
    return value


def is_scenario(question, previous=None):
    text = re.sub(r"\s+", "", question)
    if re.search(r"총비용|경영비|손익분기|최소단가|손해.*단가", text):
        return True
    if re.search(rf"비용(?:이|가|는|은)?{MONEY}", text):
        return True
    return bool(previous and re.search(r"단가|판매량|수량|비용|가정|이익", text))


def parse_scenario(question, previous=None):
    """명시한 기준값과 변동률만 해석한다. 빠진 숫자를 모델로 채우지 않는다."""
    if not is_scenario(question, previous):
        return None, None
    text = re.sub(r"\s+", "", question)
    if re.search(r"원/(?:\d+kg|톤|t)|상자|\d+kg당", text, re.I):
        return None, "시나리오 단가는 원/kg 기준으로 알려주세요. 상자·톤 단가를 자동으로 원/kg으로 간주하지 않습니다."
    if re.search(r"원/(?:ha|10a|농가)|(?:ha|10a|농가)당", text, re.I):
        return None, "면적당·농가당 비용을 전체 판매량의 총비용으로 바로 빼지 않습니다. 같은 대상·기간의 총액을 알려주세요."
    if re.search(r"예측해|예상해|맞혀|확정해|실제.*(?:순이익|이익)|기상|날씨", text):
        return None, "이 기능은 입력 가정의 계산입니다. 실제 농가 실적이나 미래 이익을 예측하지 않습니다. 판매가능수량·단가·비용 가정을 알려주세요."
    if re.search(r"추가로|거기서|다시.*(?:하락|감소|인하)", text):
        return None, "추가 변동을 적용할 기준이 모호합니다. 변경 후 단가·수량·비용을 직접 알려주세요."
    plan = {"quantity_kg": None, "price_won_kg": None, "cost_won": None, "cost_basis": "total",
            "changes": {}, "operation": "profit"}
    if previous:
        plan.update({k: v for k, v in previous.items() if k != "changes"})
        plan["changes"] = dict(previous["changes"])
    parsed = set()
    if re.search(r"손익분기|최소단가|손해.*단가", text):
        plan["operation"] = "break_even"
    elif re.search(r"이익|남|소득", text):
        plan["operation"] = "profit"
    quantity = list(re.finditer(rf"(?:판매가능수량|판매가능한양|판매수량|판매량|수량)(?:이|은|는|가)?({NUMBER})(kg|킬로그램|톤|t)", text, re.I))
    if len(quantity) > 1:
        return None, "판매가능수량이 여러 개입니다. 기준 수량 하나를 알려주세요."
    if quantity:
        match = quantity[0]
        plan["quantity_kg"] = str(number(match[1]) * (1000 if match[2].lower() in {"톤", "t"} else 1))
        plan["changes"].pop("quantity_kg", None)
        parsed.add("quantity_kg")
    for key, pattern in (("price_won_kg", rf"(?:단가|가격)(?:가|이|는|은)?{MONEY}"),
                         ("cost_won", rf"(?:총비용|경영비|비용)(?:이|가|는|은)?{MONEY}")):
        matches = list(re.finditer(pattern, text))
        if len(matches) > 1:
            return None, "기준 금액이 여러 개입니다. 단가와 비용을 각각 하나씩 알려주세요."
        if matches:
            plan[key] = str(number(matches[0][1], matches[0][2]))
            plan["changes"].pop(key, None)
            parsed.add(key)
    if "총비용" in text and "경영비" in text:
        return None, "총비용과 경영비가 함께 있습니다. 어느 비용 기준으로 계산할지 알려주세요."
    if "경영비" in text:
        plan["cost_basis"] = "operating"
    elif "총비용" in text:
        plan["cost_basis"] = "total"
    for key, terms in (("price_won_kg", "단가|가격"), ("quantity_kg", "판매량|수량"), ("cost_won", "총비용|경영비|비용")):
        matches = list(re.finditer(rf"(?:{terms})(?:가|이|는|은)?({NUMBER})%(?:가|이|만큼|정도)?(떨어|내려|하락|감소|인하|올라|오르|오르면|상승|증가|인상)", text))
        if len(matches) > 1:
            return None, "같은 항목의 변동률이 여러 개입니다. 기준 변동률 하나를 알려주세요."
        if matches:
            match = matches[0]
            percent = number(match[1])
            if percent < 0:
                return None, "변동 방향과 양수 변동률을 함께 알려주세요. 예: 단가 10% 하락."
            sign = -1 if match[2] in {"떨어", "내려", "하락", "감소", "인하"} else 1
            plan["changes"][key] = str(percent * sign)
            parsed.add(key)
    # Detect unparsed numeric inputs rather than silently inheriting old values.
    if re.search(rf"(?:판매량|판매가능수량|판매가능한양|수량)(?:이|은|는|가|을)?{NUMBER}", text) and "quantity_kg" not in parsed:
        return None, "판매가능수량의 단위를 kg 또는 톤으로 알려주세요. 생산량을 판매량으로 간주하지 않습니다."
    if re.search(rf"(?:단가|가격)(?:가|이|는|은)?{NUMBER}", text) and "price_won_kg" not in parsed:
        return None, "단가는 원/kg 기준 금액 또는 변동률로 알려주세요."
    if re.search(rf"(?:총비용|경영비|비용)(?:이|가|는|은)?{NUMBER}", text) and "cost_won" not in parsed:
        return None, "비용은 원 단위 금액 또는 변동률로 알려주세요."
    missing = [label for key, label in (("quantity_kg", "판매가능수량(kg)"), ("cost_won", "비용(원)")) if plan[key] is None]
    if plan["operation"] == "profit" and plan["price_won_kg"] is None:
        missing.append("단가(원/kg)")
    if missing:
        return None, "가정 계산에 필요한 입력: " + ", ".join(missing) + ". 예: 판매량 1,000kg, 단가 4,000원, 총비용 300만원."
    try:
        compute(plan)
    except (ValueError, InvalidOperation) as exc:
        return None, str(exc)
    return plan, None


def compute(plan):
    """단위가 확인된 가정으로 전후 매출·잔여액·손익분기를 계산한다."""
    if plan["operation"] not in {"profit", "break_even"} or plan["cost_basis"] not in {"total", "operating"}:
        raise ValueError("계산 종류와 비용 기준을 확인해 주세요.")
    base = {key: D(plan[key]) if plan[key] is not None else None for key in ("quantity_kg", "price_won_kg", "cost_won")}
    changed = dict(base)
    for key, value in base.items():
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("수량·단가·비용은 0 이상의 유효한 값이어야 합니다.")
    if not base["quantity_kg"]:
        raise ValueError("판매가능수량은 0보다 커야 합니다.")
    for key, percentage in plan["changes"].items():
        if key not in base or base[key] is None:
            raise ValueError("변동률을 적용할 기준값이 필요합니다.")
        rate = D(percentage)
        if not rate.is_finite() or rate < -100 or abs(rate) > 1000:
            raise ValueError("변동률은 -100% 이상, 절댓값 1000% 이내로 입력해 주세요.")
        changed[key] = base[key] * (1 + rate / 100)
    if not changed["quantity_kg"]:
        raise ValueError("변경 후 판매가능수량은 0보다 커야 합니다.")
    result = {"base": base, "changed": changed,
              "break_even": base["cost_won"] / base["quantity_kg"],
              "changed_break_even": changed["cost_won"] / changed["quantity_kg"]}
    if base["price_won_kg"] is not None:
        for label, inputs in (("before", base), ("after", changed)):
            revenue = inputs["quantity_kg"] * inputs["price_won_kg"]
            profit = revenue - inputs["cost_won"]
            # A separate algebraic identity checks arithmetic, not generated prose.
            if profit + inputs["cost_won"] != revenue:
                raise ValueError("계산 검산 실패")
            result[label] = {"revenue": revenue, "profit": profit}
    return result


def fmt(value):
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def render_scenario(plan):
    result = compute(plan)
    label = "총비용 기준 이익" if plan["cost_basis"] == "total" else "경영비 차감 잔여액 (총비용 기준 순이익 아님)"
    lines = ["사용자 입력 가정에 따른 계산입니다. 실제 농가 실적·미래 예측이 아닙니다.",
             f"기준 가정: 판매가능수량 {fmt(result['base']['quantity_kg'])}kg, "
             f"비용 {fmt(result['base']['cost_won'])}원" + (f", 단가 {fmt(result['base']['price_won_kg'])}원/kg" if result['base']['price_won_kg'] is not None else ""),
             "비용은 지정한 총액으로 계산하며, 변경하지 않은 항목은 고정합니다."]
    if "before" in result:
        lines += ["", f"| 구분 | 매출 (원) | {label} (원) |", "|---|---|---|",
                  f"| 변경 전 | {fmt(result['before']['revenue'])} | {fmt(result['before']['profit'])} |",
                  f"| 변경 후 | {fmt(result['after']['revenue'])} | {fmt(result['after']['profit'])} |", ""]
    for key, title in (("quantity_kg", "판매가능수량"), ("price_won_kg", "단가"), ("cost_won", "비용")):
        if key in plan["changes"]:
            lines.append(f"변경 가정: {title} {D(plan['changes'][key]):+g}% → {fmt(result['changed'][key])}" + ("kg" if key == "quantity_kg" else "원/kg" if key == "price_won_kg" else "원"))
    lines += [f"\n손익분기단가: 변경 전 {fmt(result['break_even'])}원/kg / 변경 후 {fmt(result['changed_break_even'])}원/kg",
              "계산식: 매출 = 판매가능수량 × 단가; 이익/잔여액 = 매출 − 지정 비용; 손익분기단가 = 지정 비용 ÷ 판매가능수량.",
              "해석·한계: 가격·판매량·비용이 실제로 이렇게 변한다는 예측은 아닙니다. 비용에 빠진 자가노동·토지·감가상각 등이 있으면 그 항목까지 반영한 순이익으로 해석할 수 없습니다.",
              "대안: 판매량·가격·비용의 가정을 각각 바꾸어 비교할 수 있습니다. 후속 변동률은 위 기준 가정에 적용하며 중복 누적하지 않습니다.",
              "출처: 이 대화의 사용자 입력 가정. 계산식과 비용 범위는 위에 명시했습니다."]
    return "\n".join(lines)
