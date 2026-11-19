"""감귤 화면 디자인: 감귤색 히어로, 인사·추천 질문, 질문 입력, 감귤 일러스트.

대화가 시작돼도 이 화면을 유지하고, 질문과 답변은 감귤 그림 아래에 이어서 보여 준다.
사이드바는 숨기고, 새 대화·예시 질문·리포트 버튼을 로고 아래 한 줄에 둔다.
"""
import base64

import streamlit as st

from citrus_freellm import art

BRAND = '감귤의 신(神)'
TOP_LINE = '데이터로 읽는 제주 감귤, 감귤의 신(神)'
HEADLINE = ('감귤의 신(神)', '데이터로 읽는 감귤 수급 비서')
GREETING = ('안녕하세요. 제주 감귤의 생산·가격·경영비 자료를 찾아보고 계산해 드려요.',
            '궁금한 걸 바로 적거나, 아래 추천 질문을 눌러 시작해 보세요.')
# 써라운드 글꼴에는 한자가 없어 '神'이 빈칸으로 보인다. 그 한 글자만 Noto Sans KR로 그린다.
HANJA_FONT = 'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@900&text=%E7%A5%9E&display=swap'


def with_hanja(text):
    return text.replace('神', '<span class="citrus-hanja">神</span>')


def title_html(text):
    """Big titles: '감귤' in citrus orange, 神 in a font that has it."""
    return with_hanja(text).replace('감귤', '<span class="citrus-word">감귤</span>', 1)


SUGGESTIONS = ('2024년산 품종별 소득 비교해줘', '언제 팔면 비싼가?', '노지온주 손익분기 단가 보여줘')

# 글꼴: 카페24 써라운드(눈누 배포, 웹 사용 가능). 본문은 얇은 써라운드에어, 제목·굵은 글씨는 써라운드.
# 받지 못하면 시스템 한글 글꼴로 대신한다.
SSURROUND = 'https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2105_2@1.0/'
# 써라운드에는 한자 모양이 없거나 깨져 보이므로, 한자는 이 글꼴이 맡지 않고 시스템 한글 글꼴로 넘긴다.
ROUND_RANGE = 'U+0000-33FF, U+A960-A97F, U+AC00-D7FF, U+FE30-FE4F, U+FF00-FFEF'
FONT_FACES = ''.join(
    "@font-face {font-family: 'Citrus Round'; font-weight: %s; font-display: swap; "
    "src: url('%s%s.woff') format('woff'); unicode-range: %s;}\n" % (weights, SSURROUND, name, ROUND_RANGE)
    for weights, name in (('100 500', 'Cafe24SsurroundAir'), ('600 900', 'Cafe24Ssurround')))
FONT_STACK = ("'Citrus Round', 'Cafe24Ssurround', 'Apple SD Gothic Neo', 'Malgun Gothic', "
              "'Noto Sans KR', sans-serif")

