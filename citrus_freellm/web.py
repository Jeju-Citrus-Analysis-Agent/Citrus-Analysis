"""팀 검증용 Streamlit 화면. 답변·검증·리포트는 기존 모듈을 재사용한다."""
import sys
from pathlib import Path

import streamlit as st

# Streamlit은 파일을 직접 실행하므로 현재 작업 폴더와 무관하게 패키지를 찾는다.
parent = str(Path(__file__).resolve().parents[1])
if parent not in sys.path:
    sys.path.insert(0, parent)

from citrus_freellm.agent import Agent
from citrus_freellm.client import LazyFreeLLMClient
from citrus_freellm.reporting import save_report

EXAMPLES = (
    "어떤 품종이 면적당 매출이 높나?",
    "언제 팔면 비싼가?",
    "생산량이 늘면 가격은?",
    "날씨는 영향이 있나?",
    "2019년과 2020년 천혜향 생산량 비교",
    "판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 10% 하락 시 이익은?",
)


def main():
    st.set_page_config(page_title="제주 감귤 분석 도우미", page_icon="🍊", layout="centered")
    # Agent를 전역 캐시에 두면 다른 브라우저 세션과 대화가 섞일 수 있다.
    if "agent" not in st.session_state:
        st.session_state.agent = Agent(LazyFreeLLMClient())
        st.session_state.messages = []
        st.session_state.exports = []
    agent = st.session_state.agent
    st.title("🍊 제주 감귤 분석 도우미")
    st.caption("팀 검증용 · 통계 조회, 근거에 따른 설명, 가정 계산")

    selected_question = None
    with st.sidebar:
        st.header("대화와 리포트")
        if st.button("새 대화", use_container_width=True):
            agent.reset()
            st.session_state.messages = []
            st.session_state.exports = []
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
            label, mime = {".html": ("읽기용 리포트", "text/html"),
                           ".md": ("Markdown 리포트", "text/markdown"),
                           ".json": ("계산 조건·출처 기록", "application/json")}[extension]
            st.download_button(label, content, file_name=name, mime=mime, key=name)
        with st.expander("사용 안내"):
            st.write("원자료 조회, 기존 분석 설명, 사용자 가정 계산을 구분해 답합니다. 미래 가격을 예측하지 않습니다.")
            st.write("새 대화는 현재 대화와 조건을 비웁니다. 이미 저장한 리포트는 유지됩니다.")
            st.write("브라우저 연결이 끊기거나 서버를 재시작하면 대화가 초기화될 수 있습니다.")
        with st.expander("검증할 질문"):
            for index, question in enumerate(EXAMPLES):
                if st.button(question, key=f"example_{index}", use_container_width=True):
                    selected_question = question

    if not st.session_state.messages:
        st.info("궁금한 내용을 입력하거나 왼쪽 ‘검증할 질문’에서 선택하세요.")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("감귤 데이터에 관해 질문해 주세요") or selected_question
    if prompt:
        if prompt.strip() == "/reset":
            agent.reset()
            st.session_state.messages = []
            st.session_state.exports = []
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("근거와 계산 조건을 확인하고 있습니다…"):
                try:
                    answer = agent.ask(prompt)
                except (RuntimeError, ValueError, OSError):
                    # 원본 예외에는 서버 응답이나 경로가 포함될 수 있어 화면에 노출하지 않는다.
                    answer = "요청을 처리하지 못했습니다. 서버 연결·키 설정·자료 경로를 확인한 뒤 다시 질문해 주세요."
            st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()


if __name__ == "__main__":
    main()
