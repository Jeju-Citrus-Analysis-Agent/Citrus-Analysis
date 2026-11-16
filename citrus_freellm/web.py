"""팀 검증용 Streamlit 화면. 답변·검증·리포트는 기존 모듈을 재사용한다."""
import re
import sys
from collections import Counter
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# Streamlit은 파일을 직접 실행하므로 현재 작업 폴더와 무관하게 패키지를 찾는다.
parent = str(Path(__file__).resolve().parents[1])
if parent not in sys.path:
    sys.path.insert(0, parent)

from citrus_freellm import landing
from citrus_freellm.agent import Agent
from citrus_freellm.reporting import save_report
from citrus_freellm.example_questions import EXAMPLE_CATEGORIES
from citrus_freellm.presentation import split_answer
from citrus_freellm.navigation import question_anchor, scroll_script, SCROLL_FRAME_HEIGHT
from citrus_freellm.usability import (availability_signature, source_availability, snapshot_context,
                                     restore_context, followup_context, chart_followup,
                                     comparison_followup, number_hints, unit_hints,
                                     needs_examples, related_examples, friendly_failure)


@st.cache_data(show_spinner=False)
def available_sources(signature):
    # The size and modification time invalidate the cache when local files change.
    return source_availability()


def static_chart(frame, artifact):
    # st.line_chart and friends always zoom on the mouse wheel, which hijacks
    # page scrolling. Plain Altair charts are not interactive unless asked.
    import altair as alt
    series = artifact.get('series')
    columns = [artifact['x'], artifact['y']] + ([series, '원래 값'] if series else [])
    data = frame[columns].set_axis(['x', 'y'] + (['s', 'v'] if series else []), axis=1)
    chart = alt.Chart(data)
    points = data['x'].nunique()
    if artifact.get('chart_kind') == 'bar':
        chart = chart.mark_bar()
    else:
        chart = chart.mark_point(filled=True) if points == 1 else chart.mark_line(point=True)
    tooltip = [alt.Tooltip('x:O', title=artifact['x']), alt.Tooltip('y:Q', title=artifact['y'], format=',')]
    encoding = {'x': alt.X('x:O', sort=None, title=artifact['x'], axis=alt.Axis(labelAngle=0 if points <= 8 else -45)),
                'y': alt.Y('y:Q', title=artifact['y'])}
    if series:
        # Several metrics share one % axis; colour tells them apart, bars sit side by side.
        order = list(dict.fromkeys(data['s']))
        encoding['color'] = alt.Color('s:N', sort=order, title=series, legend=alt.Legend(orient='bottom'))
        if artifact.get('chart_kind') == 'bar':
            encoding['xOffset'] = alt.XOffset('s:N', sort=order)
        tooltip = [tooltip[0], alt.Tooltip('s:N', title=series), tooltip[1],
                   alt.Tooltip('v:Q', title='원래 값', format=',')]
    return chart.encode(**encoding, tooltip=tooltip)


LONG_DETAILS = 900  # characters; shorter details (a lookup table) stay open under the conclusion


def plain_tildes(text):
    """'2016~2020 … 53~56%' must not become strikethrough: Streamlit reads a pair of ~ as ~~."""
    return re.sub(r'(?<!\\)~', r'\\~', text)


def begin_edit(index):
    message = st.session_state.messages[index]
    st.session_state.editing_question = {
        'index': index, 'context': message.get('context', snapshot_context(Agent()))}
    st.session_state.edit_text = message['content']
    request_scroll(index)


def request_scroll(index):
    nonce = st.session_state.get('scroll_nonce', 0) + 1
    st.session_state.scroll_nonce = nonce
    st.session_state.scroll_target = {'index': index, 'nonce': nonce}