CSS = '<style>\n@import url("' + HANJA_FONT + '");\n' + FONT_FACES + '''
:root {
  /* 과즙 팔레트: 크림 바탕 위에 진한 감귤색과 귤잎 초록으로 대비를 준다. */
  --bg: #FFF5E4; --line: #F3D3A6;
  --citrus: #FF8A00; --citrus-deep: #F26B00; --citrus-dark: #D95500;
  --peel-light: #FFC266; --leaf: #1E8F3E; --leaf-dark: #146B2D;
  --ink: #1A1410; --paper: #FFFFFF; --font: ''' + FONT_STACK + ''';
}
/* 글씨체: 앱 전체. 아이콘 글꼴은 각 아이콘이 따로 지정하므로 그대로 남는다. */
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp td, .stApp th, .stApp [data-testid="stMarkdownContainer"] {
  font-family: var(--font);
}
/* 팝오버(예시 질문·리포트·사용 안내)는 .stApp 바깥에 그려지므로 따로 지정한다. */
[data-testid="stPopoverBody"], [data-testid="stPopoverBody"] :is(p, li, label, button, input, div):not([data-testid="stIconMaterial"]),
[role="listbox"] li, [role="option"] {font-family: var(--font);}
/* 숨 쉴 틈: 줄 간격과 문단·목록·표 사이를 넉넉하게 */
.citrus-hanja {font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans CJK KR', serif; font-weight: 900;}
.stApp p, .stApp li {letter-spacing: 0; line-height: 1.85;}
.stApp [data-testid="stMarkdownContainer"] p {margin-bottom: .9rem;}
.stApp [data-testid="stMarkdownContainer"] li {margin-bottom: .45rem;}
.stApp [data-testid="stMarkdownContainer"] ul, .stApp [data-testid="stMarkdownContainer"] ol {margin: .4rem 0 1rem;}
.stApp [data-testid="stMarkdownContainer"] table {margin: .6rem 0 1.2rem;}
.stApp [data-testid="stMarkdownContainer"] td, .stApp [data-testid="stMarkdownContainer"] th {padding: .5rem .8rem;}
.stApp [data-testid="stCaptionContainer"] {line-height: 1.7;}
[data-testid="stChatMessage"] [data-testid="stVerticalBlock"] {gap: 1.1rem;}
/* 사이드바는 쓰지 않는다: 도구는 로고 아래 한 줄에 둔다. */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {display: none;}
.st-key-citrus_toolbar {max-width: 860px; margin: .2rem auto 1.4rem;}
.st-key-citrus_toolbar button {
  background: var(--paper); color: var(--ink); border: 0; border-radius: 999px;
  padding: .3rem .95rem; min-height: 0; box-shadow: inset 0 0 0 1.5px var(--line);
}
.st-key-citrus_toolbar button:hover {background: var(--citrus-deep); color: var(--paper); box-shadow: none;}
.st-key-citrus_toolbar button p {font-weight: 700; font-size: .9rem;}
/* 본문은 크림색. Streamlit 1.65부터 본문은 data-testid 대신 class="stMain"이라 둘 다 지정한다. */
.stApp, .stMain, [data-testid="stMain"] {background: var(--bg);}
/* Streamlit 기본 헤더(Deploy·메뉴, 높이 60px)는 쓰지 않는다. 남겨 두면 검은 띠와 로고를 덮는다. */
[data-testid="stHeader"] {display: none;}
[data-testid="stMainBlockContainer"] {padding: 0 2rem 0; max-width: 1180px;}
.citrus-topbar {
  margin: 0 -2rem 0; padding: .55rem 1rem; background: var(--leaf-dark); color: var(--bg);
  font-weight: 800; font-size: .9rem; text-align: center; letter-spacing: -.01em;
}
.citrus-logo {
  font-weight: 900; font-size: clamp(1.25rem, 2.6vw, 2rem); letter-spacing: -.04em;
  color: var(--ink); line-height: 1; padding-top: 1.1rem; white-space: nowrap;
}
.citrus-band {
  display: flex; align-items: baseline; gap: .9rem; flex-wrap: wrap;
  max-width: 860px; margin: 0 auto .8rem; padding: .2rem 0 1rem; border-bottom: 2px solid var(--ink);
}
.citrus-band .citrus-logo {padding-top: 1rem; font-size: clamp(1.15rem, 2vw, 1.5rem);}
.citrus-band-sub {font-weight: 700; color: var(--ink); opacity: .8;}
/* 첫 화면은 높이(vh)에 맞춰 줄어들어, 아래 감귤 그림까지 한 화면에 들어온다. */
@keyframes citrus-in {from {opacity: 0; transform: translateY(12px);} to {opacity: 1; transform: none;}}
.citrus-hero {animation: citrus-in .45s ease-out; text-align: center; color: var(--ink); padding: clamp(.25rem, 3vh, 4rem) 0 .5rem;}
.citrus-hero h1 {
  font-size: clamp(2.2rem, min(7.2vw, 8.5vh), 6rem); font-weight: 900; line-height: 1.08;
  letter-spacing: -.045em; margin: 0; padding: 0; color: var(--ink);
}
.citrus-hero h1 .sub {display: block; margin-top: .45em; font-size: .62em; letter-spacing: -.035em;}
.citrus-greeting {margin-top: clamp(.6rem, 2.5vh, 1.6rem); font-size: clamp(1rem, 1.6vw, 1.2rem); font-weight: 700; line-height: 1.75;}
/* 추천 질문: 감귤색 테두리의 흰 알약 버튼, 누르면 감귤색으로 꽉 찬다 */
.citrus-word {color: var(--citrus-deep);}
.st-key-citrus_suggestions button {
  background: var(--paper); color: var(--ink); border: 0; border-radius: 999px;
  padding: .5rem 1.15rem; box-shadow: inset 0 0 0 2px var(--citrus); min-height: 0;
}
.st-key-citrus_suggestions button p {font-weight: 700; font-size: .95rem;}
.st-key-citrus_suggestions button:hover {background: var(--citrus-deep); color: var(--paper); box-shadow: none;}
.st-key-citrus_suggestions {max-width: 860px; margin: .4rem auto 0;}
/* 질문 입력: 테두리 한 겹의 단정한 칸 + 검정 버튼 */
/* 입력칸과 질문하기 버튼은 같은 높이(--prompt-h)를 쓴다. */
.st-key-citrus_prompt {--prompt-h: clamp(3rem, 6.5vh, 3.9rem); max-width: 780px; margin: clamp(.2rem, 2vh, 2rem) auto 0;}
.st-key-citrus_prompt [data-testid="stForm"] {border: 0; padding: 0;}
/* 1.65부터 입력칸 바깥 틀은 data-baseweb="input" 대신 stTextInputRootElement다. */
.st-key-citrus_prompt [data-baseweb="input"], .st-key-citrus_prompt [data-testid="stTextInputRootElement"] {
  box-sizing: border-box; height: var(--prompt-h);
  border: 2px solid var(--ink); border-radius: 16px; background: var(--paper);
}
.st-key-citrus_prompt [data-baseweb="input"] > div,
.st-key-citrus_prompt [data-testid="stTextInputRootElement"] > div, .st-key-citrus_prompt input {
  height: 100%; border: 0; border-radius: 14px; background: var(--paper);
}
.st-key-citrus_prompt input {padding: 0 1.2rem; font-size: 1.15rem; font-weight: 500; color: var(--ink);}
.st-key-citrus_prompt [data-testid="InputInstructions"] {display: none;}
.st-key-citrus_prompt button {
  box-sizing: border-box; height: var(--prompt-h); min-height: var(--prompt-h);
  background: var(--citrus-deep); color: var(--paper); border: 0; border-radius: 16px; padding: 0 1.4rem; width: 100%;
}
.st-key-citrus_prompt button p {font-weight: 700; font-size: 1.15rem;}
.st-key-citrus_prompt button:hover {background: var(--citrus-dark); color: var(--paper);}
/* 대화: 감귤 그림 아래 흰 카드로 이어 붙인다. */
[data-testid="stChatMessage"] {
  max-width: 860px; margin: 0 auto 1.4rem; background: var(--paper); border: 1.5px solid var(--line);
  border-radius: 22px; padding: 1.5rem 1.75rem; box-shadow: 0 8px 24px rgba(242, 107, 0, .08);
}
[data-testid="stChatMessage"] + [data-testid="stChatMessage"] {margin-top: 1.4rem;}
[data-testid="stBottom"], [data-testid="stBottom"] > div {background: var(--bg);}
[data-testid="stBottom"] [data-testid="stChatInput"] {
  max-width: 860px; margin: 0 auto; border: 2px solid var(--ink); border-radius: 14px; background: var(--paper);
}
.citrus-art {margin: .5rem -2rem 0; line-height: 0;}
.citrus-art img {display: block; width: 100%; height: auto;}
/* 한국어는 낱말 중간에서 줄을 바꾸지 않는다 ('천혜/향' 방지). */
.stApp p, .stApp li, .stApp td, .stApp th, .citrus-greeting, .citrus-hero h1 {word-break: keep-all; overflow-wrap: anywhere;}
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] {padding: 0 1rem;}
  .citrus-topbar, .citrus-art {margin-left: -1rem; margin-right: -1rem;}
  /* 툴바 버튼 4개를 한 줄에: 고정된 툴바가 화면을 덜 가린다. */
  .st-key-citrus_toolbar {gap: .35rem; flex-wrap: nowrap; margin-bottom: .8rem;}
  .st-key-citrus_toolbar button {padding: .25rem .55rem;}
  .st-key-citrus_toolbar button p {font-size: .78rem; white-space: nowrap;}
  /* 아이콘(앞 아이콘·펼침 화살표)은 감싼 칸째 숨겨야 자리가 빈다. */
  .st-key-citrus_toolbar button :is(span, div):has(> [data-testid="stIconMaterial"]) {display: none;}
  /* 질문하기 버튼은 입력칸 아래 전체 폭으로 */
  /* 추천 질문은 작게: 한 줄에 둘씩 들어가 감귤 그림까지 첫 화면에 보인다. */
  .st-key-citrus_suggestions {gap: .4rem;}
  .st-key-citrus_suggestions button {padding: .35rem .8rem;}
  .st-key-citrus_suggestions button p {font-size: .8rem;}
  .citrus-greeting {font-size: .92rem; line-height: 1.6;}
  .st-key-citrus_prompt {--prompt-h: 3.3rem;}
  .st-key-citrus_prompt input {font-size: 1rem;}
  .st-key-citrus_prompt [data-testid="stColumn"] [data-testid="stElementContainer"],
  .st-key-citrus_prompt [data-testid="stFormSubmitButton"] {width: 100% !important; max-width: 100%;}
  /* 대화 카드: 여백을 줄이고 아이콘은 위에 두어 본문이 화면 폭을 다 쓴다. */
  [data-testid="stChatMessage"] {padding: 1rem .9rem; border-radius: 18px; flex-direction: column; gap: .4rem;}
  [data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {width: 100%; margin-left: 0;}
  /* 넓은 표는 글자를 세로로 쪼개지 않고 옆으로 밀어서 본다. */
  .stApp [data-testid="stMarkdownContainer"] table {display: block; overflow-x: auto; max-width: 100%;}
  .stApp [data-testid="stMarkdownContainer"] td, .stApp [data-testid="stMarkdownContainer"] th {white-space: nowrap; padding: .4rem .6rem;}
}
</style>'''

