"""Descriptive comparisons with explicit baselines and no invented observations."""
import math

import pandas as pd

from .presentation import number, result_first, split_answer, SUMMARY_HEADER, DETAILS_HEADER


# Two-sided 5% critical t values by degrees of freedom (n - 2); scipy is not a dependency.
T_CRITICAL = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
              10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042}


def correlation_reading(r, n):
    """Plain-language strength of a Pearson r, and whether n years can tell it from chance."""
    df = n - 2
    critical = T_CRITICAL[max(k for k in T_CRITICAL if k <= df)] if df < 30 else 1.96
    significant = abs(r) < 1 and abs(r) * math.sqrt(df / (1 - r * r)) >= critical
    direction = '함께 늘어나는' if r > 0 else '한쪽이 늘 때 다른 쪽은 줄어드는'
    if abs(r) < .3:
        strength = '뚜렷한 관계가 보이지 않습니다'
    elif abs(r) < .7:
        strength = f'{direction} 경향이 약하게 보입니다'
    else:
        strength = f'{direction} 경향이 강하게 보입니다'
    test = (f'{n}개 연도로 확인했을 때 우연히 나온 값으로 보기 어렵습니다(5% 유의수준에서 유의).' if significant else
            f'{n}개 연도뿐이라 우연히 나온 값과 구별되지 않습니다(5% 유의수준에서 유의하지 않음).')
    return strength, test


def append_comparison(answer, summary, details):
    if not details:
        return answer
    lead, body = split_answer(answer)
    if not body:
        return answer + '\n\n**비교 분석**\n\n' + details
    lead = lead.removeprefix(SUMMARY_HEADER).strip()
    body = body.removeprefix(DETAILS_HEADER).strip()
    return result_first(lead + ('\n\n' + summary if summary else ''), body + '\n\n**비교 분석**\n\n' + details)


def difference(before, after, unit, percentage=True):
    delta = after - before
    text = f'{number(delta, True)}{"퍼센트포인트" if unit == "%" else unit}'
    if percentage:
        text += f' ({delta / before * 100:+.2f}%)' if before else ' (기준값이 0이므로 증감률 계산 안 함)'
    return text


def extrema(frame, dimension, metric, label, unit):
    if metric not in frame or dimension not in frame:
        return ''
    values = pd.to_numeric(frame[metric], errors='coerce')
    valid = values.notna() & values.map(lambda x: math.isfinite(x) if pd.notna(x) else False)
    if valid.sum() < 2:
        return ''
    part = frame.loc[valid].copy().reset_index(drop=True)
    part[metric] = values.loc[valid].to_numpy()
    high, low = part.loc[part[metric].idxmax()], part.loc[part[metric].idxmin()]
    def item(value):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
    missing = len(frame) - len(part)
    suffix = f' 빠진 값 {missing}개를 제외한 범위입니다.' if missing else ''
    if (part[metric] == high[metric]).sum() > 1 or (part[metric] == low[metric]).sum() > 1:
        suffix += ' 동률이 있으면 대표 항목 하나를 표시했습니다.'
    return (f'{label}: 확인한 범위에서 가장 높은 값은 {item(high[dimension])} **{number(high[metric])}{unit}**, '
            f'가장 낮은 값은 {item(low[dimension])} **{number(low[metric])}{unit}**입니다.' + suffix)


def merged_descriptions(frame, variety):
    notes = [extrema(frame, '연도', c, label, unit) for c, label, unit in (
        ('생산량_톤', f'{variety} 생산량', '톤'), ('연평균기온_도', '연평균 기온', '℃'), ('연강수량_mm', '연간 강수량', 'mm'))]
    for column, label in (('연평균기온_도', '기온'), ('연강수량_mm', '강수량')):
        if len(frame) >= 3 and frame[column].nunique() > 1 and frame['생산량_톤'].nunique() > 1:
            r = frame['생산량_톤'].corr(frame[column])
            if math.isfinite(r):
                notes.append(f'{len(frame)}개 연도에서 생산량과 {label}의 상관계수: **{r:.3f}** ({correlation_reading(r, len(frame))[1]})')
    return '\n\n'.join(n for n in notes if n) + '\n\n연도별 관측값의 비교이며 날씨가 원인이라는 증거가 아닙니다.'


