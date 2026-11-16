"""Resolve public data citations from the repository README, preserving file evidence."""
import re
from pathlib import PurePosixPath

from .repository import repository_root

# Derived -> parent, transformation. Paths are retained only in internal provenance.
PARENTS = {
    'fruit_production_clean.csv': ('fruit_production.csv', '품종 분류·명칭 정제'),
    'jeju_special_crops.csv': ('crop_production.csv', '제주 지역 추출'),
    'jeju_special_crops_clean.csv': ('jeju_special_crops.csv', '중복·소계 제거 및 단수 재계산'),
    'varieties_summary_clean.csv': ('varieties_summary.csv', '전년비를 증감률로 정제'),
    'weather_monthly.csv': ('weather_daily.csv', '일별 관측을 월별로 집계'),
    'weather_daily.csv': ('asos_daily_original', '기상 관측 일자료 정제'),
    'citrus_production_yearly.csv': ('jasdc_production', '품종별 생산 통계 정제·단위 통일 및 면적당 지표 계산'),
    'citrus_processing_yearly.csv': ('jasdc_processing', '가공처리 통계 정제·단위 통일'),
    'citrus_processing_by_company.csv': ('jasdc_processing', '업체별 가공처리 통계 정제'),
    'citrus_export_yearly.csv': ('jasdc_export', '국가별 수출 통계 정제·단위 통일'),
    'citrus_price_daily.csv': ('jasdc_manual_daily', '내려받은 일별 가격·출하 표 정제 및 시즌 구분'),
    'citrus_price_monthly_box.csv': ('jasdc_manual_monthly', '내려받은 월별 상자규격 가격 표 정제'),
    **{name: ('distribution_analysis.xlsx', '유통처리 표 추출·정제') for name in (
        'noji_yearly.csv', 'noji_monthly_2025.csv', 'noji_market_2025.csv',
        'noji_size.csv', 'varieties_summary.csv')},
}


def readme_source(path):
    """Return only links documented in README; never infer a dataset detail URL."""
    name = PurePosixPath(path).name
    lineage, transformations = [name], []
    while name in PARENTS:
        name, transformation = PARENTS[name]
        lineage.append(name)
        transformations.append(transformation)
    note = ''
    if name == 'fruit_production.csv':
        label = '제주데이터허브'
    elif name == 'crop_production.csv':
        label, note = '제주데이터허브', 'README에서 출처로 추정'
    elif name == 'distribution_analysis.xlsx':
        label = '유통처리 상황'
    elif name in {'jasdc_production', 'jasdc_processing', 'jasdc_export'}:
        label = {'jasdc_production': '감귤 생산정보', 'jasdc_processing': '가공처리현황', 'jasdc_export': '수출현황'}[name]
    elif name in {'jasdc_manual_daily', 'jasdc_manual_monthly'}:
        label = '제주농산물수급관리센터'
        note = '수동 다운로드한 가격·출하 표를 정제한 자료. README에 상세 원문 주소 미기재'
    elif name == 'asos_daily_original' or name.startswith('asos_daily_'):
        label = '기상청 ASOS 일자료'
    else:
        return None
    try:
        readme = (repository_root() / 'README.md').read_text(encoding='utf-8')
    except OSError:
        if label == '기상청 ASOS 일자료':
            return {'title': label, 'note': 'README에서 원문 URL을 확인하지 못함', 'lineage': lineage, 'transformations': transformations}
        return None
    match = re.search(r'\[' + re.escape(label) + r'\]\((https://[^\s)]+)\)', readme)
    if not match:
        if label == '기상청 ASOS 일자료':
            return {'title': label, 'note': 'README에서 원문 URL을 확인하지 못함', 'lineage': lineage, 'transformations': transformations}
        return None
    title = '제주농산물수급관리센터 · 유통처리 상황' if label == '유통처리 상황' else label
    return {'title': title, 'url': match[1], 'lineage': lineage,
            'transformations': transformations, **({'note': note} if note else {})}


def source_citation(source):
    """Show the original publication; file paths remain in internal evidence only."""
    path = source.get('path')
    origin = readme_source(path) if path else None
    if origin:
        label = f"[{origin['title']}]({origin['url']})" if origin.get('url') else origin['title']
        notes = list(reversed(origin.get('transformations', [])))
        if origin.get('note'):
            notes.append(origin['note'])
        return label + (' (' + '; '.join(notes) + ')' if notes else '')
    if source.get('url'):
        return f"[{source.get('title', source['url'])}]({source['url']})"
    if path:
        return '프로젝트 공개 문서' if path.endswith('.md') else '원문 출처 미확인'
    return '사용자 입력'


def public_text(text):
    """Keep storage filenames out of answers, including quoted document excerpts."""
    return re.sub(r'`?(?:[\w.*-]+/)*[\w.*-]+\.csv`?', '통계 자료', text, flags=re.IGNORECASE)
