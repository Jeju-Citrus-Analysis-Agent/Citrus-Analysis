"""Keyless tools. Read only registered files; never execute user code or URLs."""
import calendar
import hashlib
import io
import math
from numbers import Integral
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import pandas as pd
import requests

from .tools import ROOT, production
from .scenarios import parse_scenario, compute, fmt
from .presentation import result_first
from .sources import source_citation

TOOL_GUIDE = (
    ('conversation', '인사와 쉬운 설명', ('안녕', '생산량과 출하량은 뭐가 달라?')),
    ('data_query', '여러 자료 보기', ('2020년 제주 날씨 보여줘', '2020년 수출 자료 보여줘')),
    ('chart', '그래프 그리기', ('천혜향 생산량을 그래프로 보여줘', '한라봉 생산량 그래프 그려줘')),
    ('quality', '자료 문제 확인', ('생산량 자료에 빠진 값이 있어?', '날씨 자료에 중복이 있어?')),
    ('join', '자료를 한 표로 보기', ('천혜향 생산량과 기온을 한 표로 보여줘', '한라봉 생산량과 강수량을 같이 보여줘')),
    ('document_search', '문서에서 찾기', ('문서에서 2017년 면적을 찾아줘', '문서에서 출하 시기를 찾아줘')),
    ('web_search', '인터넷 자료 찾기', ('인터넷에서 감귤 통계 찾아줘', '인터넷에서 감귤 출하 자료 찾아줘')),
    ('relationship', '날씨와 생산량 비교', ('기온과 천혜향 생산량은 관계가 있어?', '강수량과 한라봉 생산량은 관계가 있어?')),
    ('sensitivity', '가격별 이익 비교', (
        '가격이 내려갈 때 이익을 예시로 보여줘',
        '가격이 오를 때 이익을 예시로 보여줘')),
    ('investigate', '차례대로 살펴보기', ('천혜향 생산량을 차례대로 살펴봐줘', '한라봉 생산량을 순서대로 확인해줘')),
    ('cost', '경영비·소득·손익분기 조회', ('2024년산 품종별 소득 비교해줘', '노지온주 손익분기 단가 보여줘')),
)

# Every file is explicitly registered. Arbitrary paths and expressions are rejected.
DATASETS = {
    'production': ('data/raw/public/fruit_production.csv', '과수 생산량', '기준연도'),
    'weather': ('data/processed/weather_monthly.csv', '월별 날씨', '연월'),
    'exports': ('data/processed/citrus_export_yearly.csv', '국가별 수출', '연도'),
    'processing': ('data/processed/citrus_processing_yearly.csv', '가공 처리량', '연도'),
    'price': ('data/processed/citrus_price_daily.csv', '일별 출하·가격', '일자'),
    'monthly_price': ('data/processed/noji_monthly_2025.csv', '2025년산 월별 출하·가격', '산지연도'),
}


# 제주농산물수급관리센터에서 받은 자료와 그로부터 만든 파일 (이용약관상 저장소·제출본에서 제외).
JASDC_DERIVED = re.compile(r'citrus_[a-z_]+\.csv|noji_[a-z0-9_]+\.csv|varieties_summary|external/cost/')


class ToolUnavailable(ValueError):
    """A user-readable explanation of a missing condition or unusable source."""


def table(frame, limit=20):
    # Only year columns print 2024 as "2024"; a price of 2,024원/kg must keep its comma.
    year_columns = {c for c in frame.columns if re.search('연도|산지|시즌|^년$|^연$', str(c))}

    def cell(value, column):
        if pd.isna(value):
            return '없음'
        if isinstance(value, float):
            return f'{value:,.2f}'.rstrip('0').rstrip('.')
        if isinstance(value, Integral):
            return str(value) if column in year_columns and 1900 <= value <= 2100 else f'{value:,}'
        return str(value).replace('|', ' / ').replace('\n', ' ').replace('<', '&lt;').replace('>', '&gt;')
    names = {'생산량_톤': '생산량(톤)', '연평균기온_도': '연평균 기온(℃)', '연강수량_mm': '연간 강수량(mm)',
             '수출량_톤': '수출량(톤)', '수출액_천달러': '수출액(천 달러)', '연월': '월', '관측일수': '관측일 수',
             '평균기온_c': '평균 기온(℃)', '강수량_mm': '강수량(mm)'}
    columns = [names.get(c, c) for c in frame.columns]
    lines = ['| ' + ' | '.join(map(str, columns)) + ' |', '|' + '---|' * len(columns)]
    lines.extend('| ' + ' | '.join(cell(v, c) for v, c in zip(row, frame.columns)) + ' |'
                 for row in frame.head(limit).itertuples(index=False, name=None))
    if len(frame) > limit:
        lines.append(f'전체 {len(frame):,}행 중 앞의 {limit}행입니다. 연도나 지역을 지정하면 범위를 줄일 수 있습니다.')
    return '\n'.join(lines)


