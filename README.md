# 🍊 제주 감귤 분석 에이전트 (jeju_citrus)

제주 감귤 농가와 예비 창업자를 위한 **생산·유통·가격 데이터 분석 및 수급 예측 에이전트** 프로젝트입니다.

> 📌 **현재 단계: Phase 2 — 정제 파이프라인·심화 분석** (Phase 1 EDA 완료)
> 상세 요구사항과 진행 상황은 [`docs/requirements_spec.md`](docs/requirements_spec.md)를 참고하세요.

## 팀 검증용 감귤 도우미

별도 [`citrus_freellm`](citrus_freellm/README.md) 패키지에서 통계 조회·검증,
공개 분석 자료에 근거한 설명, 사용자 가정 계산과 리포트를 제공합니다.
Streamlit 화면은 저장소 루트에서 다음 명령으로 실행합니다.

```powershell
python -m pip install -r citrus_freellm/requirements-ui.txt
python -m streamlit run citrus_freellm/web.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

원자료 조회의 자연어 해석에는 자신의 FreeLLMAPI 서버·키가 필요합니다.
등록된 분석 설명과 가정 계산은 API 없이 사용할 수 있습니다.
[팀 검증 순서와 예상 결과](citrus_freellm/docs/TEAM_REVIEW.md)를 참고하세요.

---

## 🔍 주요 발견

[`01_eda`](notebooks/01_eda.ipynb) · [`02_trend_weather_timing`](notebooks/02_trend_weather_timing.ipynb) 결과 요약입니다.

| 주제 | 발견 | 근거 |
| --- | --- | --- |
| 수급과 가격 | 생산량이 1% 늘면 단가가 **2~3% 하락**합니다(탄력성 -2.2, 최근 10년 -2.9). 그래서 많이 생산된 해에는 조수입이 오히려 줄어듭니다. | 노지온주 22년 |
| 장기 추세 | 노지온주는 재배면적 **-29%**, 단가 **2배**, ha당 조수입 **2.2배** (2004년 → 2025년, 명목 가격) | 22년 |
| 품종 | 최근 3년 ha당 매출은 하우스온주가 노지의 **4.6배**이고, 천혜향 2.9배, 월동온주·레드향 2.4배 순입니다. (경영비 미반영) | 8개 품종 |
| 기상 | **여름이 더운 해일수록 ha당 생산량은 적고 단가는 높았습니다.** 추세를 제거한 뒤 여름 평균기온과 단가의 상관은 +0.83입니다. | 22년, 상관 |
| 출하 시기 | **10월 조기 출하는 5개 시즌 모두 12월보다 쌌습니다**(0.67~1.01배). 반면 2월 출하의 이득은 해마다 1.0~1.8배로 제각각이었고, **생산량으로는 설명되지 않았습니다**(2023·2025년산은 생산량이 거의 같은데 1.79배 vs 1.01배). | 5개 시즌 일별 |
| 2026년산 | 시즌 초반(9/1~11/8) 실측 결과 출하량은 전년보다 **+33%**, 도매가는 **-7%** 입니다. 폭염 기반 모델도 -7%를 예측하지만, 백테스트 오차가 '전년 단가 그대로'와 비슷해서(16.1% vs 16.9%) **근거는 시장 신호뿐**입니다. | 실측 (모델은 참고) |

---

## 📁 폴더 구조

```text
jeju_citrus/
├── data/
│   ├── raw/                  # 원본 데이터 (읽기 전용, 직접 수정 금지)
│   │   ├── public/           #   공공데이터 CSV (crop_production, fruit_production)
│   │   ├── distribution/     #   감귤 유통처리 통합 엑셀 (5개 시트 → processed/noji_*·varieties)
│   │   ├── jasdc/            #   jasdc 자동 수집 원본 (git 제외)
│   │   └── jasdc_manual/     #   jasdc 수동 다운로드 (git 제외)
│   │       ├── price_daily/        # 일별 총괄가격 엑셀 (price_whole_*.xlsx / .txt)
│   │       └── price_monthly_box/  # 월별 상자규격 가격 (price_monthly_box_*.txt)
│   ├── interim/              # 품질 이슈 정제 결과 *_clean.csv (코드로 재생성, git 제외)
│   ├── processed/            # 분석용 최종 데이터
│   └── external/             # 외부 데이터 (weather/: 기상청 ASOS 등)
│
├── docs/
│   └── requirements_spec.md  # 요구사항 정의서 (데이터 명세, 품질 이슈, 로드맵)
│
├── notebooks/                # 분석 노트북 (번호_주제.ipynb)
│   ├── 01_eda.ipynb          #   탐색적 데이터 분석
│   └── 02_trend_weather_timing.ipynb  # 장기 추세·기상 영향·출하 시기
│
├── reports/
│   └── figures/              # 저장된 그래프 (git 제외)
│
├── scripts/                  # 실행 진입점
│   ├── make_dataset.py       #   raw → processed·interim 전체 재생성
│   ├── check_quality.py      #   데이터 품질 이슈(Q3~Q11) 확인 근거 출력
│   ├── collect_jasdc.py      #   jasdc 수집 → 정제
│   └── run_eda.py            #   데이터 로드 확인용 간단 EDA
│
├── src/jeju_citrus/          # 재사용 코드 (패키지)
│   ├── config.py             #   경로·인코딩 등 공통 설정
│   ├── features.py           #   시즌별 기상 지표, 월별 가중평균 가격
│   ├── data/
│   │   ├── loader.py         #   load_raw(), load_processed()
│   │   ├── preprocess.py     #   parse_crop_year(), drop_total_rows()
│   │   ├── make_dataset.py   #   정제 파이프라인 (제주 데이터 추출 등)
│   │   ├── extract_distribution.py # 유통처리 엑셀 5개 시트 → noji_*·varieties CSV
│   │   ├── clean_quality.py  #   품질 이슈 Q3~Q5 정제 → interim/
│   │   ├── quality_checks.py #   Q7~Q11 원천 확인용 비교표
│   │   ├── collect_jasdc.py  #   jasdc 정적 표 수집
│   │   └── clean_jasdc.py    #   jasdc 원본 정제·검증
│   └── visualization/
│       └── style.py          #   set_style(), set_korean_font()
│
├── tests/                    # pytest 테스트
├── environment.yml           # conda 환경 정의 (Python 3.10)
├── pyproject.toml            # 패키지·의존성·도구 설정
└── requirements.txt          # 런타임 의존성
```

### 구조 원칙
| 원칙 | 설명 |
| --- | --- |
| **데이터 단방향 흐름** | 데이터는 `raw → interim → processed` 방향으로만 흐릅니다. `raw/`는 수정하지 않습니다. |
| **실험은 노트북, 재사용 코드는 `src/`** | 노트북에서 두 번 이상 쓰게 되는 코드는 `src/jeju_citrus/`의 함수로 옮기고 테스트를 작성합니다. |
| **경로 하드코딩 금지** | 모든 경로는 `config.py`에서만 정의합니다. 실행 위치와 상관없이 동작합니다. |
| **노트북 이름 규칙** | `01_eda.ipynb`, `02_price_analysis.ipynb`처럼 번호를 붙여 분석 순서를 드러냅니다. |

---

## 📊 데이터

| 위치 | 파일 | 내용 | 기간 |
| --- | --- | --- | --- |
| raw/public | `crop_production.csv` | 전국 특용작물 생산현황 (원본 이름 `시도별특용작물생산현황.csv`, [제주데이터허브](https://jejudatahub.net) 추정) | 2010~2023 |
| raw/public | `fruit_production.csv` | 제주 과수 품종별 생산면적·생산량 (원본 이름 `제주품종별과수생산량통계.csv`, [제주데이터허브](https://jejudatahub.net)) | 2015~2020 |
| raw/distribution | `distribution_analysis.xlsx` | 감귤 유통처리 통합 엑셀 (아래 noji_*, varieties의 원본). 출처: jasdc [유통처리 상황](https://jasdc.or.kr/tangerine/day/distribution/tangerine1.htm) 표를 시트 5개로 옮긴 것 | 2021~2025 |
| processed | `jeju_special_crops.csv` | 제주 특용작물 (raw에서 제주만 추출) | 2010~2023 |
| processed | `noji_yearly.csv` | 노지온주 연도별 처리량·단가·조수입 | 2021~2025 |
| processed | `noji_monthly_2025.csv` | 2025년산 노지온주 월별 출하량·가격 (도매+직거래 출하 기준) | 2025년산 |
| processed | `noji_market_2025.csv` | 2025년산 노지온주 도매시장별 거래량·가격 | 2025년산 |
| processed | `noji_size.csv` | 노지온주 규격(2S~2L)별 가격·거래비율 | 2023~2025 |
| processed | `varieties_summary.csv` | 하우스·월동·만감류 품종별 유통 비교 | 2024~2025 |
| processed | `citrus_production_yearly.csv` | **8개 품종** 연도별 재배면적·생산량·조수입·농가수·단가 + ha당 지표 | 2004~2025 |
| processed | `citrus_processing_yearly.csv` | 총처리량·가공처리량·가공률·수매단가 | 2004~2025 |
| processed | `citrus_processing_by_company.csv` | 가공업체별 가공처리량 | 2004~2025 |
| processed | `citrus_export_yearly.csv` | 국가별 수출량·수출액 | 2003~2025 |
| processed | `citrus_price_daily.csv` | 노지온주 일별 출하량·평균가 (도매/직거래) | 2021-10 ~ 2026-11 (5.2개 시즌) |
| processed | `citrus_price_monthly_box.csv` | 노지온주 월별·상자규격별 도매가격 | 2024 시즌 |
| external | `weather/asos_daily_*.csv` | 기상청 ASOS 일자료 원본 (cp949, 10년 단위 분할) | 2004-01 ~ 2026-11 |
| processed | `weather_daily.csv` | 제주·고산·성산·서귀포 일별 기온·강수·습도·일조·일사 | 2004-01 ~ 2026-11 |
| processed | `weather_monthly.csv` | 지점별 월 요약 + 폭염·열대야·영하·호우 일수 | 2004-01 ~ 2026-11 |
| interim | `varieties_summary_clean.csv` | 전년비 → 증감률로 바로잡은 품종별 유통 비교 (Q3) | 2024~2025 |
| interim | `fruit_production_clean.csv` | 대분류 통일 + `집계수준` 컬럼 (Q4) | 2015~2020 |
| interim | `jeju_special_crops_clean.csv` | 중복·소계·미재배 행 제거, 단수 재계산·이상 표시 (Q5) | 2010~2023 |

### ⚠️ 데이터를 쓸 때 알아둘 점 (품질 이슈 확인 결과)
- **단가는 `조수입 ÷ 처리량`입니다.** 생산량으로 나눈 값이 아닙니다. 2023~2024년 만감류·월동온주는 생산량과 처리량이 달라서 `단가 × 생산량 ≠ 조수입`입니다. 조수입은 `조수입_백만원`을 그대로 쓰고, 단가가 믿을 만한지는 `단가_검증` 컬럼으로 확인하세요(`확인불가` 4건은 제외 권장).
- **2017년에 재배면적 통계가 끊깁니다.** 온주밀감 면적이 줄고 레드향·천혜향·황금향 면적이 2.5~4.4배로 늘었지만 생산량은 그대로입니다. 2016년 이전과 이후의 면적·ha당 생산량을 바로 비교하지 마세요.
- **일별 출하 표는 처리량의 45~53%만 담습니다**(도매시장+직거래). 월별 상자규격 표와 9대 도매시장 표는 그 가운데 다시 53~58%입니다. 가격은 세 표 모두 같은 출처라 함께 써도 되지만, **물량은 섞지 마세요.**
- 자세한 근거: `python scripts/check_quality.py`, [요구사항 정의서 §4](docs/requirements_spec.md#4-데이터-품질-이슈-eda-결과)

### 외부 데이터 수집 (제주농산물수급관리센터)
`citrus_*.csv` 4종은 [제주농산물수급관리센터](https://jasdc.or.kr)의 공개 통계표를 수집·정제한 데이터입니다. `noji_*.csv`·`varieties_summary.csv`(원본 `distribution_analysis.xlsx`)도 같은 사이트의 [유통처리 상황](https://jasdc.or.kr/tangerine/day/distribution/tangerine1.htm) 화면(노지온주·하우스온주·월동온주·만감류 탭) 표입니다.

```bash
python scripts/collect_jasdc.py   # 수집(data/raw/jasdc/) → 정제(data/processed/citrus_*.csv)
```

- 수집 원본은 값을 그대로 `data/raw/jasdc/`에 저장하고, 수집 시각과 URL을 `manifest.json`에 기록합니다.
- 정제 단계에서 단위를 통일하고(만감류 조수입 억원 → 백만원), 원본 오타를 보정하고, 단가가 조수입 ÷ 생산량과 맞는지 검증합니다.
- **⚠️ 이용약관상 사전 승낙 없이 복제·유통·상업적으로 이용하는 것이 금지되어 있습니다.** 그래서 수집 데이터는 `.gitignore`로 git에서 제외했습니다. 새로 clone한 경우 위 명령으로 다시 수집하세요.
- 가격·출하 화면(일별·월별·도매시장별)은 JS로 데이터를 불러오는 구조라 자동으로 수집하지 않습니다. 화면의 '엑셀 다운로드'로 받아서 일별은 `data/raw/jasdc_manual/price_daily/`, 월별 상자규격은 `data/raw/jasdc_manual/price_monthly_box/`에 넣습니다.

> **⚠️ `crop_production.csv`가 깨져 보이는 이유**
> 이 파일은 공공데이터에서 흔히 쓰는 **cp949(EUC-KR)** 인코딩으로 저장되어 있습니다. VSCode는 기본적으로 UTF-8로 열기 때문에 한글이 깨져 보이지만, **파일 자체는 정상**입니다.
> - 코드에서는 `load_raw("crop_production.csv")`가 인코딩을 자동으로 처리합니다(`config.RAW_ENCODINGS`).
> - VSCode에서 보려면 오른쪽 아래 `UTF-8` 클릭 → `Reopen with Encoding` → `Korean (EUC-KR)`을 선택하세요.
> - 원본 보존 원칙에 따라 raw 파일은 변환하지 않습니다. processed 파일은 모두 UTF-8입니다.

> **raw에 엑셀(.xlsx)이 남아 있는 이유**
> raw는 받은 그대로 보관하는 곳이라 원본 형식을 바꾸지 않습니다. 분석에는 엑셀을 직접 쓰지 않고, 코드가 만든 **processed의 CSV**를 씁니다.
> - `distribution/distribution_analysis.xlsx` → `extract_distribution.py` → `processed/noji_*.csv`, `varieties_summary.csv` (시트 5개 → CSV 5개)
> - `jasdc_manual/price_daily/*.xlsx` → `clean_jasdc_manual.py` → `processed/citrus_price_daily.csv`
> - `load_raw("crop_production.csv")`처럼 파일 이름만 줘도 하위 폴더에서 찾아 읽습니다.

---

## 🚀 시작하기

### 1. 환경 설정 (최초 1회)
```bash
cd jeju_citrus

# conda 환경 생성: Python 3.10 + 의존성 + 프로젝트 패키지(편집 모드)를 한 번에 설치
conda env create -f environment.yml
conda activate jeju_citrus

# Jupyter 커널 등록 (노트북에서 이 환경을 쓰기 위해)
python -m ipykernel install --user --name jeju_citrus --display-name "Python 3.10 (jeju_citrus)"
```

> 의존성이 바뀌었을 때: `conda env update -f environment.yml --prune`
> 한글 폰트는 `koreanize-matplotlib` 패키지에 들어 있으므로 따로 설치할 필요가 없습니다.

### 2. 노트북으로 분석하기
- **VSCode:** `notebooks/01_eda.ipynb`을 열고 오른쪽 위 커널 선택에서 **Python 3.10 (jeju_citrus)** 를 고르세요.
- **브라우저:** `jupyter lab`

### 3. 스크립트 / 테스트
```bash
python scripts/collect_jasdc.py  # jasdc 데이터 수집·정제 (최초 1회)
python scripts/make_dataset.py   # 모든 원본(raw/external) → processed·interim 재생성
python scripts/check_quality.py  # 품질 이슈 확인 근거 출력
python scripts/run_eda.py        # 데이터 로드 확인
pytest                           # 테스트
ruff check .                     # 코드 스타일 검사
```

---

## 🧩 코드에서 사용하기

```python
from jeju_citrus.data import load_raw, load_processed
from jeju_citrus.data.preprocess import parse_crop_year, drop_total_rows
from jeju_citrus.visualization import set_style

set_style()  # seaborn 테마 + 한글 폰트

yearly = load_processed("noji_yearly")
yearly["연도"] = parse_crop_year(yearly["연도"])          # '2025년산' → 2025

monthly = drop_total_rows(load_processed("noji_monthly_2025"), "월구분")  # '계' 행 제거
fruit = load_raw("fruit_production.csv")                  # 인코딩 자동 처리
```

---

## 🗺️ 로드맵

| 단계 | 내용 | 상태 |
| --- | --- | --- |
| Phase 1 | EDA, 데이터 품질 이슈 파악, 장기 데이터(2004~2025) 확보 | ✅ |
| Phase 2 | 정제 파이프라인(품질 이슈 Q3~Q11 ✅), 가격·수익성 심화 분석 (경영비 반영 ⏳) | 🔄 진행 중 |
| Phase 3 | 기상 데이터 결합·상관분석 ✅, 병해충 데이터 ⏳ | 🔄 |
| Phase 4 | 예측 모델 (질의응답·리포트 에이전트는 담당 외) | ⏳ |

상세 내용은 [요구사항 정의서 §6](docs/requirements_spec.md#6-로드맵)을 참고하세요.
