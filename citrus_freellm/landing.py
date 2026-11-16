"""감귤 화면 디자인: 감귤색 히어로, 인사·추천 질문, 질문 입력, 감귤 일러스트.

대화가 시작돼도 이 화면을 유지하고, 질문과 답변은 감귤 그림 아래에 이어서 보여 준다.
사이드바는 건드리지 않는다.
"""
import streamlit as st

BRAND = '제주감귤분석도우미'
TOP_LINE = '데이터로 읽는 제주 감귤, 감귤의 신(神)'
HEADLINE = ('감귤의 신(神)', '데이터로 읽는 감귤 수급 비서')
GREETING = ('안녕하세요! 🍊 제주 감귤의 생산·가격·경영비 자료를 찾아보고 계산해 드려요.',
            '궁금한 걸 바로 적거나, 아래 추천 질문을 눌러 시작해 보세요.')
SUGGESTIONS = ('2024년산 품종별 소득 비교해줘', '언제 팔면 비싼가?', '노지온주 손익분기 단가 보여줘')

# Pretendard: 한글 웹 글꼴. 인터넷이 없으면 시스템 한글 글꼴로 대신한다.
FONT = ('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/'
        'pretendardvariable-dynamic-subset.min.css')
FONT_STACK = ("'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, "
              "'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', sans-serif")