def main():
    # One layout before and after the first question: the hero stays and answers follow it.
    # Chat cards keep a readable width through landing.CSS.
    st.set_page_config(page_title="감귤의 신 (神) : 데이터로 읽는 제주 감귤 수급 비서", page_icon="🍊", layout="wide")
    st.markdown('''<style>
    [class*="st-key-edit_action_"] button {
        min-height: 1.5rem; padding: .05rem .35rem;
        border: 0; background: transparent; color: #64748b;
    }
    [class*="st-key-edit_action_"] button p {font-size: .75rem;}
    [class*="st-key-edit_action_"] button:hover {background: #f1f5f9;}
    [data-testid="stMain"] {overflow-anchor: none; scroll-behavior: auto;}
    </style>''', unsafe_allow_html=True)
    st.sidebar.caption("API 키 없이 사용 · 인터넷 검색만 연결 필요")
    # Agent를 전역 캐시에 두면 다른 브라우저 세션과 대화가 섞일 수 있다.
    if "agent" not in st.session_state or getattr(st.session_state.agent, 'client', None) is not None:
        st.session_state.agent = Agent(local_only=True)
        st.session_state.messages = []
        st.session_state.exports = []
    agent = st.session_state.agent
    agent.local_only = True
    availability = available_sources(availability_signature())
    selected_question = landing.render()

    selected_context = None
    edited_index = None
    with st.sidebar:
        st.header("대화와 리포트")
        if st.button("새 대화", use_container_width=True):
            agent.reset()
            st.session_state.messages = []
            st.session_state.exports = []
            st.session_state.pop('editing_question', None)
            st.session_state.pop('comparison_target', None)
            st.session_state.pop('scroll_target', None)
            st.rerun()
        st.caption(f"리포트에 담을 수 있는 결과: {len(agent.results)}개")
        scope = st.radio("저장 범위", ("최근 결과 1개", "전체 결과"))
        if st.button("리포트 만들기", disabled=not agent.results, use_container_width=True):
            try:
                paths = save_report(agent.results, scope == "전체 결과")
                st.session_state.exports = [(Path(p).name, Path(p).read_bytes()) for p in paths]
            except (ValueError, OSError):
                st.error("리포트를 저장하지 못했습니다. 저장 폴더의 접근 권한을 확인해 주세요.")
        for name, content in st.session_state.exports:
            extension = Path(name).suffix
            label, mime = {".pdf": ("PDF 리포트", "application/pdf"),
                           ".md": ("Markdown 리포트", "text/markdown")}[extension]
            st.download_button(label, content, file_name=name, mime=mime, key=name)
        if st.session_state.exports and not any(n.endswith('.pdf') for n, _ in st.session_state.exports):
            st.caption('PDF용 한글 글꼴이나 변환 도구를 찾지 못해 Markdown만 만들었습니다.')
        with st.expander("사용 안내"):
            st.markdown("""
**질문하기**

**연도 + 품종 + 궁금한 항목**을 적어 주세요.
예: ‘2020년 천혜향 생산량 알려줘’

아래 **예시 질문**을 눌러 시작해도 됩니다.

**예시 질문 → 무엇을 하고 싶으세요?**에서 원하는 일을 고른 뒤 질문을 눌러 보세요.
API 키는 필요 없으며, 인터넷 검색만 인터넷 연결이 필요합니다.

표가 나온 뒤 **‘그래프로 그려줘’**라고 입력하면 같은 항목·기간·수치를 그래프로 볼 수 있습니다.

**결과 저장**

**리포트 만들기 → PDF 리포트** 또는 **Markdown 리포트**를 눌러 다운로드하세요.
**새 대화**를 누르면 이전 질문과 계산 조건이 지워집니다.

답변은 **결론 → 세부 설명** 순서로 보여줍니다.
질문 아래 작은 **수정하기**를 누르면 그 자리에서 고칠 수 있습니다.

**참고하세요**

- 생산량·면적 조회는 **2015~2020년** 자료가 기본입니다.
- 인사와 간단한 용어 설명을 지원합니다. 자유로운 잡담과 미래 예측은 지원하지 않습니다.
""")
        with st.expander("예시 질문", expanded=True):
            category = st.selectbox('무엇을 하고 싶으세요?', tuple(EXAMPLE_CATEGORIES), key='example_category')
            for index, question in enumerate(EXAMPLE_CATEGORIES[category]):
                if st.button(question, key=f'example_{category}_{index}', use_container_width=True):
                    selected_question = question

    def show_artifacts(message):
        import pandas as pd
        for artifact in message.get('artifacts', []):
            if artifact['type'] == 'chart':
                st.caption(artifact['title'] + ' · 단위: ' + artifact['unit'])
                st.altair_chart(static_chart(pd.DataFrame(artifact['data']), artifact), use_container_width=True)

    for message_index, message in enumerate(st.session_state.messages):
        if message['role'] == 'user':
            st.markdown(f'<div id="{question_anchor(message_index)}" style="height:0;scroll-margin-top:5rem" aria-hidden="true"></div>', unsafe_allow_html=True)
        with st.chat_message(message["role"]):
            editing = st.session_state.get('editing_question')
            if message['role'] == 'user' and editing and editing['index'] == message_index:
                with st.form(f'edit_question_form_{message_index}'):
                    edited = st.text_area('질문 수정', key='edit_text')
                    st.caption('저장하면 이 질문과 답변을 바꿉니다. 그 뒤에 이어진 대화는 새로 시작합니다.')
                    save, cancel = st.columns([1, 1])
                    submitted = save.form_submit_button('저장하고 답변 받기')
                    cancelled = cancel.form_submit_button('취소')
                if submitted:
                    if edited.strip():
                        selected_question = edited.strip()
                        selected_context = editing['context']
                        edited_index = message_index
                    else:
                        st.warning('질문을 입력해 주세요.')
                if cancelled:
                    st.session_state.pop('editing_question', None)
                    st.rerun()
                continue
            summary, details = split_answer(message['content']) if message['role'] == 'assistant' else (message['content'], '')
            st.markdown(plain_tildes(summary))
            if message['role'] == 'assistant':
                hints = number_hints(summary)
                if hints:
                    st.caption(plain_tildes('숫자를 쉽게 읽으면: ' + ' · '.join(hints)), help='원래 값과 단위는 그대로 유지합니다.')
            if details and len(details) > LONG_DETAILS:
                # Long explanations: conclusion and picture first, the evidence one click away.
                show_artifacts(message)
                with st.expander('자세히 보기 (표·근거·출처)'):
                    st.markdown(plain_tildes(details))
            elif details:
                st.markdown(plain_tildes(details))
                show_artifacts(message)
            else:
                show_artifacts(message)
            if message['role'] == 'assistant':
                units = unit_hints(message['content'])
                if units:
                    st.caption(plain_tildes('단위 도움말: ' + ' · '.join(units)))
                if message.get('examples'):
                    st.caption('이렇게 물어보면 바로 답할 수 있어요. 눌러서 질문해 보세요.')
                    for example_index, example in enumerate(message['examples']):
                        if st.button(plain_tildes(example), key=f'related_{message_index}_{example_index}', icon=':material/chat_bubble:'):
                            selected_question = example
            if message['role'] == 'user':
                with st.container(key=f'edit_action_{message_index}'):
                    st.button('수정하기', key=f'edit_{message_index}', on_click=begin_edit,
                              args=(message_index,), help='이 질문을 그 자리에서 수정합니다.')

    if st.session_state.messages:
        # The scroll job resizes this div in the browser. A keyed container keeps
        # Streamlit from reusing that resized node as the next question anchor.
        with st.container(key='question_scroll_space'):
            st.markdown('<div id="question-scroll-space" style="height:0" aria-hidden="true"></div>', unsafe_allow_html=True)
    target = st.session_state.pop('scroll_target', None)
    if target is not None:
        # Changing the container key forces remounting even on consecutive submits.
        with st.container(key=f"question_navigation_{target['nonce']}"):
            if hasattr(st, 'iframe'):
                st.iframe(scroll_script(target['index'], target['nonce']), height=SCROLL_FRAME_HEIGHT, tab_index=-1)
            else:
                components.html(scroll_script(target['index'], target['nonce']), height=SCROLL_FRAME_HEIGHT)

    prompt = st.chat_input("감귤 데이터에 관해 질문해 주세요") or selected_question
    if prompt:
        if prompt.strip() == "/reset":
            agent.reset()
            st.session_state.messages = []
            st.session_state.exports = []
            st.session_state.pop('editing_question', None)
            st.session_state.pop('comparison_target', None)
            st.session_state.pop('scroll_target', None)
        else:
            if edited_index is not None and prompt == selected_question:
                # Editing creates a new continuation at that turn, so later answers
                # cannot silently retain the old assumptions. Remove their report
                # records too; downloaded files are independent of this session.
                messages = st.session_state.messages
                obsolete = Counter((messages[i]['content'], messages[i + 1]['content'])
                                   for i in range(edited_index, len(messages) - 1)
                                   if messages[i]['role'] == 'user' and messages[i + 1]['role'] == 'assistant')
                kept = []
                for record in reversed(agent.results):
                    identity = (record['question'], record['text'])
                    if obsolete[identity]:
                        obsolete[identity] -= 1
                    else:
                        kept.append(record)
                agent.results = list(reversed(kept))
                st.session_state.messages = messages[:edited_index]
                agent.history = [{'role': m['role'], 'content': m['content']}
                                 for m in st.session_state.messages[-12:]]
                st.session_state.exports = []
            if prompt == selected_question and selected_context is not None:
                restore_context(agent, selected_context)
            context_before = snapshot_context(agent)
            st.session_state.pop('editing_question', None)
            st.session_state.pop('comparison_target', None)
            previous_result = agent.results[-1] if agent.results else None
            st.session_state.messages.append({"role": "user", "content": prompt, 'context': context_before})
            with st.spinner("근거와 계산 조건을 확인하고 있습니다…"):
                try:
                    answer = agent.ask(prompt)
                except (RuntimeError, ValueError, OSError):
                    # 원본 예외에는 서버 응답이나 경로가 포함될 수 있어 화면에 노출하지 않는다.
                    answer = "요청을 처리하지 못했습니다. 입력한 조건과 자료 파일을 확인한 뒤 다시 질문해 주세요."
            created_result = bool(agent.results and agent.results[-1] is not previous_result)
            next_context = followup_context(prompt, agent, availability) if created_result else None
            examples = related_examples(prompt, availability) if needs_examples(prompt, answer, agent) else []
            if examples:
                answer = friendly_failure(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer,
                                              'artifacts': agent.last_artifacts, 'trace': agent.last_trace,
                                              'followup': next_context, 'examples': examples})
            request_scroll(len(st.session_state.messages) - 2)
        st.rerun()


if __name__ == "__main__":
    main()
