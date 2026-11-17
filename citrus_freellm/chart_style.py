"""Change how the last chart looks (bar, line, area, points) without touching its numbers."""
import copy
import re

RESTYLE_TITLE = '그래프 모양 바꾸기'
STYLES = (
    ('bar', r'막대|바\s*(?:그래프|차트)|bar'),
    ('area', r'영역\s*(?:그래프|차트)?|area'),
    ('point', r'점\s*(?:그래프|차트)|산점|점으로|scatter'),
    ('line', r'꺾은\s*선|선\s*(?:그래프|차트)|라인|line'),
)
NAMES = {'bar': '막대그래프', 'line': '꺾은선 그래프', 'area': '영역 그래프', 'point': '점 그래프'}
CHANGE = re.compile(r'바꿔|바꾸|변경|로\s*(?:다시\s*)?(?:그려|보여|해|만들)|으로\s*(?:다시\s*)?(?:그려|보여|해|만들)|로\s*줘|으로\s*줘')
NEW_SUBJECT = re.compile(r'(?:19|20)\d{2}|온주|한라봉|천혜향|레드향|황금향|생산량|면적|가격|단가|소득|경영비|기온|강수')


def requested_style(question):
    for kind, pattern in STYLES:
        if re.search(pattern, question, re.I):
            return kind
    return None


def is_restyle(question):
    """'막대그래프로 바꿔줘' changes the last chart; '천혜향 생산량 막대그래프' draws a new one."""
    return bool(requested_style(question) and CHANGE.search(question) and not NEW_SUBJECT.search(question))


def styled(artifacts, kind):
    charts = []
    for artifact in artifacts:
        artifact = copy.deepcopy(artifact)
        if artifact.get('type') == 'chart':
            artifact['chart_kind'] = kind
        charts.append(artifact)
    return charts


def restyle_answer(kind, count):
    return (f'앞선 그래프{" " + str(count) + "개" if count > 1 else ""}를 **{NAMES[kind]}**로 바꿨어요. '
            '숫자와 기간은 그대로예요.\n\n막대·꺾은선·영역·점 그래프 중에서 다시 바꿀 수 있어요.')