def pair_rows(before, after, keys, metrics, before_label, after_label):
    """Pair observations one-to-one; never sum totals, components or duplicates."""
    from .local_tools import table
    if before.duplicated(keys).any() or after.duplicated(keys).any():
        return '', '같은 비교 기준에 기록이 여러 개 있어 중복을 임의로 합치지 않고 비교를 보류했습니다.'
    columns = [m[0] for m in metrics if m[0] in before and m[0] in after]
    if not columns:
        return '', '서로 같은 단위로 비교할 지표가 없습니다.'
    merged = before[keys + columns].merge(after[keys + columns], on=keys, how='inner', suffixes=('_전', '_후'), validate='one_to_one')
    if merged.empty:
        return '', f'{before_label}와 {after_label}에 공통으로 있는 비교 항목이 없습니다.'
    unmatched = len(before) + len(after) - 2 * len(merged)
    lines = [f'비교 기준: **{before_label} → {after_label}**. 공통 항목 {len(merged)}개를 짝지었습니다.']
    if unmatched:
        lines.append(f'한쪽에만 있는 {unmatched}개 항목은 제외했습니다. 없는 값을 0으로 채우지 않았습니다.')
    leads = []
    for column, label, unit, percentage in metrics:
        if column not in columns:
            continue
        a, b = (pd.to_numeric(merged[column + suffix], errors='coerce') for suffix in ('_전', '_후'))
        valid = a.notna() & b.notna() & a.map(lambda x: math.isfinite(x) if pd.notna(x) else False) & b.map(lambda x: math.isfinite(x) if pd.notna(x) else False)
        if unit != '℃':
            valid &= (a >= 0) & (b >= 0)
        if not valid.any():
            lines.append(f'{label}: 유효한 짝이 없어 계산하지 않았습니다.')
            continue
        view = merged.loc[valid, keys].copy().rename(columns={key: key.lstrip('_') for key in keys})
        view[f'{before_label} {label}({unit})'] = a[valid]
        view[f'{after_label} {label}({unit})'] = b[valid]
        view['변화량(' + ('퍼센트포인트' if unit == '%' else unit) + ')'] = b[valid] - a[valid]
        if percentage:
            view['변화율(%)'] = ((b[valid] - a[valid]) / a[valid].replace(0, float('nan')) * 100)
        lines += ['', f'**{label} 비교**', table(view), '']
        if percentage and (a[valid] == 0).any():
            lines.append('기준값이 0인 항목의 변화율은 계산하지 않았습니다.')
        if (~valid).any():
            lines.append(f'이 지표에서 빠진 값 또는 유효하지 않은 값이 있는 {(~valid).sum()}개 짝은 제외했습니다.')
        deltas = (b - a).where(valid).abs()
        index = deltas.idxmax()
        item = ' · '.join(str(int(merged.loc[index, k])) + '월' if k == '_월' else str(merged.loc[index, k]) for k in keys)
        leads.append(f'{label}의 변화 폭이 가장 큰 항목은 **{item}**이며 {difference(a[index], b[index], unit, percentage)}입니다.')
    return (f'{before_label} → {after_label} 비교: ' + ' '.join(leads[:2]) if leads else ''), '\n\n'.join(lines)


def baseline_years(selected, available):
    requested = sorted(set(selected))
    if len(requested) > 1:
        return requested[0], requested[-1]
    if not requested:
        return None
    target = requested[0]
    earlier = [year for year in available if year < target]
    later = [year for year in available if year > target]
    peer = max(earlier) if earlier else min(later) if later else None
    return tuple(sorted((target, peer))) if peer is not None else None