CSS = '''<style>
@import url("''' + FONT + '''");
:root {
  --citrus: #FFA02E; --citrus-deep: #F27405; --citrus-dark: #D95E00;
  --peel-light: #FFC266; --leaf: #2F9E44; --leaf-dark: #237A33;
  --ink: #141414; --paper: #FFFFFF; --font: ''' + FONT_STACK + ''';
}
/* 글씨체: 앱 전체(사이드바 포함). 아이콘 글꼴은 각 아이콘이 따로 지정하므로 그대로 남는다. */
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp td, .stApp th, .stApp [data-testid="stMarkdownContainer"] {
  font-family: var(--font);
}
.stApp p, .stApp li {letter-spacing: -.01em;}
/* 본문은 감귤색, 사이드바는 그대로 둔다. */
[data-testid="stMain"], [data-testid="stHeader"] {background: var(--citrus);}
[data-testid="stMainBlockContainer"] {padding: 0 2rem 0; max-width: 1180px;}
.citrus-topbar {
  margin: 0 -2rem 0; padding: .55rem 1rem; background: var(--ink); color: var(--paper);
  font-weight: 800; font-size: .9rem; text-align: center; letter-spacing: -.01em;
}
.citrus-logo {
  font-weight: 900; font-size: clamp(1.25rem, 2.6vw, 2rem); letter-spacing: -.04em;
  color: var(--ink); line-height: 1; padding-top: 1.1rem; white-space: nowrap;
}
.citrus-band {
  display: flex; align-items: baseline; gap: .9rem; flex-wrap: wrap;
  max-width: 860px; margin: 0 auto 1.4rem; padding: .2rem 0 1rem; border-bottom: 2px solid var(--ink);
}
.citrus-band .citrus-logo {padding-top: 1rem; font-size: clamp(1.15rem, 2vw, 1.5rem);}
.citrus-band-sub {font-weight: 700; color: var(--ink); opacity: .8;}
.citrus-hero {text-align: center; color: var(--ink); padding: clamp(2.5rem, 7vw, 5.5rem) 0 1.5rem;}
.citrus-hero h1 {
  font-size: clamp(2.6rem, 7.2vw, 6rem); font-weight: 900; line-height: 1.08;
  letter-spacing: -.045em; margin: 0; padding: 0; color: var(--ink);
}
.citrus-hero h1 .sub {display: block; font-size: .62em; letter-spacing: -.035em;}
.citrus-greeting {margin-top: 1.6rem; font-size: clamp(1rem, 1.6vw, 1.2rem); font-weight: 700; line-height: 1.75;}
/* 추천 질문: 흰 알약 버튼 */
.st-key-citrus_suggestions button {
  background: var(--paper); color: var(--ink); border: 0; border-radius: 999px;
  padding: .5rem 1.15rem; box-shadow: none; min-height: 0;
}
.st-key-citrus_suggestions button p {font-weight: 700; font-size: .95rem;}
.st-key-citrus_suggestions button:hover {background: var(--ink); color: var(--paper);}
.st-key-citrus_suggestions {max-width: 860px; margin: .4rem auto 0;}
/* 질문 입력: 테두리 한 겹의 단정한 칸 + 검정 버튼 */
/* 입력칸과 질문하기 버튼은 같은 높이(--prompt-h)를 쓴다. */
.st-key-citrus_prompt {--prompt-h: 3.9rem; max-width: 780px; margin: 2rem auto 0;}
.st-key-citrus_prompt [data-testid="stForm"] {border: 0; padding: 0;}
.st-key-citrus_prompt [data-baseweb="input"] {
  box-sizing: border-box; height: var(--prompt-h);
  border: 2px solid var(--ink); border-radius: 16px; background: var(--paper);
}
.st-key-citrus_prompt [data-baseweb="input"] > div, .st-key-citrus_prompt input {
  height: 100%; border: 0; border-radius: 14px; background: var(--paper);
}
.st-key-citrus_prompt input {padding: 0 1.2rem; font-size: 1.15rem; font-weight: 500; color: var(--ink);}
.st-key-citrus_prompt [data-testid="InputInstructions"] {display: none;}
.st-key-citrus_prompt button {
  box-sizing: border-box; height: var(--prompt-h); min-height: var(--prompt-h);
  background: var(--ink); color: var(--paper); border: 0; border-radius: 16px; padding: 0 1.4rem; width: 100%;
}
.st-key-citrus_prompt button p {font-weight: 700; font-size: 1.15rem;}
.st-key-citrus_prompt button:hover {background: var(--citrus-dark); color: var(--paper);}
/* 대화: 감귤 그림 아래 흰 카드로 이어 붙인다. */
[data-testid="stChatMessage"] {
  max-width: 860px; margin: 0 auto .9rem; background: var(--paper);
  border-radius: 18px; padding: 1rem 1.25rem; box-shadow: 0 2px 0 rgba(0,0,0,.06);
}
[data-testid="stBottom"], [data-testid="stBottom"] > div {background: var(--citrus);}
[data-testid="stBottom"] [data-testid="stChatInput"] {
  max-width: 860px; margin: 0 auto; border: 2px solid var(--ink); border-radius: 14px; background: var(--paper);
}
.citrus-art {margin: 1.5rem -2rem 1.5rem; line-height: 0;}
.citrus-art svg {display: block; width: 100%; height: auto;}
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] {padding: 0 1rem;}
  .citrus-topbar, .citrus-art {margin-left: -1rem; margin-right: -1rem;}
}
</style>'''

