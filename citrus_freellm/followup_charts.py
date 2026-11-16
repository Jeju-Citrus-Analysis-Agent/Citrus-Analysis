"""Chart displayed values from a successful answer without changing its scope."""
import math
import re

from .presentation import result_first


def is_chart_followup(question):
    text = re.sub(r'\s+|[.!?]', '', question)
    return bool(re.fullmatch(
        r'(?:그럼|그러면)?(?:(?:방금|이전)(?:답변|결과|표)(?:의표)?|이표|그표|위표|앞선표|이것|이거|그것|그거|이걸|그걸)?'
        r'(?:을|를)?(?:막대|선)?(?:그래프|차트)(?:로|으로)?'
        r'(?:그려|그려줘|그려주세요|보여줘|보여주세요|만들어줘|만들어주세요|바꿔줘|바꿔주세요)?', text))


def displayed_tables(text):
    """Read tables rendered by verified tools, never user or model prose."""
    blocks, block = [], []
    for line in text.splitlines() + ['']:
        if line.strip().startswith('|'):
            block.append([cell.strip() for cell in line.strip().strip('|').split('|')])
        else:
            if len(block) >= 3 and all(re.fullmatch(r':?-+:?', c) for c in block[1]):
                header = block[0]
                rows = [row for row in block[2:] if len(row) == len(header)]
                if rows and len(set(header)) == len(header):
                    blocks.append((header, rows))
            block = []
    return blocks


def numeric(value):
    value = value.replace('**', '').replace(',', '').strip()
    if value in {'없음', '-', '—', '미확인', ''}:
        return None
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', value):
        raise ValueError('not numeric')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('not finite')
    return result


def table_artifacts(text, question):
    artifacts = []
    for table_number, (header, rows) in enumerate(displayed_tables(text), 1):
        measures, dimensions = [], [0]
        for index in range(1, len(header)):
            try:
                values = [numeric(row[index]) for row in rows]
            except ValueError:
                dimensions.append(index)
                continue
            if any(value is not None for value in values) and header[index] not in {'순위', '연도', '기준연도'}:
                measures.append((index, values))
            else:
                dimensions.append(index)
        labels = [' · '.join(row[i] for i in dimensions) for row in rows]
        # Preserve repeated categories as separate observations, never sum them.
        if len(set(labels)) != len(labels):
            labels = [f'{label} ({i}행)' for i, label in enumerate(labels, 1)]
        for index, values in measures:
            metric = header[index]
            unit = re.search(r'\(([^()]*)\)\s*$', metric)
            artifacts.append({
                'type': 'chart', 'title': f'앞선 표 {table_number} · {metric}',
                'data': [{'항목': label, metric: value} for label, value in zip(labels, values)],
                'x': '항목', 'y': metric, 'unit': unit[1] if unit else '표에 표시된 단위',
                'chart_kind': 'line' if '선그래프' in re.sub(r'\s+', '', question) else 'bar',
            })
    return artifacts


def chart_previous_answer(agent, question):
    previous = agent.results[-1] if agent.results else None
    last_answer = agent.history[-1]['content'] if agent.history else None
    if not previous or previous['text'] != last_answer:
        return agent.remember(question, '그래프로 바꿀 앞선 표가 없습니다. 먼저 표가 포함된 조회나 분석을 요청해 주세요.')
    artifacts = table_artifacts(previous['text'], question)
    if not artifacts:
        return agent.remember(question, '앞선 답변에 그래프로 표시할 수 있는 수치 표가 없습니다. 품종·연도·지표를 지정해 조회해 주세요.')
    agent.last_artifacts = artifacts
    agent.last_trace = [{'tool': '앞선 표를 그래프로 보기', 'seconds': 0, 'steps': [], 'success': True}]
    text = result_first(
        f'앞선 답변의 표를 **그래프 {len(artifacts)}개**로 그렸습니다. 표에 표시한 항목·기간·수치를 그대로 사용했습니다.',
        '서로 다른 지표는 그래프를 나누었습니다. 아래는 그래프의 기준이 된 앞선 답변입니다.\n\n' + previous['text'])
    answer = agent.record('local_tool', question, {'tool': 'chart_from_table', 'basis_question': previous['question']}, text, previous['sources'])
    agent.results[-1]['validation'] = '앞선 성공 답변의 표시된 표 수치 재사용; 원자료 재조회·추가 집계 없음'
    return answer