def data_comparison(key, frame, full, question):
    """Compare only identified units and keys for registered dataset schemas."""
    from .local_tools import selected_years
    if key == 'weather':
        return weather_comparison(frame, full)
    time_column = {'exports': '연도', 'processing': '연도', 'price': '일자' if '일자' in full else '날짜', 'monthly_price': '산지연도'}.get(key)
    if not time_column:
        return '', ''
    if key == 'monthly_price':
        part = frame[~frame['월구분'].astype(str).isin(['계', '합계', '총계', '전체'])]
        if part['품종구분'].nunique() > 1 or part['산지연도'].nunique() > 1 or part['월구분'].duplicated().any():
            return '', '월별 가격은 같은 품종·산지연도 안에서만 비교합니다. 대상을 하나로 좁혀 주세요.'
        notes = [extrema(part, '월구분', c, label, unit) for c, label, unit in (
            ('평균가_원_5kg', '월별 평균 가격', '원/5kg'), ('출하량_톤', '월별 출하량', '톤'))]
        notes = [n for n in notes if n]
        return ' '.join(notes), '\n\n'.join(notes) + '\n\n같은 산지연도·품종의 월만 비교하며 합계 행은 제외했습니다. 가격을 월별로 단순 평균하지 않았습니다.' if notes else ''
    full = full.copy()
    frame = frame.copy()
    for part in (full, frame):
        part['_연도'] = pd.to_numeric(part[time_column].astype(str).str.extract(r'((?:19|20)\d{2})')[0], errors='coerce')
    years = selected_years(question) or sorted(frame['_연도'].dropna().unique().tolist())
    pair = baseline_years(years, full['_연도'].dropna().unique())
    if not pair:
        return '', '비교할 다른 연도의 자료가 없어 추가 연도 비교를 하지 않았습니다.'
    first, last = pair
    before, after = full[full['_연도'] == first].copy(), full[full['_연도'] == last].copy()
    if key == 'exports':
        countries = set(frame['국가'].dropna()) - {'계', '합계', '총계', '전체'}
        before, after = before[before['국가'].isin(countries)], after[after['국가'].isin(countries)]
        metrics = [('수출량_톤', '수출량', '톤', True), ('수출액_천달러', '수출액', '천 달러', True)]
        lead, body = pair_rows(before, after, ['국가'], metrics, f'{int(first)}년', f'{int(last)}년')
        end = frame[frame['_연도'] == last]
        rank = extrema(end[end['국가'].isin(countries)], '국가', '수출량_톤', f'{int(last)}년 국가별 수출량', '톤') if not end['국가'].duplicated().any() else ''
        return lead, body + ('\n\n' + rank if rank else '') + '\n\n국가별 값만 비교했으며 합계 행을 합산하지 않았습니다.'
    if key == 'processing':
        before['_항목'] = after['_항목'] = '가공 처리'
        metrics = [('총처리량_톤', '총처리량', '톤', True), ('가공처리량_톤', '가공처리량', '톤', True),
                   ('가공률_퍼센트', '가공률', '%', False), ('수매단가_원_kg', '수매단가', '원/kg', True)]
        return pair_rows(before, after, ['_항목'], metrics, f'{int(first)}년', f'{int(last)}년')
    if key == 'price':
        for part in (before, after):
            part['_월일'] = pd.to_datetime(part[time_column], errors='coerce').dt.strftime('%m-%d')
        varieties = set(frame['품종'].dropna())
        days = set(pd.to_datetime(frame[time_column], errors='coerce').dt.strftime('%m-%d').dropna())
        before = before[before['품종'].isin(varieties) & before['_월일'].isin(days)]
        after = after[after['품종'].isin(varieties) & after['_월일'].isin(days)]
        channels = [channel for channel in ('도매', '직거래') if channel in question] or ['합계']
        metrics = []
        for channel in channels:
            metrics.extend([(channel + '_출하량_톤', channel + ' 출하량', '톤', True),
                            (channel + '_평균가_원_5kg', channel + ' 평균 가격', '원/5kg', True)])
        lead, body = pair_rows(before, after, ['품종', '_월일'], metrics, f'{int(first)}년', f'{int(last)}년')
        return lead, body + '\n\n같은 달력 날짜·품종·5kg 기준 가격을 비교했습니다. 요일·작황 등 조건을 통제한 인과 분석이 아니며, 날짜별 가격을 단순 평균하지 않았습니다.'
    return '', ''