def read_source(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ToolUnavailable('등록된 자료만 읽을 수 있습니다.')
    if not path.is_file():
        message = f'필요한 자료가 없습니다: {relative}.'
        if JASDC_DERIVED.search(str(relative)):
            # Kept out of the repository and the submission archive under the centre's terms.
            message += (' 제주농산물수급관리센터 자료는 이용약관상 함께 배포하지 않습니다.'
                        ' 실행 매뉴얼의 「데이터 준비」 절차로 받은 뒤 다시 질문해 주세요.')
        raise ToolUnavailable(message)
    raw = path.read_bytes()
    try:
        frame = pd.read_csv(io.BytesIO(raw), encoding='utf-8-sig')
    except (ValueError, UnicodeError):
        raise ToolUnavailable('자료를 읽지 못했습니다. CSV 형식을 확인해 주세요.') from None
    return frame, {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}


def dataset_for(question):
    if re.search('날씨|기온|강수|기상', question):
        return 'weather'
    if '수출' in question:
        return 'exports'
    if '가공' in question:
        return 'processing'
    if re.search('월별|월마다', question) and re.search('가격|출하', question):
        return 'monthly_price'
    if re.search('가격|시세|출하', question):
        return 'price'
    return 'production'


def selected_years(question):
    years = sorted(set(map(int, re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', question))))
    if len(years) == 2 and re.search('부터|까지|~|～', question):
        return list(range(years[0], years[1] + 1))
    return years


def variety_for(question, previous=None):
    from .analysis import categories
    from .guardrails import ALIASES
    compact = re.sub(r'\s+', '', question)
    # Readers say 노지온주; the source table says 온주밀감노지. Longest match first.
    names = {alias: name for name in categories() for alias in ALIASES.get(name, (name,))}
    found, rest = [], compact
    for alias in sorted(names, key=len, reverse=True):
        if alias in rest:
            found.append(names[alias])
            rest = rest.replace(alias, ' ')
    found = list(dict.fromkeys(found))
    if len(found) > 1:
        raise ToolUnavailable('이 기능은 품종 하나씩 확인합니다. 한라봉 또는 천혜향처럼 하나를 적어 주세요.')
    if found:
        return found[0]
    if previous:
        return previous['variety']
    raise ToolUnavailable('살펴볼 품종을 알려주세요. 예: 천혜향 생산량을 그래프로 보여줘')


def select_frame(question):
    key = dataset_for(question)
    relative, title, time_column = DATASETS[key]
    frame, source = read_source(relative)
    if key == 'price' and time_column not in frame and '날짜' in frame:
        time_column = '날짜'
    years = selected_years(question)
    if years:
        observed = pd.to_numeric(frame[time_column].astype(str).str.extract(r'((?:19|20)\d{2})')[0], errors='coerce')
        missing = set(years) - set(observed.dropna().astype(int))
        if missing:
            raise ToolUnavailable('자료에 없는 연도입니다: ' + ', '.join(map(str, sorted(missing))) + '. 다른 연도를 지정해 주세요.')
        frame = frame[observed.isin(years)]
    if key == 'weather':
        stations = [s for s in ('서귀포', '성산', '고산', '제주') if s in question] or ['제주']
        frame = frame[frame['지점명'].isin(stations)]
        title += f' · {"·".join(stations)} 관측소 (제주 전체 평균 아님)'
        frame = frame[['지점명', '연월', '관측일수', '평균기온_c', '강수량_mm']]
    if key == 'exports':
        # Match actual country labels, never aggregate totals and component rows.
        countries = [c for c in frame['국가'].dropna().unique() if str(c) in question]
        if countries:
            frame = frame[frame['국가'].isin(countries)]
    months = [int(m) for m in re.findall(r'(?<!\d)(\d+)\s*월', question)]
    if months and key in {'weather', 'price', 'monthly_price'}:
        if any(not 1 <= m <= 12 for m in months):
            raise ToolUnavailable('월은 1월부터 12월까지로 알려주세요.')
        if key == 'monthly_price':
            observed_months = pd.to_numeric(frame['월구분'].astype(str).str.extract(r'(\d+)')[0], errors='coerce')
        else:
            observed_months = pd.to_datetime(frame[time_column], errors='coerce').dt.month
        frame = frame[observed_months.isin(months)]
    if frame.empty:
        raise ToolUnavailable('지정한 조건의 자료가 없습니다.')
    return frame, source, title


def production_frame(question, previous=None):
    variety = variety_for(question, previous)
    years = selected_years(question) or list(range(2015, 2021))
    from .tools import JASDC_NAMES
    if not set(years) <= set(range(2015, 2021)):
        # Outside 2015~2020 the 제주농산물수급관리센터 series (2004~2025) answers citrus varieties.
        if variety not in JASDC_NAMES:
            raise ToolUnavailable(f'{variety}는 2015~2020년 자료만 있습니다. 이 기간으로 질문해 주세요.')
        if not set(years) <= set(range(2004, 2026)):
            raise ToolUnavailable('감귤 품종 생산량은 2004~2025년 자료가 있습니다. 이 기간으로 질문해 주세요.')
    result = production(variety, min(years), max(years))
    if result['missing_years']:
        raise ToolUnavailable('빠진 연도가 있어 분석을 보류했습니다.')
    from .guardrails import validate_evidence
    # Reuse the independent source/Decimal audit, not model-generated figures.
    validate_evidence(result, result['request'])
    frame = pd.DataFrame(result['rows'])
    frame = frame[frame['연도'].isin(years)]
    if frame.empty or frame['생산량_톤'].isna().any():
        raise ToolUnavailable('생산량에 빠진 값이 있어 분석을 보류했습니다.')
    source = {'path': result['source'], 'sha256': result['source_sha256']}
    return frame[['연도', '생산량_톤']].copy(), variety, source


def annual_weather(years):
    frame, source = read_source('data/processed/weather_daily.csv')
    dates = pd.to_datetime(frame['일자'], errors='coerce')
    frame = frame[(frame['지점명'] == '제주') & dates.dt.year.isin(years)].copy()
    frame['年'] = pd.to_datetime(frame['일자']).dt.year
    if frame['일자'].duplicated().any():
        raise ToolUnavailable('제주 관측소의 날짜가 중복되어 자료 결합을 보류했습니다.')
    rows = []
    for year in years:
        part = frame[frame['年'] == year]
        expected = 366 if calendar.isleap(year) else 365
        if len(part) != expected or part[['평균기온_c', '강수량_mm']].isna().any().any():
            raise ToolUnavailable(f'{year}년 날씨의 일별 관측이 완전하지 않아 비교를 보류했습니다.')
        if not all(math.isfinite(float(v)) for v in part[['평균기온_c', '강수량_mm']].to_numpy().flat):
            raise ToolUnavailable(f'{year}년 날씨에 유효하지 않은 값이 있습니다.')
        rows.append({'연도': year, '연평균기온_도': part['평균기온_c'].mean(), '연강수량_mm': part['강수량_mm'].sum()})
    return pd.DataFrame(rows), source


def merged_frame(question, previous=None):
    fruit, variety, source = production_frame(question, previous)
    weather, weather_source = annual_weather(fruit['연도'].tolist())
    merged = fruit.merge(weather, on='연도', validate='one_to_one')
    if len(merged) != len(fruit):
        raise ToolUnavailable('공통 연도가 부족해 자료 결합을 보류했습니다.')
    return merged, variety, [source, weather_source]


def result(text, sources=(), artifacts=(), validation='등록된 로컬 파일의 값·단위·기간 확인', summary=None):
    return {'text': text, 'sources': list(sources), 'artifacts': list(artifacts), 'validation': validation, 'summary': summary}


def trend_summary(frame, variety):
    first, last = frame.iloc[0], frame.iloc[-1]
    if len(frame) == 1:
        return f"{int(last['연도'])}년 {variety} 생산량은 **{last['생산량_톤']:,.0f}톤**입니다."
    delta = last['생산량_톤'] - first['생산량_톤']
    change = f"{delta:+,.0f}톤" + (f" ({delta / first['생산량_톤'] * 100:+.2f}%)" if first['생산량_톤'] else '')
    return (f"{variety} 생산량은 {int(first['연도'])}년 **{first['생산량_톤']:,.0f}톤**에서 "
            f"{int(last['연도'])}년 **{last['생산량_톤']:,.0f}톤**으로 변했습니다. 변화량은 **{change}**입니다.")


def chart_result(question, previous=None):
    if re.search('면적|가격|출하량', question):
        raise ToolUnavailable('현재 그래프는 품종별 생산량을 지원합니다. 예: 천혜향 생산량을 그래프로 보여줘')
    frame, variety, source = production_frame(question, previous)
    from .guardrails import display_name
    variety = display_name(variety)
    artifact = {'type': 'chart', 'title': f'{variety} 생산량 변화', 'data': frame.to_dict('records'),
                'x': '연도', 'y': '생산량_톤', 'unit': '톤'}
    from .comparisons import extrema
    comparison = extrema(frame, '연도', '생산량_톤', f'{variety} 연도별 생산량', '톤')
    details = f'**{variety} 생산량 그래프**\n\n' + table(frame) + '\n\n세로축은 생산량(톤)입니다.'
    if comparison:
        details += '\n\n**비교 분석**\n\n' + comparison
    return result(details, [source], [artifact], '원자료 독립 대조를 통과한 생산량', trend_summary(frame, variety))


def quality_result(question):
    key = dataset_for(question)
    relative, title, _ = DATASETS[key]
    frame, source = read_source(relative)
    blanks = frame.isna().sum()
    details = pd.DataFrame([{'항목': c, '빠진 값 수': int(v)} for c, v in blanks.items() if v])
    text = (f'**{title} 자료 점검**\n\n- 전체: {len(frame):,}행\n'
            f'- 내용이 완전히 같은 중복: {int(frame.duplicated().sum()):,}행\n'
            f'- 빠진 값: {int(blanks.sum()):,}칸\n')
    if not details.empty:
        text += '\n' + table(details)
    keys = {'production': ['기준연도', '품종대분류', '품종소분류'], 'weather': ['지점코드', '연월'],
            'exports': ['연도', '국가'], 'processing': ['연도'], 'price': ['품종', '일자' if '일자' in frame else '날짜'],
            'monthly_price': ['품종구분', '산지연도', '월구분']}[key]
    duplicate_keys = int(frame.duplicated(keys, keep=False).sum()) if all(k in frame for k in keys) else None
    if duplicate_keys is not None:
        text += f'\n\n같은 기준의 기록이 여러 번 나온 행: {duplicate_keys:,}행'
    flags = []
    for column in frame.columns:
        if column in keys or re.search('코드|연도|연월|날짜', column):
            continue
        values = pd.to_numeric(frame[column].astype(str).str.replace(',', '', regex=False), errors='coerce').dropna()
        if len(values) < 8:
            continue
        low, high = values.quantile([.25, .75])
        width = high - low
        if width > 0:
            count = int(((values < low - 1.5 * width) | (values > high + 1.5 * width)).sum())
            if count:
                flags.append({'항목': column, '눈에 띄는 값 수': count})
    if flags:
        text += '\n\n다른 값들과 차이가 커서 살펴볼 항목(IQR 기준):\n\n' + table(pd.DataFrame(flags))
    text += '\n\n빠진 값이나 눈에 띄는 값이 모두 오류라는 뜻은 아닙니다. 계절·품종 차이나 관측하지 않는 항목일 수 있습니다. 자료는 수정하지 않았습니다.'
    summary = (f"{title} {len(frame):,}행을 확인했습니다. **빠진 값 {int(blanks.sum()):,}칸, 완전히 같은 중복 {int(frame.duplicated().sum()):,}행**입니다. "
               '검사한 값이 모두 정확하다는 뜻은 아닙니다.')
    if duplicate_keys:
        summary += f' 같은 기준으로 여러 번 기록된 행 {duplicate_keys:,}개도 확인이 필요합니다.'
    if flags:
        summary += f' 수치 차이가 커서 추가로 살펴볼 항목은 {len(flags)}개입니다.'
    return result(text, [source], validation='전체 행의 결측·완전 중복·기준 키 중복·IQR 후보 검사 (정확성 전체 보증 아님)', summary=summary)


def document_result(question):
    terms = re.sub(r'문서에서|문서|찾아\s*줘|검색해\s*줘|알려\s*줘|에\s*대해', ' ', question)
    # '시기를' must match '시기': drop a trailing particle when a word remains.
    terms = [re.sub(r'(?<=[가-힣]{2})(?:에서|으로|을|를|이|가|은|는|에|의|로|와|과)$', '', t)
             for t in re.findall(r'[가-힣A-Za-z0-9_]{2,}', terms)]
    terms = [t for t in dict.fromkeys(terms) if t not in {'내용', '자료'}]
    if not terms:
        raise ToolUnavailable('찾을 내용을 알려주세요. 예: 문서에서 2017년 면적을 찾아줘')
    paths = [ROOT / 'README.md'] + sorted((ROOT / 'docs').rglob('*.md'))
    paths += sorted((Path(__file__).parent / 'knowledge/sources').glob('*.md'))
    hits = []
    sources = {}
    for path in paths[:150]:
        if not path.resolve().is_relative_to(ROOT.resolve()) or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig', errors='replace')
        relative = path.relative_to(ROOT).as_posix()
        in_code = False
        for line_no, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith('```'):
                in_code = not in_code
            if in_code or line.lstrip().startswith('```'):
                continue  # Folder trees and code are not readable answers.
            snippet = plain_line(line)
            score = relevance(snippet, terms)
            if score and re.match(r'\s*(?:#|[-*]\s*\[[ xX]\])', line):
                score -= 50  # Headings and to-do items name a topic; body lines answer it.
            if score and re.fullmatch(r'[\d.]+\s.*', snippet) and len(snippet) < 40:
                score -= 50  # Numbered section titles such as '2.2 2017년 재배면적 단절'.
            if score and snippet:
                hits.append((score, relative, line_no, snippet[:350]))
                sources[relative] = {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}
    hits.sort(key=lambda h: (-h[0], h[1], h[2]))
    if not hits:
        return result('문서에서 찾지 못했습니다. 검색어를 짧게 바꿔 보세요.', validation='등록된 공개 Markdown 문서 검색')
    chosen = hits[:5]
    text = '**문서에서 찾아온 결과**\n\n' + '\n\n'.join(
        f'- {snippet.replace(chr(60), "&lt;")}\n\n  (위치: {path} {line}번째 줄)' for _, path, line, snippet in chosen)
    text += '\n\n문서의 해당 문장을 발췌했습니다. 최신 통계나 내용의 정확성을 새로 검증한 결과는 아닙니다.'
    return result(text, [sources[p] for p in dict.fromkeys(h[1] for h in chosen)], validation='공개 문서의 실제 문장·파일 버전 확인',
                  summary=f'문서에서 찾아온 결과, 가장 관련 있는 내용은 다음과 같습니다.\n\n> {chosen[0][3].replace(chr(60), "&lt;")}\n\n'
                          f'관련 문장은 모두 **{len(chosen)}개**입니다. 문서의 내용이며 최신 정보인지 별도 확인이 필요합니다.')


def relevance(line, terms):
    """More matched terms first; then terms that sit together; then shorter, more focused lines."""
    lower = line.lower()
    found = [lower.find(t.lower()) for t in terms if t.lower() in lower]
    if not found:
        return 0
    close = len(found) > 1 and max(found) - min(found) <= 20
    return len(found) * 100 + (30 if close else 0) - min(len(line), 300) / 30


def plain_line(line):
    """Markdown table/heading markers read as noise once a line is quoted alone."""
    line = line.strip()
    if re.fullmatch(r'\|?[\s:|-]*', line):
        return ''
    if line.startswith('|'):
        line = ' · '.join(cell.strip() for cell in line.strip('|').split('|') if cell.strip())
    line = re.sub(r'^(?:#{1,6}|>|[-*+])\s+', '', line)
    return re.sub(r'^\[[ xX]\]\s*', '', line).replace('`', '').strip()


OFFICIAL_HOSTS = ('kosis.kr', 'jeju.go.kr', 'kma.go.kr', 'data.go.kr', 'mafra.go.kr', 'kamis.or.kr', 'at.or.kr')


def web_result(question):
    query = re.sub(r'인터넷에서|인터넷|찾아\s*줘|검색해\s*줘', ' ', question).strip()[:160]
    if not re.search('감귤|귤|농업|출하|생산|기상', query):
        raise ToolUnavailable('감귤·농업 관련 검색어를 적어 주세요. 예: 인터넷에서 감귤 통계 찾아줘')
    query += ' (' + ' OR '.join('site:' + host for host in OFFICIAL_HOSTS) + ')'
    try:
        response = requests.get('https://www.bing.com/search', params={'q': query, 'format': 'rss'},
                                timeout=(3, 8), allow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 1_000_000:
            raise ValueError('too large')
        root = ET.fromstring(response.content)
        found = []
        for item in root.findall('.//item'):
            link = item.findtext('link', '')
            parsed = urlparse(link)
            if parsed.hostname in {'www.bing.com', 'bing.com'}:
                candidate = parse_qs(parsed.query).get('url', [''])[0]
                if candidate:
                    link, parsed = candidate, urlparse(candidate)
            host = parsed.hostname or ''
            if parsed.scheme != 'https' or parsed.username or parsed.password:
                continue
            if not any(host == h or host.endswith('.' + h) for h in OFFICIAL_HOSTS):
                continue
            if link not in [v[1] for v in found]:
                title = item.findtext('title', '공공기관 자료').replace('[', '').replace(']', '')[:150]
                found.append((title, link))
        if found:
            return result('**인터넷에서 찾은 공공기관 자료**\n\n' + '\n'.join(f'- [{t}]({u})' for t, u in found[:5])
                          + '\n\n검색 결과의 링크입니다. 원문에서 발표일과 통계 기준을 확인해 주세요.',
                          [{'url': u} for _, u in found[:5]], validation='공공기관 도메인 확인; 원문 수치 미검증',
                          summary=f'공공기관 자료 링크 **{len(found[:5])}개**를 찾았습니다. 발표일과 통계 값은 원문에서 확인해 주세요.')
        status = '현재 검색 결과에서 조건에 맞는 공공기관 자료를 찾지 못했습니다.'
    except (requests.RequestException, ValueError, ET.ParseError):
        status = '인터넷 검색에 연결하지 못했습니다. 인터넷 연결 상태를 확인해 주세요.'
    links = '\n'.join(f'- [{host}에서 검색](https://www.google.com/search?{urlencode({"q": query.split(" (")[0] + " site:" + host})})'
                      for host in OFFICIAL_HOSTS[:3])
    response = result(status + '\n\n대신 아래 검색 링크를 직접 열 수 있습니다.\n\n' + links,
                      validation='자동 검색 실패; 직접 검색 링크만 제공 (검색 결과 아님)',
                      summary=status + ' 직접 열 수 있는 검색 링크를 아래에 준비했습니다.')
    response['success'] = False
    return response


def relationship_result(question, previous=None):
    frame, variety, sources = merged_frame(question, previous)
    if len(frame) < 3:
        raise ToolUnavailable('관계를 비교하려면 공통 연도가 3개 이상 필요합니다. 예: 2015~2020년 천혜향 생산량과 기온은 관계가 있어?')
    weather_col = '연강수량_mm' if re.search('비가|강수|비와', question) else '연평균기온_도'
    if frame['생산량_톤'].nunique() < 2 or frame[weather_col].nunique() < 2:
        raise ToolUnavailable('값의 변화가 없어 상관계수를 계산할 수 없습니다.')
    r = frame['생산량_톤'].corr(frame[weather_col])
    from .comparisons import merged_descriptions, correlation_reading
    reading, test = correlation_reading(r, len(frame))
    weather = '강수량' if weather_col == '연강수량_mm' else '기온'
    text = (f'**{variety} 생산량과 {weather} 비교**\n\n{table(frame)}\n\n'
            f'- 비교한 연도: {len(frame)}개\n- 상관계수: {r:.3f} (-1~1 범위, 0에 가까울수록 관계가 없음)\n'
            f'- 판단: {reading}. {test}\n\n'
            '연도가 적고 다른 조건을 통제하지 않았습니다. 상관이 있더라도 날씨가 생산량 변화의 원인이라는 뜻은 아닙니다. '
            '제주 관측소의 달력 연도 자료이며 제주 전체 평균이나 재배 시기별 분석이 아닙니다.')
    text += '\n\n**비교 분석**\n\n' + merged_descriptions(frame, variety)
    return result(text, sources, validation='연도 1:1 결합·관측일 완전성·Pearson 상관 계산 (인과 분석 아님)',
                  summary=f'{variety} 생산량과 {weather} 사이에는 **{reading}**. 상관계수는 **{r:.3f}**이고, {test} '
                          f'제주 관측소 자료와 비교했으며, **날씨가 원인이라는 뜻은 아닙니다.**')


def sensitivity_result(question, previous=None):
    example = '예시' in question
    if example:
        direction = '내려가면' if re.search('내려|하락|떨어', question) else '오르면'
        question = '판매량 1000kg, 단가 4000원, 총비용 300만원일 때 가격이 10%, 20%, 30% ' + direction
        previous = None
    if re.search(r'-\s*\d+(?:\.\d+)?\s*%', question):
        raise ToolUnavailable('변동률은 양수로 적고 오르거나 내리는 방향을 알려주세요.')
    if not re.search(r'(?:가격|단가)(?:이|가|는|은)?\s*\d+(?:\.\d+)?\s*%', question):
        raise ToolUnavailable('여러 조건 비교는 가격 변동을 지원합니다. 예: 가격이 10%, 20% 내려가면?')
    rates = sorted(set(re.findall(r'(\d+(?:\.\d+)?)\s*%', question)))
    if not 2 <= len(rates) <= 10:
        raise ToolUnavailable('비교할 변동률을 2~10개 적어 주세요. 예: 가격이 10%, 20%, 30% 내려가면?')
    up = bool(re.search('오르|올라|상승|인상', question))
    down = bool(re.search('내려|하락|떨어|인하', question))
    if up == down:
        raise ToolUnavailable('가격이 오르는지 내려가는지 알려주세요.')
    clean = re.sub(r'\d+(?:\.\d+)?\s*%', '', question)
    plan, blocked = parse_scenario(clean, previous)
    if blocked or plan is None:
        raise ToolUnavailable(blocked or '판매량, 단가, 총비용을 함께 적어 주세요.')
    plan['changes'] = {}
    if plan['price_won_kg'] is None:
        raise ToolUnavailable('비교 기준 단가를 원/kg으로 알려주세요.')
    rows = []
    for rate in [0] + sorted(map(float, rates)):
        changed = dict(plan, changes={'price_won_kg': str(rate if up else -rate)})
        value = compute(changed)
        rows.append({'가격 변화(%)': rate if up else -rate, '단가(원/kg)': float(value['changed']['price_won_kg']),
                     '매출(원)': float(value['after']['revenue']), '이익(원)' if plan['cost_basis'] == 'total' else '경영비 차감 잔여액(원)': float(value['after']['profit'])})
        rows[-1]['기준 대비 잔여액 차이(원)'] = float(value['after']['profit'] - value['before']['profit'])
    text = ('**가격이 달라질 때의 계산**\n\n' + ('연습용 예시입니다. 아래 수량·가격·비용은 실제 사용자 실적이 아닙니다.\n\n' if example else '')
            + f'판매량 {fmt(compute(plan)["base"]["quantity_kg"])}kg, 비용 {fmt(compute(plan)["base"]["cost_won"])}원을 고정했습니다.\n\n'
            + table(pd.DataFrame(rows)) + '\n\n입력 가정에 따른 계산이며 미래 가격·실제 농가 이익의 예측이 아닙니다. 변동률은 최초 단가에 각각 적용했습니다.')
    profit_label = '이익' if plan['cost_basis'] == 'total' else '경영비 차감 잔여액'
    summary = ('연습용 예시 가정에서 ' if example else '입력한 가정에서 ') + ', '.join(
        f"가격 {abs(row['가격 변화(%)']):g}% {'상승' if up else '하락'} 시 **{fmt(row[profit_label + '(원)'])}원**" for row in rows[1:4])
    summary += f'의 {profit_label}이 계산됩니다. 판매량·비용을 고정한 계산이며 미래 예측이 아닙니다.'
    if len(rows) > 4:
        summary += ' 나머지 조건은 아래 표에서 확인하세요.'
    response = result(text, [{'type': 'user_assumptions'}], validation='Decimal 매출·이익 검산; 최초 단가 기준 비교', summary=summary)
    response['scenario'] = plan
    return response


def investigate_result(question, previous=None):
    frame, variety, source = production_frame(question, previous)
    if len(frame) < 2:
        raise ToolUnavailable('변화를 살펴보려면 연도 두 개 이상이 필요합니다.')
    differences = frame['생산량_톤'].diff()
    falling = frame.loc[differences < 0, '연도'].tolist()
    text = (f'**{variety} 생산량을 차례대로 살펴봤습니다.**\n\n'
            '1. 원자료를 별도로 대조해 조회 값과 누락 연도를 확인했습니다.\n'
            '2. 연도별 생산량을 비교했습니다.\n\n' + table(frame)
            + '\n\n3. 바로 앞에 표시한 연도보다 감소한 해: ' + (', '.join(map(str, falling)) if falling else '없음') + '\n')
    sources = [source]
    trace = ['원자료 대조와 누락 확인', '연도별 생산량 계산', '감소한 해 확인']
    # A fixed, inspectable plan; never claim autonomous causal discovery.
    try:
        weather, weather_source = annual_weather(frame['연도'].tolist())
        merged = frame.merge(weather, on='연도', validate='one_to_one')
        text += '\n4. 같은 연도의 제주 관측소 날씨를 함께 확인했습니다.\n\n' + table(merged)
        sources.append(weather_source)
        trace.append('제주 관측소 연도별 날씨 결합')
    except ToolUnavailable as exc:
        text += '\n4. 날씨 비교 보류: ' + str(exc)
        trace.append('날씨 자료 부족으로 비교 보류')
    text += '\n\n정해진 점검 순서로 조사한 결과입니다. 감소 원인은 확정하지 않았습니다. 재배면적·병해충·출하 조건 등은 추가 확인이 필요합니다.'
    summary = trend_summary(frame, variety) + ' 바로 앞에 표시한 연도보다 감소한 해는 ' + (', '.join(map(str, falling)) + '년입니다.' if falling else '없습니다.')
    summary += ' 감소 원인은 확정하지 않았습니다.'
    response = result(text, sources, chart_result(question, previous)['artifacts'], '고정된 조사 순서; 원자료 독립 대조와 연도별 비교', summary)
    response['steps'] = trace
    return response


def conversation_result(question):
    text = re.sub(r'[\s.!?~😊👋]', '', question)
    if text in {'안녕', '안녕하세요', '안녕하십니까', '반가워', '반갑습니다', '하이', 'hello', 'hi'}:
        return result('안녕하세요! 🍊 감귤 자료를 찾고 계산하는 도우미예요.\n\n‘천혜향 생산량을 그래프로 보여줘’처럼 물어보거나 왼쪽 예시 질문을 눌러 보세요.')
    if text in {'고마워', '감사합니다', '고맙습니다', '고마워요'}:
        return result('도움이 되었다니 다행이에요. 다른 감귤 자료도 궁금하면 물어보세요!')
    if re.search('생산량.*출하량|출하량.*생산량', question) and re.search('차이|달라|뜻', question):
        return result('**생산량**은 수확해 생산한 양이고, **출하량**은 판매·유통을 위해 내보낸 양입니다.\n\n예를 들어 100kg을 생산하고 80kg을 내보냈다면 생산량은 100kg, 출하량은 80kg입니다. 집계 기간과 대상에 따라 두 값은 다를 수 있습니다.')
    if re.search('추천.*질문|질문.*추천|예시.*질문|뭘.*물어|뭐.*물어|무엇을.*물어', question):
        from .landing import SUGGESTIONS
        picks = list(SUGGESTIONS) + ['2020년 천혜향 생산량 알려줘', '천혜향 생산량을 그래프로 보여줘']
        return result('이런 질문부터 해 보세요 🍊\n\n' + '\n'.join(f'- {q}' for q in picks)
                      + '\n\n왼쪽 **예시 질문** 메뉴에서 더 많은 질문을 고를 수 있어요.')
    if re.search('누구|이름이뭐|정체', text) and len(text) <= 12:
        return result('저는 **제주감귤분석도우미**예요 🍊 제주 감귤의 생산량·가격·경영비 자료를 찾아 계산해 드려요. '
                      '자료에 없는 내용은 지어내지 않아요.')
    if re.search('사랑|좋아해|최고|짱|귀여', text) and len(text) <= 12 and not re.search('귤|온주|한라봉|천혜향|레드향|황금향|품종', text):
        return result('고마워요, 저도 감귤만큼 좋아요 🍊 궁금한 감귤 자료가 있으면 편하게 물어보세요!')
    if re.search(r'(?:뭘|뭐|무엇을).{0,4}할\s*수\s*있|사용법|어떻게.*사용|할 수 있는', question):
        return result('자료 조회, 그래프, 빠진 값 확인, 문서 검색, 날씨 비교, 품종별 단가·경영비 조회, 이익 계산을 할 수 있어요. 왼쪽 **예시 질문** 메뉴의 **무엇을 하고 싶으세요** 목록에서 하나를 골라 보세요.')
    return None


def choose_tool(question):
    q = re.sub(r'\s+', '', question)
    if re.search('인터넷|웹에서|온라인에서', q) and re.search('찾|검색', q):
        return 'web_search'
    if re.search('문서에서|문서검색|문서.*찾', q):
        return 'document_search'
    if re.search('예측|내년|미래|전망', q):
        return None
    from .cost_tools import wants_cost_lookup
    if wants_cost_lookup(question):
        return 'cost'
    if re.search('차례대로|순서대로|단계별', q):
        return 'investigate'
    if '예시' in q and '이익' in q and re.search('가격|단가', q):
        return 'sensitivity'
    if len(re.findall(r'\d+(?:\.\d+)?\s*%', question)) >= 2:
        return 'sensitivity'
    if re.search('빠진값|누락|중복|자료.*문제|이상한값', q):
        return 'quality'
    if re.search('그래프|차트', q):
        return 'chart'
    if re.search('기온|강수|비가|비와', q) and '생산량' in q:
        if re.search('관계|관련|비교|많았|적었', q):
            return 'relationship'
        if re.search('한표|같이|함께|묶|합쳐', q):
            return 'join'
    if re.search('날씨|기온|강수|수출|가공|월별.*가격|일별.*가격', q) and (re.search('보여|알려|조회|비교|차이|증감|많|적|높|낮', q) or selected_years(question)):
        return 'data_query'
    return None


def dispatch(question, agent):
    start = time.perf_counter()
    response = conversation_result(question)
    name = 'conversation' if response else choose_tool(question)
    if not name:
        return None
    try:
        if response is None:
            if name == 'data_query':
                frame, source, title = select_frame(question)
                response = result(f'**{title}**\n\n' + table(frame) + '\n\n열 이름의 단위를 그대로 표시했습니다. 합계 행과 세부 항목은 합산하지 않았습니다.', [source],
                                  summary=f'요청 조건에 맞는 **{title} 자료 {len(frame):,}건**을 찾았습니다. 아래 표에서 값을 확인할 수 있습니다.')
                from .comparisons import data_comparison
                try:
                    full, full_source = read_source(DATASETS[dataset_for(question)][0])
                    if full_source['sha256'] == source['sha256']:
                        lead, comparison = data_comparison(dataset_for(question), frame, full, question)
                        if comparison:
                            response['text'] += '\n\n**비교 분석**\n\n' + comparison
                            if lead:
                                # The comparison is the finding; the row count only says where it came from.
                                response['summary'] = lead + '\n\n' + response['summary']
                    else:
                        response['text'] += '\n\n원자료가 변경되어 추가 비교를 보류했습니다.'
                except (OSError, ValueError, KeyError, TypeError):
                    response['text'] += '\n\n추가 비교에 필요한 자료를 확인하지 못했습니다. 위 조회 결과는 그대로 제공합니다.'
            elif name == 'chart':
                response = chart_result(question, agent.previous_request)
            elif name == 'quality':
                response = quality_result(question)
            elif name == 'join':
                frame, variety, sources = merged_frame(question, agent.previous_request)
                response = result(f'**{variety} 생산량과 날씨를 연도별로 묶었습니다.**\n\n' + table(frame)
                                  + '\n\n날씨는 제주 관측소의 달력 연도 기준입니다. 제주 전체 평균이나 인과관계가 아닙니다.', sources,
                                  summary=f'**{variety} 생산량과 날씨를 {len(frame)}개 연도 기준으로 한 표에 묶었습니다.** 날씨는 제주 관측소 기준이며 제주 전체 평균이 아닙니다.')
                from .comparisons import merged_descriptions
                response['text'] += '\n\n**비교 분석**\n\n' + merged_descriptions(frame, variety)
            elif name == 'document_search':
                response = document_result(question)
            elif name == 'web_search':
                response = web_result(question)
            elif name == 'relationship':
                response = relationship_result(question, agent.previous_request)
            elif name == 'sensitivity':
                response = sensitivity_result(question, agent.scenario)
            elif name == 'investigate':
                response = investigate_result(question, agent.previous_request)
            elif name == 'cost':
                from .cost_tools import cost_result
                text, sources, summary, plan, charts = cost_result(question, read_source, table, ToolUnavailable)
                response = result(text, sources, charts, summary=summary,
                                  validation='표준소득표 소득·순수익·단위 검산, CPI 기준연도 확인 (표본 농가 기준)')
                response['steps'] = [f"조회 종류: {plan['kind']}", f"품종: {', '.join(plan['varieties']) or '전체/기본'}",
                                     f"연도: {', '.join(map(str, plan['years'])) or '전체'}"]
        response.setdefault('success', True)
    except (ToolUnavailable, ValueError, KeyError, OSError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ToolUnavailable) else '자료의 형식·단위·입력값을 확인하지 못해 처리를 보류했습니다. 질문 조건을 확인해 주세요.'
        response = result(message)
        response['success'] = False
    response['tool'] = name
    title = next(item[1] for item in TOOL_GUIDE if item[0] == name)
    response['trace'] = [{'tool': title, 'seconds': round(time.perf_counter() - start, 3),
                          'steps': response.get('steps', []), 'success': response['success']}]
    if response['sources']:
        response['text'] += '\n\n출처: ' + ', '.join(dict.fromkeys(source_citation(s) for s in response['sources']))
    if response.get('summary'):
        response['text'] = result_first(response['summary'], response['text'])
    return response
