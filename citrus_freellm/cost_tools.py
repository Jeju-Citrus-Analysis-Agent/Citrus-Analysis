"""Standard-income (경영비·소득), break-even price and CPI-real price lookups.

Every figure comes from a registered local file and is re-checked before it is shown:
소득 = 총수입 − 경영비, 순수익 = 총수입 − 생산비, 만원 열 = 원 열 ÷ 10,000.
Statements from notebooks 03·04 stay in knowledge cards; this module only computes.
"""
import re

import pandas as pd

STANDARD_INCOME = 'data/external/cost/standard_income.csv'
CPI = 'data/external/cpi/cpi_annual.csv'
PRODUCTION = 'data/processed/citrus_production_yearly.csv'

COST_VARIETIES = ('노지온주', '하우스온주', '월동온주', '한라봉', '천혜향', '레드향', '황금향')
PRICE_VARIETIES = COST_VARIETIES + ('카라향',)
ALIASES = {'노지감귤': '노지온주', '노지': '노지온주', '시설감귤': '하우스온주', '하우스감귤': '하우스온주',
           '하우스': '하우스온주', '하우스월동감귤': '월동온주', '월동감귤': '월동온주', '월동': '월동온주'}
# Column stem → display label (만원/10a unless stated).
METRICS = {'총수입': '총수입', '경영비': '경영비', '소득': '소득', '생산비': '생산비', '순수익': '순수익'}
METRIC_TERMS = (('총수입', r'총수입|매출|조수입'), ('경영비', r'경영비|비용'), ('소득', r'(?<!순)(?<!표준)소득'),
                ('생산비', r'생산비'), ('순수익', r'순수익|순이익'))
BASIS_NOTE = ('표준소득표는 표본 농가 조사값(10a = 1,000㎡당)입니다. 소득 = 총수입 − 경영비이며 자가노동·자기자본 보상이 남아 있어 '
              '순이익이 아닙니다. 순수익 = 총수입 − 생산비(경영비 + 자가노동비 + 자본용역비)입니다. 만감류는 표준표 총수입이 '
              '제주 평균의 1.1~3.7배라 평균 농가 소득으로 읽으면 과대평가됩니다.')

COST_TERMS = r'경영비|소득|순수익|순이익|생산비|총수입|표준소득|손익분기|실질단가|실질가격|실질매출|물가보정|물가를?빼|경영비율'
EXPLAIN_TERMS = r'왜|원인|이유|때문|분해|몇톤|만톤|넘으면|많으면|평균|차이는|차이가|의미|뜻|어떤품종|어느품종|추천|유리'


def compact(question):
    return re.sub(r'\s+', '', question)


def wants_cost_lookup(question):
    """Numeric lookups only. Assumption scenarios and 'why' questions go elsewhere."""
    q = compact(question)
    if not re.search(COST_TERMS, q):
        return False
    if re.search(r'\d[\d,]*(?:\.\d+)?(?:억|만|천)?(?:원|kg|킬로|톤|t\b)', q, re.I) or re.search(r'판매량|판매가능', q):
        return False
    if re.search(EXPLAIN_TERMS, q) or re.search(r'예측|내년|미래|전망', q):
        return False
    if re.search(r'경영비물가|비용물가|경영비지수|비용구성|어때|어떤가|어떻게', q):
        return False
    if re.search(r'손익분기', q) and re.search(r'생산량|물량', q):
        return False
    if re.search(r'실질|물가', q) and not re.search(r'단가|가격|매출|조수입|소득|경영비|순수익', q):
        return False
    return bool(varieties_in(question) or years_in(question) or re.search(r'품종별|품종마다|전체품종|모든품종|순위', q))


def varieties_in(question):
    q = compact(question)
    found = [v for v in PRICE_VARIETIES if v in q]
    for alias, name in ALIASES.items():
        if alias in q and name not in found and not any(alias in v for v in found):
            found.append(name)
    return list(dict.fromkeys(found))