# 지구본 자리에 놓는 감귤. 화면 아래에 윗부분만 떠오르도록 원의 중심을 아래에 둔다.
CITRUS_ART = '''<div class="citrus-art" aria-hidden="true">
<svg viewBox="0 0 1200 380" preserveAspectRatio="xMidYMax meet" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="peel" cx="42%" cy="18%" r="75%">
      <stop offset="0" stop-color="#FFB347"/><stop offset=".55" stop-color="#F58A12"/><stop offset="1" stop-color="#E06A00"/>
    </radialGradient>
    <clipPath id="fruit"><circle cx="600" cy="640" r="430"/></clipPath>
  </defs>
  <g fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" stroke-dasharray="22 26" opacity=".95">
    <path d="M40 330 C 150 250, 250 250, 330 300"/>
    <path d="M870 300 C 960 250, 1080 240, 1170 300"/>
  </g>
  <g fill="#FFFFFF">
    <circle cx="305" cy="190" r="46"/><circle cx="360" cy="160" r="58"/><circle cx="420" cy="190" r="44"/>
    <rect x="262" y="190" width="200" height="56" rx="28"/>
  </g>
  <g stroke="#2F9E44" stroke-width="13" stroke-linecap="round">
    <path d="M930 52 v62"/><path d="M903 67 l54 32"/><path d="M903 99 l54 -32"/>
  </g>
  <circle cx="600" cy="640" r="430" fill="url(#peel)"/>
  <g clip-path="url(#fruit)" fill="#FFC266" opacity=".55">
    <circle cx="470" cy="300" r="5"/><circle cx="520" cy="262" r="4"/><circle cx="580" cy="300" r="5"/>
    <circle cx="640" cy="262" r="4"/><circle cx="700" cy="296" r="5"/><circle cx="760" cy="270" r="4"/>
    <circle cx="420" cy="350" r="4"/><circle cx="540" cy="345" r="5"/><circle cx="660" cy="340" r="4"/>
    <circle cx="790" cy="335" r="5"/><circle cx="350" cy="370" r="4"/><circle cx="860" cy="365" r="4"/>
  </g>
  <ellipse cx="500" cy="290" rx="120" ry="38" fill="#FFFFFF" opacity=".18" transform="rotate(-14 500 290)"/>
  <path d="M600 214 q 4 -30 -6 -52" stroke="#6B4423" stroke-width="10" stroke-linecap="round" fill="none"/>
  <path d="M598 176 C 640 120, 720 118, 760 140 C 720 182, 650 196, 598 176 Z" fill="#2F9E44"/>
  <path d="M600 176 C 660 150, 712 142, 752 142" stroke="#237A33" stroke-width="4" fill="none" stroke-linecap="round"/>
  <path d="M592 184 C 556 140, 500 136, 470 152 C 500 186, 552 196, 592 184 Z" fill="#3DB356"/>
</svg></div>'''


def is_landing():
    return not st.session_state.get('messages')


def render():
    """Draw the hero above the conversation. Returns a question chosen or typed here, if any."""
    chosen = None
    st.html(CSS)
    if is_landing():
        # Before the first question the hero input is the only one; afterwards the
        # chat input stays at the bottom so a long conversation needs no scrolling up.
        st.html('<style>[data-testid="stBottom"] {display: none;}</style>')
    st.html(f'<div class="citrus-topbar">{TOP_LINE}</div>')
    if not is_landing():
        # During a conversation the big hero would fill a whole screen above the
        # answers; keep a slim band instead. '새 대화' brings the full hero back.
        st.html(f'<div class="citrus-band"><span class="citrus-logo">{BRAND}</span>'
                f'<span class="citrus-band-sub">{HEADLINE[0]} · {HEADLINE[1]}</span></div>')
        return None
    st.html(f'<div class="citrus-logo">{BRAND}</div>')
    st.html('<div class="citrus-hero"><h1>' + HEADLINE[0] + '<span class="sub">' + HEADLINE[1]
            + '</span></h1><div class="citrus-greeting">' + '<br>'.join(GREETING) + '</div></div>')
    with st.container(key='citrus_suggestions', horizontal=True, horizontal_alignment='center', gap='small'):
        for index, question in enumerate(SUGGESTIONS):
            if st.button(question, key=f'citrus_suggestion_{index}'):
                chosen = question
    with st.container(key='citrus_prompt'):
        with st.form('citrus_prompt_form', clear_on_submit=True, border=False):
            field, send = st.columns([5, 1.3], vertical_alignment='center')
            typed = field.text_input('질문', placeholder='감귤 데이터에 관해 질문해 주세요', label_visibility='collapsed')
            if send.form_submit_button('질문하기') and typed.strip():
                chosen = typed.strip()
    st.html(CITRUS_ART)
    return chosen