# 화면 아래에서 해처럼 떠오르는 반쪽 귤 단면과 튀어 오르는 과즙.
# st.html은 <svg>를 지워 버리므로(1.65 확인) 그림 파일(data URI)로 넣는다.
CITRUS_SVG = art.main_art()
CITRUS_ART = ('<div class="citrus-art" aria-hidden="true"><img alt="" src="data:image/svg+xml;base64,'
              + base64.b64encode(CITRUS_SVG.encode()).decode() + '"></div>')

# 시작 화면의 귤 한 알. 배·사과처럼 보이지 않게 납작한 모양·오톨도톨한 껍질·별 모양 꼭지로 그리고,
# 주변에 과즙 방울이 계속 톡톡 튀어 오른다. 이모지는 운영체제마다 달라 쓰지 않는다.
WHOLE_CITRUS_SVG = art.whole_art()
WHOLE_CITRUS_URI = 'data:image/svg+xml;base64,' + base64.b64encode(WHOLE_CITRUS_SVG.encode()).decode()

SPLASH_CSS = '''<style>
[data-testid="stBottom"] {display: none;}
.citrus-splash {text-align: center; color: var(--ink); padding-top: clamp(1.5rem, 12vh, 7rem);}
.citrus-splash h1 {font-size: clamp(2.2rem, min(7vw, 8vh), 4.6rem); font-weight: 900; letter-spacing: -.045em; margin: 0; padding: 0; color: var(--ink);}
.citrus-splash p {font-weight: 700; margin: .4rem 0 0; opacity: .85;}
.st-key-citrus_enter {margin: clamp(.5rem, 4vh, 2.5rem) auto 0;}
/* 귤 한 알이 곧 버튼: 그림은 배경, 글자는 화면 읽기 프로그램용으로만 남긴다. */
.st-key-citrus_enter button {
  width: clamp(170px, min(42vw, 42vh), 320px); height: auto; aspect-ratio: 1; min-height: 0; padding: 0;
  border: 0; border-radius: 50%; box-shadow: none; cursor: pointer;
  background: url("''' + WHOLE_CITRUS_URI + '''") center / contain no-repeat,
              radial-gradient(closest-side, rgba(255, 176, 64, .45), rgba(255, 176, 64, 0));
  animation: citrus-bob 2.6s ease-in-out infinite; transition: transform .2s ease;
  /* 같은 감귤색 배경 위에서도 귤이 떠 보이도록 그림자를 깐다. */
  filter: drop-shadow(0 14px 18px rgba(120, 50, 0, .28));
}
.st-key-citrus_enter button:hover, .st-key-citrus_enter button:focus-visible {
  background: url("''' + WHOLE_CITRUS_URI + '''") center / contain no-repeat,
              radial-gradient(closest-side, rgba(255, 176, 64, .6), rgba(255, 176, 64, 0));
  animation-play-state: paused; transform: scale(1.07) rotate(-6deg);
}
.st-key-citrus_enter button:focus-visible {outline: 3px solid var(--ink); outline-offset: 6px;}
.st-key-citrus_enter button:active {transform: scale(.96);}
.st-key-citrus_enter button p {
  position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
}
.citrus-splash-hint {text-align: center; font-weight: 800; font-size: 1.05rem; color: var(--ink); margin-top: .6rem;}
@keyframes citrus-bob {0%, 100% {transform: translateY(0);} 50% {transform: translateY(-10px);}}
@media (prefers-reduced-motion: reduce) {.st-key-citrus_enter button {animation: none;}}
</style>'''