def years_in(question):
    years = sorted(set(map(int, re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', question))))
    if len(years) == 2 and re.search(r'부터|까지|~|～|사이', question):
        return list(range(years[0], years[1] + 1))
    return years


def plan_for(question):
    q = compact(question)
    if re.search(r'손익분기', q):
        kind = 'breakeven'
    elif re.search(r'(?:실질|물가).*(?:단가|가격)|(?:단가|가격).*(?:실질|물가)', q):
        kind = 'real_price'
    else:
        kind = 'income'
    metrics = [name for name, pattern in METRIC_TERMS if re.search(pattern, q)]
    return {'kind': kind, 'varieties': varieties_in(question), 'years': years_in(question),
            'metrics': metrics, 'real': bool(re.search(r'실질|물가', q)),
            'rank': bool(re.search(r'순위|비교|1위|높|낮|품종별|품종마다', q))}


def verified_standard_income(read_source):
    frame, source = read_source(STANDARD_INCOME)
    needed = ['산지연도', '대응품종', '수량_kg_10a', '단가_원_kg'] + [f'{m}_원_10a' for m in METRICS] + [f'{m}_만원_10a' for m in METRICS]
    missing = [c for c in needed if c not in frame]
    if missing:
        raise ValueError('표준소득표 열이 없습니다: ' + ', '.join(missing))
    won = frame[[f'{m}_원_10a' for m in METRICS]].astype(float)
    if ((won['총수입_원_10a'] - won['경영비_원_10a'] - won['소득_원_10a']).abs() > 1).any():
        raise ValueError('표준소득표 검산 실패: 소득 ≠ 총수입 − 경영비')
    if ((won['총수입_원_10a'] - won['생산비_원_10a'] - won['순수익_원_10a']).abs() > 1).any():
        raise ValueError('표준소득표 검산 실패: 순수익 ≠ 총수입 − 생산비')
    for metric in METRICS:
        if ((frame[f'{metric}_원_10a'] / 10_000 - frame[f'{metric}_만원_10a']).abs() > 0.06).any():
            raise ValueError(f'표준소득표 단위 검산 실패: {metric}')
    if frame.duplicated(['산지연도', '대응품종']).any():
        raise ValueError('표준소득표에 같은 연도·품종이 중복돼 있습니다.')
    if (frame['수량_kg_10a'] <= 0).any():
        raise ValueError('표준소득표 수량이 0 이하입니다.')
    return frame, source


def cpi_series(read_source):
    frame, source = read_source(CPI)
    if not {'연도', 'CPI_2020_100'} <= set(frame) or frame['연도'].duplicated().any():
        raise ValueError('CPI 자료 형식을 확인하지 못했습니다.')
    series = frame.set_index('연도')['CPI_2020_100'].astype(float)
    if (series <= 0).any() or abs(series.get(2020, 0) - 100) > 0.01:
        raise ValueError('CPI 기준연도(2020=100)를 확인하지 못했습니다.')
    return series, source


def select_rows(frame, varieties, years, unavailable):
    """Explicitly requested variety·year pairs must exist; otherwise say which are missing."""
    available = {v: sorted(frame.loc[frame['대응품종'] == v, '산지연도'].astype(int)) for v in COST_VARIETIES}
    for variety in varieties:
        if variety not in COST_VARIETIES:
            raise unavailable(f'{variety}은(는) 표준소득표에 없는 품종입니다. 표준소득표 품종: ' + ', '.join(COST_VARIETIES))
        lacking = [y for y in years if y not in available[variety]]
        if lacking:
            have = available[variety]
            raise unavailable(f'{variety} 표준소득표는 {have[0]}~{have[-1]}년산만 있습니다. '
                              f'요청 연도 중 없는 해: {", ".join(map(str, lacking))}.')
    all_years = sorted(frame['산지연도'].astype(int).unique())
    outside = [y for y in years if y not in all_years]
    if outside:
        raise unavailable(f'표준소득표는 {all_years[0]}~{all_years[-1]}년산 자료입니다. 없는 해: {", ".join(map(str, outside))}.')
    rows = frame
    if varieties:
        rows = rows[rows['대응품종'].isin(varieties)]
    if years:
        rows = rows[rows['산지연도'].isin(years)]
    if rows.empty:
        raise unavailable('지정한 조건의 표준소득표 자료가 없습니다.')
    order = {v: i for i, v in enumerate(COST_VARIETIES)}
    return rows.assign(_order=rows['대응품종'].map(order)).sort_values(['산지연도', '_order']).drop(columns='_order')


def income_lookup(plan, read_source, table, unavailable):
    frame, source = verified_standard_income(read_source)
    rows = select_rows(frame, plan['varieties'], plan['years'], unavailable)
    sources = [source]
    metrics = plan['metrics'] or list(METRICS)
    unit = '만원/10a'
    out = rows[['산지연도', '대응품종']].rename(columns={'대응품종': '품종'}).copy()
    values = {m: rows[f'{m}_만원_10a'].astype(float) for m in METRICS}
    if plan['real']:
        cpi, cpi_source = cpi_series(read_source)
        missing = sorted(set(rows['산지연도']) - set(cpi.index))
        if missing:
            raise unavailable('CPI가 없는 연도라 실질 금액을 계산하지 못했습니다: ' + ', '.join(map(str, missing)))
        factor = 100 / rows['산지연도'].map(cpi).to_numpy()
        values = {m: v * factor for m, v in values.items()}
        unit = '만원/10a, 2020년 물가'
        sources.append(cpi_source)
    for metric in metrics:
        out[f'{metric}({unit})'] = values[metric].round(1).to_numpy()
    if not plan['metrics'] or '경영비' in metrics:
        out['경영비율(%)'] = (rows['경영비_원_10a'] / rows['총수입_원_10a'] * 100).round(1).to_numpy()
    several = out.groupby('산지연도')['품종'].transform('count') > 1
    rank_metric = '소득' if '소득' in metrics or not plan['metrics'] else metrics[0]
    if several.any():
        out[f'{rank_metric} 순위(큰 값=1)'] = (
            pd.Series(values[rank_metric].to_numpy(), index=out.index)
            .groupby(out['산지연도']).rank(ascending=False, method='min').astype(int))
    summary = income_summary(out, rows, values, metrics, rank_metric, unit)
    text = ('**표준소득표 조회**' + (' (CPI로 2020년 물가 기준 실질화)' if plan['real'] else '') + '\n\n' + table(out, limit=70)
            + '\n\n검산: 모든 행에서 소득 = 총수입 − 경영비, 순수익 = 총수입 − 생산비(±1원), 만원 열 = 원 열 ÷ 10,000을 확인했습니다.'
            + '\n\n' + BASIS_NOTE
            + '\n\n이 결과의 해석(품종 순위 변화·실질 소득 추세·평균 농가와의 차이)은 ‘경영비 빼면 어떤 품종이 좋아?’, '
              '‘하우스온주 소득이 왜 줄었어?’처럼 물어보면 분석 근거로 설명합니다.')
    return text, sources, summary, income_charts(out, metrics, rank_metric, unit)


def series_chart(title, frame, x, series_columns, unit, kind='line', series_name='지표'):
    """Several same-unit columns on one axis (no rescaling): long rows keyed by series."""
    data = [{x: row[x], series_name: column, '값': float(row[column]), '원래 값': float(row[column])}
            for _, row in frame.iterrows() for column in series_columns if pd.notna(row[column])]
    return {'type': 'chart', 'title': title, 'data': data, 'x': x, 'y': '값', 'series': series_name,
            'unit': unit, 'chart_kind': kind}


def income_charts(out, metrics, rank_metric, unit):
    years, varieties = out['산지연도'].nunique(), out['품종'].nunique()
    value_columns = [c for c in out.columns if c.split('(')[0] in metrics and '순위' not in c]
    if not value_columns:
        return []
    if varieties == 1 and years > 1:
        return [series_chart(f"{out['품종'].iloc[0]} 표준 농가 {'·'.join(metrics)} 추이", out, '산지연도', value_columns, unit)]
    if years == 1 and varieties > 1:
        return [series_chart(f"{int(out['산지연도'].iloc[0])}년산 품종별 {'·'.join(metrics)}", out, '품종', value_columns, unit, 'bar')]
    column = next(c for c in value_columns if c.startswith(rank_metric))
    wide = out.pivot_table(index='산지연도', columns='품종', values=column, sort=False).reset_index()
    order = [v for v in COST_VARIETIES if v in wide.columns]
    return [series_chart(f'품종별 {rank_metric} 추이' + (' (2020년 물가)' if '물가' in unit else ''), wide, '산지연도', order, unit, series_name='품종')]


def income_summary(out, rows, values, metrics, rank_metric, unit):
    years = sorted(out['산지연도'].unique())
    varieties = list(dict.fromkeys(out['품종']))
    label = rank_metric
    v = pd.Series(values[rank_metric].to_numpy(), index=out.index)
    if len(years) == 1 and len(varieties) > 1:
        best, worst = v.idxmax(), v.idxmin()
        if rank_metric in {'경영비', '생산비'}:
            return (f"{years[0]}년산 표준 농가 {josa(label, '이', '가')} 가장 큰 품종은 **{out.at[best, '품종']} {v[best]:,.1f}{unit_short(unit)}**, "
                    f"가장 작은 품종은 **{out.at[worst, '품종']} {v[worst]:,.1f}{unit_short(unit)}**입니다.")
        return (f"{years[0]}년산 표준 농가 {label} 1위는 **{out.at[best, '품종']} {v[best]:,.1f}{unit_short(unit)}**, "
                f"최하위는 **{out.at[worst, '품종']} {v[worst]:,.1f}{unit_short(unit)}**입니다 ({len(varieties)}개 품종).")
    if len(varieties) == 1 and len(years) > 1:
        first, last = out.index[0], out.index[-1]
        change = (v[last] / v[first] - 1) * 100 if v[first] > 0 else None
        text = (f"{varieties[0]} 표준 농가 {josa(label, '은', '는')} {years[0]}년산 **{v[first]:,.1f}** → {years[-1]}년산 "
                f"**{v[last]:,.1f}{unit_short(unit)}**")
        text += f" ({change:+.1f}%)입니다." if change is not None else "입니다."
        low = v.idxmin()
        if v[low] < 0:
            text += f" {', '.join(str(int(y)) for y in out.loc[v < 0, '산지연도'])}년산은 마이너스였습니다."
        return text
    if len(varieties) == 1 and len(years) == 1:
        parts = [f"{m} **{values[m].iloc[0]:,.1f}**" for m in metrics]
        return f"{years[0]}년산 {varieties[0]} 표준 농가(10a당, {unit}): " + ', '.join(parts) + '입니다.'
    leader = out.loc[v.groupby(out['산지연도']).idxmax(), ['산지연도', '품종']]
    counts = leader['품종'].value_counts()
    return (f"{years[0]}~{years[-1]}년산 표준소득표에서 {josa(label, '이', '가')} 가장 큰 해가 가장 많은 품종은 "
            f"**{counts.index[0]}({counts.iloc[0]}개 연도)**입니다. 연도별 값은 아래 표에 있습니다.")


def josa(word, with_final, without_final):
    """Pick 은/는, 이/가 from the last syllable's final consonant."""
    code = ord(word[-1]) - 0xAC00
    return word + (with_final if 0 <= code <= 11171 and code % 28 else without_final)


def unit_short(unit):
    return '만원/10a' + (' (2020년 물가)' if '물가' in unit else '')


def breakeven_lookup(plan, read_source, table, unavailable):
    frame, source = verified_standard_income(read_source)
    varieties = plan['varieties'] or ['노지온주']
    rows = select_rows(frame, varieties, plan['years'], unavailable)
    qty = rows['수량_kg_10a'].astype(float)
    out = rows[['산지연도', '대응품종']].rename(columns={'대응품종': '품종'}).copy()
    out['수량(kg/10a)'] = qty.astype(int).to_numpy()
    out['실제 단가(원/kg)'] = rows['단가_원_kg'].astype(int).to_numpy()
    cash = (rows['경영비_원_10a'] / qty).round()
    full = (rows['생산비_원_10a'] / qty).round()
    out['경영비 손익분기(원/kg)'] = cash.astype(int).to_numpy()
    out['생산비 손익분기(원/kg)'] = full.astype(int).to_numpy()
    ratio = (rows['단가_원_kg'] / (rows['생산비_원_10a'] / qty)).round(2)
    out['단가 ÷ 생산비 손익분기(배)'] = ratio.to_numpy()
    below = out.loc[ratio.to_numpy() < 1, ['산지연도', '품종']]
    first, last = out.iloc[0], out.iloc[-1]
    name = ', '.join(dict.fromkeys(out['품종']))
    if len(out) == 1:
        summary = (f"{int(first['산지연도'])}년산 {name} 표준 농가의 생산비 손익분기 단가는 **{first['생산비 손익분기(원/kg)']:,}원/kg**, "
                   f"경영비(현금 비용) 손익분기 단가는 **{first['경영비 손익분기(원/kg)']:,}원/kg**입니다. "
                   f"실제 단가 {first['실제 단가(원/kg)']:,}원/kg은 생산비 손익분기의 {first['단가 ÷ 생산비 손익분기(배)']}배입니다.")
    else:
        summary = (f"{name} 표준 농가의 생산비 손익분기 단가는 {int(first['산지연도'])}년산 **{first['생산비 손익분기(원/kg)']:,}원/kg** → "
                   f"{int(last['산지연도'])}년산 **{last['생산비 손익분기(원/kg)']:,}원/kg**입니다. "
                   f"실제 단가는 그 {ratio.min():.2f}~{ratio.max():.2f}배였습니다.")
        if not below.empty:
            summary += ' 손익분기보다 낮게 판 해: ' + ', '.join(f"{int(r.산지연도)}년산 {r.품종}" for r in below.itertuples()) + '.'
    text = ('**표준소득표 기반 손익분기 단가**\n\n' + table(out, limit=70)
            + '\n\n계산식: 경영비 손익분기 = 경영비 ÷ 수량 (이보다 싸면 현금 비용도 못 건짐), '
              '생산비 손익분기 = 생산비 ÷ 수량 (이보다 싸면 자기 노동 대가를 다 못 받음). 수량은 표준 농가 10a당 수확량입니다.'
            + '\n\n' + BASIS_NOTE
            + '\n\n제주 전체 생산량 기준의 손익분기(노지온주 약 47만 톤)는 ‘생산량이 몇 톤 넘으면 적자야?’로 물어보세요. '
              '내 농가의 판매량·단가·비용을 알려주면 가정 계산도 할 수 있습니다.')
    chart = series_chart(f"{name} 실제 단가와 손익분기 단가" if out['품종'].nunique() == 1 else '품종별 손익분기 단가',
                         out, '산지연도', ['실제 단가(원/kg)', '경영비 손익분기(원/kg)', '생산비 손익분기(원/kg)'], '원/kg')
    return text, [source], summary, [chart] if out['품종'].nunique() == 1 else []


def real_price_lookup(plan, read_source, table, unavailable):
    frame, source = read_source(PRODUCTION)
    if not {'품종', '연도', '단가_원_kg', '단가_검증'} <= set(frame):
        raise ValueError('생산 통계 열을 확인하지 못했습니다.')
    varieties = plan['varieties'] or ['노지온주']
    if len(varieties) > 1:
        raise unavailable('실질 단가는 품종 하나씩 조회합니다. 예: 노지온주 실질 단가 보여줘')
    variety = varieties[0]
    rows = frame[frame['품종'] == variety].copy()
    if rows.empty:
        raise unavailable(f'{variety} 단가 자료가 없습니다.')
    excluded = rows[rows['단가_검증'] == '확인불가']['연도'].astype(int).tolist()
    rows = rows[rows['단가_검증'] != '확인불가']
    if plan['years']:
        lacking = sorted(set(plan['years']) - set(rows['연도'].astype(int)))
        if lacking:
            raise unavailable(f'{variety} 단가가 없거나 검증되지 않은 연도입니다: ' + ', '.join(map(str, lacking)))
        rows = rows[rows['연도'].isin(plan['years'])]
    cpi, cpi_source = cpi_series(read_source)
    missing = sorted(set(rows['연도'].astype(int)) - set(cpi.index))
    if missing:
        rows = rows[~rows['연도'].isin(missing)]
    if rows.empty:
        raise unavailable('CPI와 단가가 함께 있는 연도가 없습니다.')
    rows = rows.sort_values('연도')
    real = rows['단가_원_kg'].astype(float) * 100 / rows['연도'].map(cpi).to_numpy()
    out = pd.DataFrame({'연도': rows['연도'].astype(int).to_numpy(), '품종': variety,
                        '명목 단가(원/kg)': rows['단가_원_kg'].round().astype(int).to_numpy(),
                        'CPI(2020=100)': rows['연도'].map(cpi).round(1).to_numpy(),
                        '실질 단가(원/kg, 2020년 물가)': real.round().astype(int).to_numpy(),
                        '단가 기준': rows['단가_검증'].to_numpy()})
    first, last = out.iloc[0], out.iloc[-1]
    nominal_change = (last['명목 단가(원/kg)'] / first['명목 단가(원/kg)'] - 1) * 100
    real_change = (real.iloc[-1] / real.iloc[0] - 1) * 100
    summary = (f"{variety} 단가는 {first['연도']}→{last['연도']}년 명목 **{nominal_change:+.1f}%**, "
               f"CPI로 물가를 뺀 실질 **{real_change:+.1f}%**입니다.")
    text = ('**CPI 물가 보정 단가**\n\n' + table(out, limit=40)
            + '\n\n계산식: 실질 단가 = 명목 단가 ÷ CPI(연도) × 100 (2020년 물가 기준). 단가 = 조수입 ÷ 처리량입니다.'
            + (f"\n\n단가 검증이 ‘확인불가’인 연도는 제외했습니다: {', '.join(map(str, excluded))}." if excluded else '')
            + ('\n\n‘처리량기준’ 연도는 생산량이 아닌 처리량으로 나눈 단가입니다.' if (out['단가 기준'] == '처리량기준').any() else '')
            + '\n\nCPI는 소비자 생활물가입니다. 농사 비용 물가(농가구입가격지수·품종별 경영비지수)로 보정하면 결론이 달라질 수 있습니다. '
              '분석 문서 기준 노지온주 2017→2025년 실질 단가는 CPI 기준 +16.8%, 노지 경영비지수 기준 −4.9%였습니다. '
              '자세한 설명은 ‘가격이 오른 건 물가 때문이야?’로 물어보세요.')
    chart = series_chart(f'{variety} 명목 단가와 물가 보정 단가', out, '연도',
                         ['명목 단가(원/kg)', '실질 단가(원/kg, 2020년 물가)'], '원/kg (실질은 2020년 물가)')
    return text, [source, cpi_source], summary, [chart]


def cost_result(question, read_source, table, unavailable):
    plan = plan_for(question)
    handler = {'income': income_lookup, 'breakeven': breakeven_lookup, 'real_price': real_price_lookup}[plan['kind']]
    text, sources, summary, charts = handler(plan, read_source, table, unavailable)
    return text, sources, summary, plan, charts


# Analysis cards (notebooks 03·04) get a picture drawn from the same verified files.
EXPLANATION_CHARTS = {
    'cost_income': '품종별 소득 2016년부터 2024년까지',
    'income_decomposition': '품종별 실질 소득 2016년부터 2024년까지',
    'breakeven': '노지온주 손익분기 단가',
    'inflation_real': '노지온주 실질 단가',
}


def explanation_charts(evidence_ids, limit=2):
    """Charts for analysis explanations; silently none when the local files are missing."""
    from .local_tools import ToolUnavailable, read_source, table
    charts = []
    for evidence in evidence_ids:
        if evidence not in EXPLANATION_CHARTS or len(charts) >= limit:
            continue
        plan = plan_for(EXPLANATION_CHARTS[evidence])
        if evidence in {'cost_income', 'income_decomposition'}:
            plan.update(varieties=[], years=list(range(2016, 2025)), metrics=['소득'], rank=True)
        try:
            handler = {'income': income_lookup, 'breakeven': breakeven_lookup, 'real_price': real_price_lookup}[plan['kind']]
            charts += handler(plan, read_source, table, ToolUnavailable)[3]
        except (ToolUnavailable, ValueError, KeyError, OSError):
            continue
    return charts[:limit]
