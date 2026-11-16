"""Local UI helpers: actual coverage, explicit follow-ups and readable numbers."""
from copy import deepcopy
from decimal import Decimal
import re

import pandas as pd

from . import local_tools as lt

CONTEXT_FIELDS = ('previous_request', 'scenario', 'insight_ids', 'last_metadata_question')


def snapshot_context(agent):
    return {name: deepcopy(getattr(agent, name)) for name in CONTEXT_FIELDS}


def restore_context(agent, context):
    for name in CONTEXT_FIELDS:
        setattr(agent, name, deepcopy(context.get(name)))


def availability_signature():
    signature = []
    for key, (relative, _, column) in lt.DATASETS.items():
        path = lt.ROOT / relative
        try:
            stat = path.stat()
            signature.append((key, str(path.resolve()), column, stat.st_size, stat.st_mtime_ns))
        except OSError:
            signature.append((key, str(path), column, None, None))
    return tuple(signature)


def source_availability():
    records = []
    for key, (relative, title, column) in lt.DATASETS.items():
        record = {'key': key, 'title': title, 'period': '자료 없음', 'years': [], 'variety_years': {}}
        try:
            frame, _ = lt.read_source(relative)
            if key == 'price' and column not in frame and '날짜' in frame:
                column = '날짜'
            if column not in frame:
                raise ValueError('time column missing')
            years = pd.to_numeric(frame[column].astype(str).str.extract(r'((?:19|20)\d{2})')[0], errors='coerce').dropna().astype(int)
            record['years'] = sorted(years.unique().tolist())
            if record['years']:
                record['period'] = f"{record['years'][0]}~{record['years'][-1]}년"
            else:
                record['period'] = '기간 확인 필요'
            if column in {'날짜', '일자', '연월'}:
                dates = pd.to_datetime(frame[column], errors='coerce').dropna()
                if not dates.empty:
                    fmt = '%Y-%m' if column == '연월' else '%Y-%m-%d'
                    record['period'] = dates.min().strftime(fmt) + '~' + dates.max().strftime(fmt)
            if key == 'production':
                from .repository import cleaning_rules
                cleaned = cleaning_rules(lt.ROOT).clean_fruit_production(frame)
                record['variety_years'] = {name: sorted(part['연도'].unique().tolist()) for name, part in cleaned.groupby('품종')}
            record['available'] = True
        except (OSError, ValueError, TypeError, KeyError, ImportError):
            record.update(available=False, period='파일 없음 또는 확인 필요')
        records.append(record)
    return records


def followup_context(question, agent, availability):
    if not agent.results or agent.results[-1]['question'] != question:
        return None
    record = agent.results[-1]
    conditions = record['conditions']
    if record['kind'] == 'verified_lookup':
        variety = conditions['variety']
        years = conditions.get('years', list(range(conditions['start_year'], conditions['end_year'] + 1)))
        metrics = conditions.get('metrics', ['생산량_톤'])
        metric = '생산량' if '생산량_톤' in metrics else '생산면적'
    elif record['kind'] == 'local_tool' and conditions.get('tool') in {'chart', 'join', 'relationship', 'investigate'}:
        try:
            variety = lt.variety_for(question, agent.previous_request)
        except lt.ToolUnavailable:
            return None
        years = lt.selected_years(question)
        metric = '생산량'
    else:
        return None
    source = next((r for r in availability if r['key'] == 'production' and r['available']), None)
    if not source:
        return None
    available = source['variety_years'].get(variety, [])
    years = years or available
    if not years or not set(years) <= set(available):
        return None
    anchor = max(years)
    candidates = [year for year in available if year != anchor]
    if metric == '생산면적':
        candidates = [year for year in candidates if (year < 2017) == (anchor < 2017)]
    return {'variety': variety, 'years': years, 'metric': metric, 'anchor': anchor, 'compare_years': candidates}


def chart_followup(context):
    years = context['years']
    # Use explicit years so later unrelated conversation cannot change the query.
    period = ', '.join(map(str, years)) + '년'
    return f"{period} {context['variety']} 생산량을 그래프로 보여줘"


def comparison_followup(context, year):
    if year not in context['compare_years']:
        raise ValueError('지원하는 비교 연도가 아닙니다.')
    return f"{context['anchor']}년과 {year}년 {context['variety']} {context['metric']} 비교"


def korean_number(value):
    number = Decimal(str(value).replace(',', ''))
    if not number.is_finite() or abs(number) >= Decimal('1e16'):
        return str(value)
    sign = '-' if number < 0 else ''
    number = abs(number)
    whole = int(number)
    chunks = []
    for divisor, suffix in ((10**12, '조'), (10**8, '억'), (10**4, '만')):
        count, whole = divmod(whole, divisor)
        if count:
            chunks.append(f'{count:,}{suffix}')
    remainder = Decimal(whole) + number % 1
    if remainder or not chunks:
        chunks.append(f'{remainder:,.8f}'.rstrip('0').rstrip('.'))
    return sign + ' '.join(chunks)


def number_hints(summary):
    hints = []
    for match in re.finditer(r'(?<![\d.])([+-]?\d[\d,]*(?:\.\d+)?)\s*(원/kg|톤|원|ha)', summary):
        raw, unit = match.groups()
        value = Decimal(raw.replace(',', ''))
        if abs(value) < 10000:
            continue
        hint = f'{raw}{unit} = {korean_number(value)}{unit}'
        if hint not in hints:
            hints.append(hint)
    return hints[:3]


def unit_hints(answer):
    # Encoded search URLs contain percent signs that are not percentage results.
    text = re.sub(r'https?://\S+', '', answer)
    hints = []
    if '톤' in text:
        hints.append('1톤 = 1,000kg입니다.')
    elif re.search(r'kg|킬로그램', text):
        hints.append('kg(킬로그램)은 무게를 나타내는 단위입니다.')
    if re.search(r'(?<![A-Za-z])ha(?![A-Za-z])|헥타르', text):
        hints.append('1ha = 10,000㎡로, 면적을 나타냅니다.')
    if re.search(r'원\s*/\s*kg|원_kg|kg당', text):
        hints.append('원/kg은 1kg당 가격입니다.')
    if re.search(r'원[_/]5kg|5kg당|5kg 상자', text):
        hints.append('원/5kg은 5kg 기준 가격입니다. 1kg당 가격과 구분하세요.')
    if '%' in text or '퍼센트' in text:
        hints.append('10% 증가는 100이 110으로 늘어난다는 뜻입니다.')
    if re.search(r'℃|°C|기온_c|기온_도', text):
        hints.append('℃는 기온을 나타내는 섭씨 단위입니다.')
    if re.search(r'강수량.*mm', text):
        hints.append('강수량 1mm는 비가 물 높이 1mm만큼 쌓인 양입니다.')
    return hints