def weather_comparison(frame, full):
    full = full.copy()
    dates = pd.to_datetime(full['연월'], errors='coerce')
    full['_연도'], full['_월'] = dates.dt.year, dates.dt.month
    full['_완전'] = pd.to_numeric(full['관측일수'], errors='coerce') == dates.dt.days_in_month
    stations = set(frame['지점명'].unique()) if '지점명' in frame else set()
    full = full[full['지점명'].isin(stations)] if stations else full
    months = set(pd.to_datetime(frame['연월'], errors='coerce').dt.month.dropna())
    full = full[full['_월'].isin(months)]
    years = pd.to_datetime(frame['연월'], errors='coerce').dt.year.dropna().unique()
    metrics = [('평균기온_c', '평균 기온', '℃', False), ('강수량_mm', '강수량', 'mm', True)]
    if len(stations) > 1:
        names = sorted(stations)
        selected_dates = set(frame['연월'])
        subset = full[full['연월'].isin(selected_dates) & full['_완전']]
        leads, bodies = [], []
        for station in names[1:]:
            lead, body = pair_rows(subset[subset['지점명'] == names[0]], subset[subset['지점명'] == station],
                                   ['연월'], metrics, names[0], station)
            leads.append(lead)
            bodies.append(body)
        return ' '.join(leads[:1]), '\n\n'.join(bodies) + '\n\n같은 월·완전 관측 월만 비교했습니다. 기온은 ℃ 차이로 비교하며 증감률을 계산하지 않습니다.'
    pair = baseline_years(years, full['_연도'].dropna().unique())
    if not pair:
        return '', '비교할 다른 연도의 월별 날씨가 없습니다.'
    first, last = pair
    before, after = full[(full['_연도'] == first) & full['_완전']], full[(full['_연도'] == last) & full['_완전']]
    lead, body = pair_rows(before, after, ['지점명', '_월'], metrics, f'{int(first)}년', f'{int(last)}년')
    incomplete = int((full['_연도'].isin(pair) & ~full['_완전']).sum())
    body += '\n\n계절 차이를 줄이기 위해 같은 월끼리 비교했습니다. 기온은 ℃ 차이만 계산하며 기온의 증감률은 계산하지 않습니다.'
    if incomplete:
        body += f' 관측일이 부족한 {incomplete}개 월은 비교에서 제외했습니다.'
    return lead, body


def lookup_comparison(data, request):
    """Add an independently verified neighbouring year without changing context."""
    from .tools import production, ROOT, cleaning_rules
    from .guardrails import validate_evidence
    rows = validate_evidence(data, request)
    years = request.get('years', list(range(request['start_year'], request['end_year'] + 1)))
    if len(years) != 1 or len(rows) != 1:
        return '', ''
    year = years[0]
    raw = pd.read_csv(ROOT / 'data/raw/public/fruit_production.csv', encoding='utf-8-sig')
    cleaned = cleaning_rules(ROOT).clean_fruit_production(raw)
    available = cleaned.loc[cleaned['품종'] == request['variety'], '연도'].unique()
    metrics = request.get('metrics', ['생산량_톤'])
    if '생산면적_ha' in metrics and '생산량_톤' not in metrics:
        available = [candidate for candidate in available if (candidate < 2017) == (year < 2017)]
    pair = baseline_years([year], available)
    if not pair:
        return '', '추가로 비교할 연도가 없습니다.'
    peer = int(pair[0] if pair[1] == year else pair[1])
    evidence = production(request['variety'], peer, peer)
    peer_rows = validate_evidence(evidence, evidence['request'])
    if len(peer_rows) != 1 or evidence['source_sha256'] != data['source_sha256']:
        return '', '원자료 버전 또는 비교 연도의 값을 확인하지 못해 추가 비교를 보류했습니다.'
    current, other = rows[0], peer_rows[0]
    first, last = (other, current) if peer < year else (current, other)
    notes = []
    for metric in request.get('metrics', ['생산량_톤']):
        unit, label = ('ha', '생산면적') if metric == '생산면적_ha' else ('톤', '생산량')
        if metric == '생산면적_ha' and first['연도'] < 2017 <= last['연도']:
            notes.append('면적은 2017년 통계 단절을 넘으므로 추가 증감 비교를 하지 않았습니다.')
            continue
        a, b = first[metric], last[metric]
        if a is None or b is None:
            notes.append(f'{label}에 빠진 값이 있어 추가 비교를 하지 않았습니다.')
            continue
        from .guardrails import display_name
        notes.append(f"{display_name(request['variety'])} {label}을 추가 비교하면 **{first['연도']}년 {number(a)}{unit} → {last['연도']}년 {number(b)}{unit}**, 변화는 **{difference(a, b, unit)}**입니다.")
    body = '\n\n'.join(notes)
    return ' '.join(notes[:2]), f'요청 연도 외에 자료가 있는 가까운 연도를 기준으로 추가 비교했습니다.\n\n{body}' if body else ''
