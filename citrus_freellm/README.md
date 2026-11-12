# 제주 감귤 분석 도우미

팀 검증용 CLI·Streamlit 도우미입니다. 생산 통계 조회·계산, 기존 분석에 근거한 설명,
사용자 가정에 따른 이익·손익분기 계산과 리포트 저장을 지원합니다.
기존 `citrus_agent.py`, `eda_tools.py`, 원본 데이터는 변경하지 않습니다.

## 가장 쉬운 웹 실행 (현재 컴퓨터)

`citrus_freellm/start-web.cmd`를 탐색기에서 더블클릭하세요.
브라우저에 `http://127.0.0.1:8501`이 열립니다. 창이 유지되는 동안 사용할 수 있습니다.
PowerShell이나 VS Code 터미널에서는 **citrus_freellm의 상위 폴더**에서 실행합니다.

```powershell
python -m pip install -r citrus_freellm/requirements-ui.txt
.\citrus_freellm\start-web.cmd
```

직접 실행하려면 다음 명령을 사용합니다. API 서버는 별도로 켜져 있어야 합니다.

```powershell
python -m streamlit run citrus_freellm/web.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

화면에는 채팅, 새 대화, 검증할 질문, 리포트 생성·다운로드가 있습니다.
에이전트는 브라우저 세션별로 분리됩니다. 새로고침·연결 종료·서버 재시작 시 대화가
초기화될 수 있으니 필요한 결과는 리포트로 저장하세요.

터미널 방식도 유지합니다. `start-agent.cmd` 더블클릭 또는 다음 명령입니다.

```powershell
python -m citrus_freellm
```

## 팀원이 Git에서 받은 뒤 설치

Python 3.10 이상이 필요합니다. 다음 두 배치를 지원합니다.

- Citrus-Analysis 저장소 **안**에 citrus_freellm 폴더가 있는 배치
- citrus_freellm과 Citrus-Analysis가 같은 상위 폴더에 나란히 있는 현재 배치

다른 위치의 참조 저장소는 `CITRUS_REPO_PATH` 환경 변수로 지정합니다.
생산 통계 조회에는 `src/jeju_citrus/data/clean_quality.py`와
`data/raw/public/fruit_production.csv`가 필요합니다. 원자료는 참조 저장소에서 읽습니다.

```powershell
python -m pip install -r citrus_freellm/requirements-ui.txt
Copy-Item citrus_freellm/.env.example citrus_freellm/.env
```

`.env`에 **자신의 FreeLLMAPI 서버 주소·통합 키**를 입력합니다. 서버 대시보드에서
공급자 키와 모델도 등록해야 합니다. 기존 `.env`가 있으면 복사로 덮어쓰지 마세요.
현재 실행의 기본 주소는 `http://127.0.0.1:3001/v1`입니다.