def enter():
    st.session_state.entered = True


def splash():
    """The first screen: one tangerine to click. Clicking it opens the main page."""
    st.html(CSS)
    st.html(SPLASH_CSS)
    st.html(f'<div class="citrus-splash"><h1>{title_html(BRAND)}</h1><p>{HEADLINE[1]}</p></div>')
    with st.container(key='citrus_enter', horizontal_alignment='center'):
        st.button('귤을 눌러 시작하기', key='citrus_enter_button', on_click=enter)
    st.html('<div class="citrus-splash-hint">귤을 눌러 시작하세요</div>')


def is_landing():
    return not st.session_state.get('messages')


def render(tools=None):
    """Draw the hero above the conversation. Returns a question chosen or typed here, if any.

    `tools` draws the small button row (새 대화·예시 질문·리포트·사용 안내) under the logo.
    """
    chosen = None
    st.html(CSS)
    if is_landing():
        # Before the first question the hero input is the only one; afterwards the
        # chat input stays at the bottom so a long conversation needs no scrolling up.
        st.html('<style>[data-testid="stBottom"] {display: none;}</style>')
        # The landing page is exactly one screen tall: the tangerine takes whatever height
        # is left under the question box, so it is always visible without scrolling.
        st.html('''<style>
        [data-testid="stMainBlockContainer"] {height: 100dvh; padding-bottom: 0;}
        .st-key-citrus_toolbar {margin: .9rem auto .2rem;}
        [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {height: 100%;}
        [data-testid="stElementContainer"]:has(.citrus-art) {flex: 1 1 0; min-height: 110px; display: flex; flex-direction: column;}
        [data-testid="stElementContainer"]:has(.citrus-art) > [data-testid="stHtml"] {flex: 1 1 0; min-height: 0;}
        .citrus-art {height: 100%; box-sizing: border-box; margin-top: 0; padding-top: .5rem;}
        .citrus-art img {height: 100%; max-height: 380px; object-fit: contain; object-position: center bottom; margin-top: auto;}
        .citrus-art {display: flex; flex-direction: column; justify-content: flex-end;}
        </style>''')
    st.html(f'<div class="citrus-topbar">{with_hanja(TOP_LINE)}</div>')
    if not is_landing():
        # During a conversation the big hero would fill a whole screen above the
        # answers; keep a slim band instead. '새 대화' brings the full hero back.
        st.html(f'<div class="citrus-band"><span class="citrus-logo">{with_hanja(BRAND)}</span>'
                f'<span class="citrus-band-sub">{HEADLINE[1]}</span></div>')
        # Keep 새 대화·예시 질문·리포트·사용 안내 reachable in a long conversation.
        st.html('<style>[data-testid="stLayoutWrapper"]:has(> .st-key-citrus_toolbar) {'
                'position: sticky; top: 0; z-index: 50; background: var(--bg); padding-top: .6rem;}</style>')
        if tools:
            tools()
        return None
    # The hero below already shows the name in large type; a second small logo here
    # only pushed the tangerine off the first screen.
    if tools:
        tools()
    st.html('<div class="citrus-hero"><h1>' + title_html(HEADLINE[0]) + '<span class="sub">' + HEADLINE[1]
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
