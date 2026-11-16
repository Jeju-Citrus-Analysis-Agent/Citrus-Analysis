"""Local UI helpers: actual coverage, explicit follow-ups and readable numbers."""
from copy import deepcopy
from functools import lru_cache
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


@lru_cache(maxsize=1)
def jasdc_years():
    """Years in the 2004~ citrus series that answers lookups outside the fruit table."""
    from .tools import JASDC_SOURCE
    try:
        frame, _ = lt.read_source(JASDC_SOURCE)
        return sorted(int(y) for y in pd.to_numeric(frame['연도'], errors='coerce').dropna().unique())
    except (OSError, ValueError, KeyError, lt.ToolUnavailable):
        return []


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


# Standalone questions only: a suggestion must work no matter what came before it.
EXTRA_EXAMPLES = ('2020년 천혜향 생산량 알려줘', '2019년과 2020년 한라봉 생산량 비교', '어떤 데이터가 있어?',
                  '어떤 품종이 면적당 매출이 높나?', '언제 팔면 비싼가?', '손익분기 분석 설명해줘', '물가 보정 결과 알려줘',
                  '판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 10% 하락 시 이익은?')
DEFAULT_EXAMPLES = ('2020년 천혜향 생산량 알려줘', '천혜향 생산량을 그래프로 보여줘', '어떤 데이터가 있어?')
TOPICS = {
    '생산': r'생산|수확|얼마나\s*났|많이\s*났', '면적': r'면적', '날씨': r'날씨|기온|강수|비가|더웠|추웠',
    '수출': r'수출', '가공': r'가공', '가격': r'가격|단가|시세|비싸|싸게|팔면|출하',
    '이익': r'이익|수익|손익|적자|흑자|판매량', '소득': r'소득|경영비|비용|농가', '물가': r'물가|CPI|실질',
    '그래프': r'그래프|차트|그려', '문서': r'문서', '자료': r'자료|데이터|빠진|누락|중복', '매출': r'매출|면적당',
}


def needs_examples(question, answer, agent):
    """A reply without a verified conclusion means the question could not be answered."""
    from .presentation import SUMMARY_HEADER, split_answer
    if re.search(r'보고서|리포트|/report', question):
        return False
    if answer.startswith(SUMMARY_HEADER):
        # A conclusion can still be "nothing found" for the requested condition.
        return bool(re.search(r'자료가 없습니다|찾지 못했습니다', split_answer(answer)[0]))
    conversation = next(title for key, title, _ in lt.TOOL_GUIDE if key == 'conversation')
    return not any(step.get('tool') == conversation for step in agent.last_trace)


@lru_cache(maxsize=256)
def answers(question):
    from .agent import Agent
    from .presentation import SUMMARY_HEADER
    try:
        return Agent(local_only=True).ask(question).startswith(SUMMARY_HEADER)
    except Exception:  # A suggestion that cannot run is simply not offered.
        return False


def related_examples(question, availability, limit=3):
    """Clickable questions close to what was asked, each checked to produce an answer."""
    source = next((r for r in availability if r['key'] == 'production' and r.get('available')), None)
    variety_years = source['variety_years'] if source else {}
    compact = re.sub(r'\s+', '', question)
    variety = next((name for name in sorted(variety_years, key=len, reverse=True) if name in compact), None)
    pool = [q for key, _, questions in lt.TOOL_GUIDE if key != 'web_search' for q in questions] + list(EXTRA_EXAMPLES)
    if variety:
        # Same question shapes, but about the variety the reader named.
        pool = [q.replace('천혜향', variety).replace('한라봉', variety) for q in pool] + pool
        years = variety_years[variety]
        asked = [int(y) for y in re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', question) if int(y) in years]
        year = asked[0] if asked else years[-1]
        pool.insert(0, f'{year}년 {variety} 생산량 알려줘')
    asked_topics = {name for name, pattern in TOPICS.items() if re.search(pattern, question)}

    def score(candidate):
        shared = sum(1 for name in asked_topics if re.search(TOPICS[name], candidate))
        return shared * 2 + (variety is not None and variety in candidate)

    ranked = [q for q in sorted(dict.fromkeys(pool), key=score, reverse=True) if score(q) > 0]
    chosen = []
    # Checking runs the question, so stop as soon as enough have worked.
    for candidate in ranked + [q for q in DEFAULT_EXAMPLES if q not in ranked]:
        if len(chosen) == limit:
            break
        if candidate not in chosen and answers(candidate):
            chosen.append(candidate)
    return chosen


APOLOGY = '죄송해요, 이 질문은 제가 바로 답하기 어려워요. 🍊 아래 예시 질문을 참고해 주세요.'
# Reasons worth keeping: what data exists, not instructions on how to phrase a question.
SPECIFIC_REASON = re.compile(r'(?:19|20)\d{2}\s*~\s*(?:19|20)\d{2}년산?만|자료에 없는 연도|없는 해:|파일이 없|자료가 없습니다')


def friendly_failure(answer):
    """Replace stiff 'specify the variety/year' templates with a short apology.

    The original wording stays in the agent's history; only what the reader sees changes.
    A concrete data-range reason (e.g. "레드향 표준소득표는 2020~2024년산만 있습니다") is kept.
    """
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    reasons = [line for line in lines if SPECIFIC_REASON.search(line)]
    return APOLOGY + ('\n\n' + reasons[0] if reasons else '')