FreeLLMAPI 실행 파일·DB·키는 Git에 포함하지 않습니다. 자체 서버가 없다면
[공식 저장소](https://github.com/tashfeenahmed/freellmapi)의 설치 방법으로 준비하세요.
개발 시 확인한 로컬 서버의 참조 커밋은 `8cf07cf`입니다. `start-server.ps1`은 이 폴더의
`runtime/server/dist/index.js` 설치를 전제로 합니다. 외부 서버를 쓰면 웹을 직접 실행하세요.
`start-web.cmd`는 로컬 runtime이 없어도 화면을 열며 설명·가정 계산은 로컬에서 동작합니다.
처음부터 서버가 설치되고 키가 등록되는 자동 설치 도구는 아닙니다.

```powershell
python -m citrus_freellm --diagnose
```

위 명령은 실제 모델 연결을 확인합니다. API 키는 이 저장소의 Python 코드만으로 발급되지 않습니다.
대시보드(3001)와 도우미 웹 화면(8501)은 서로 다른 화면입니다.
공유한 Git 주소는 팀원이 설치할 코드를 제공하며 웹 서비스 주소가 아닙니다.

## 검증할 질문

```text
2019년과 2020년 천혜향 생산량 비교
그러면 2018년은?
생산면적은?
둘 다 알려줘
2020년 한라봉과 천혜향 생산량 비교
2020년 만감류 생산량 상위 3개
2019~2020년 천혜향 생산량 평균
어떤 데이터가 있어?
자세히
어떤 품종이 면적당 매출이 높나?
언제 팔면 비싼가?
생산량이 늘면 가격은?
날씨는 영향이 있나?
2026년산 가격은?
판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 10% 하락 시 이익은?
그럼 단가 20% 하락이면?
전체 리포트 저장
```

가정 계산은 이익 100만원 → 60만원, 손익분기 3,000원/kg입니다.
후속 20% 하락은 최초 단가 4,000원 기준으로 계산해 이익 20만원입니다.
변동률을 누적하지 않으며, 생산량을 판매가능수량으로 간주하지 않습니다.
경영비만 주면 총비용을 반영한 순이익이라고 부르지 않습니다.

## 답변 근거와 지원 범위

- 원자료 조회·계산: 생산량·생산면적의 연도 조회·비교, 같은 집계수준의 품종 비교·순위·연도 평균.
  조회 결과와 원본 CSV를 독립 경로로 대조합니다. 누락 값은 보간하지 않습니다.
- 분석 설명: 검토된 다섯 주제의 문서 스냅샷·인용을 확인하고 적용 범위·해석·대안·한계를 제시합니다.
  현재 없는 장기 생산·가격 CSV를 새로 계산했다고 표현하지 않습니다.
- 가정 계산: 사용자 판매가능수량·단가·비용을 Decimal로 계산합니다. 미래 예측이 아닙니다.

수확·재배면적을 생산면적으로 확정하지 않습니다. 2017년 면적 통계 단절을 가로지르는
면적 변화·평균은 보류합니다. 일반 상식으로 인과관계를 확정하거나 미래 시세를 만들지 않습니다.
문서의 해시 일치는 문서 내용 자체의 정확성까지 증명하지 않습니다.

## 리포트·데이터 관리

웹에서 저장 범위 선택 → 리포트 만들기 → 다운로드를 누릅니다.
질문창에서는 `리포트 저장`/`/report`(최근 1개),
`전체 리포트 저장`/`/report all`(최근 최대 30개)을 사용합니다.
`reports/exported` 아래 HTML·Markdown·JSON을 저장합니다. 실패한 요청은 성공 기록에 넣지 않습니다.
`/reset` 또는 새 대화는 메모리를 비우며 이미 저장한 파일은 유지합니다.

`.env`, 로그인 정보, runtime, 로그, 리포트, 캐시는 `.gitignore`로 제외합니다.
`.env.example`은 값 없는 설정 양식입니다. 실제 키를 이 파일에 넣지 마세요.
`knowledge`에는 공개 README·노트북에서 필요한 문장만 발췌해 포함합니다. 내부 Slack 문서 사본은 제외합니다.

인식된 가정 계산의 금액·수량과 분석 원문은 외부 모델에 보내지 않습니다. 일반 조회·의도 해석에는 현재 질문과
검증된 이전 조회 조건이 공급자로 전송될 수 있습니다. 이전 대화 전체는 첨부하지 않습니다.
UI는 기본적으로 이 컴퓨터의 127.0.0.1에만 연결합니다.

## 테스트와 구조

```powershell
python -m unittest discover -s citrus_freellm/tests -v
```

현재 152개 통과: 기존 조회 회귀·변조·정의·시나리오·출처·리포트 검사에
저장소 배치/누락 의존성/깃 제외/Windows 체크아웃 5개와 UI 상태/초기화/다운로드/세션 분리/오류 처리 5개를 추가했습니다.
UI 의존성이 없으면 UI 테스트 5개는 건너뜁니다. 테스트의 모델 응답은 모의 응답이며 외부 호출하지 않습니다.

질문별 기대 결과는 [팀 검증 안내](docs/TEAM_REVIEW.md),
모듈과 검증·가정 계산 설계는 [설계 문서](docs/DESIGN.md)를 참고하세요.
현재 파일의 정의·기간 안내는 `python -m citrus_freellm --data-guide`로 생성합니다.
실제 모델 평가는 별도 명시 실행인 `python -m citrus_freellm.evaluate --live`입니다.
실행하면 평가 질문과 조회 조건을 외부 공급자에게 전송합니다.

구현은 Streamlit의 [채팅](https://docs.streamlit.io/develop/api-reference/chat),
[세션 상태](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state),
[앱 테스트](https://docs.streamlit.io/develop/concepts/app-testing/cheat-sheet) API를 사용합니다.
