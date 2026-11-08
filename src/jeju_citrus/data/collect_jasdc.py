"""제주농산물수급관리센터(jasdc.or.kr) 감귤 통계 수집기.

정적 HTML 표만 수집한다(생산정보 8개 품종, 가공처리현황, 수출현황).
수집 결과는 **값을 손대지 않은 문자열 그대로** ``data/raw/jasdc/``에 저장하고,
정제(숫자 변환·단위 통일·오타 보정)는 ``clean_jasdc.py``에서 한다.

⚠️ 이용약관상 사전 승낙 없이 복제·유통·상업적 이용이 금지되어 있으므로
   수집 데이터는 개인 학습·분석 용도로만 사용하고 git에 올리지 않는다(.gitignore).

실행: python scripts/collect_jasdc.py
"""

import io
import json
import time
from datetime import datetime

import pandas as pd
import requests

from jeju_citrus.config import JASDC_RAW_DIR

BASE_URL = "https://jasdc.or.kr"
USER_AGENT = "jeju-citrus-study/0.1 (personal research)"
REQUEST_INTERVAL_SEC = 1.0  # 서버 부담을 줄이기 위한 요청 간격

# 저장 파일명 → (페이지 경로, 페이지 내 표 순서)
PAGES: dict[str, tuple[str, int]] = {
    "production_노지온주": ("/tangerine/output/output1.htm", 0),
    "production_하우스온주": ("/tangerine/output/output2.htm", 0),
    "production_월동온주": ("/tangerine/output/output3.htm", 0),
    "production_한라봉": ("/tangerine/output/output4.htm", 0),
    "production_천혜향": ("/tangerine/output/output5.htm", 0),
    "production_레드향": ("/tangerine/output/output6.htm", 0),
    "production_황금향": ("/tangerine/output/output7.htm", 0),
    "production_카라향": ("/tangerine/output/output8.htm", 0),
    "processing": ("/tangerine/processing.htm", 0),
    "processing_by_company": ("/tangerine/processing.htm", 1),
    "export": ("/tangerine/export.htm", 0),
}


def fetch_html(session: requests.Session, path: str) -> str:
    resp = session.get(BASE_URL + path, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_table(html: str, index: int) -> pd.DataFrame:
    """HTML에서 ``index``번째 표를 문자열 그대로 읽는다(빈 칸은 빈 문자열)."""
    tables = pd.read_html(io.StringIO(html), thousands=None, keep_default_na=False)
    return tables[index].astype(str)


def collect(out_dir=JASDC_RAW_DIR) -> dict[str, int]:
    """모든 페이지를 수집해 CSV와 수집 기록(manifest.json)을 저장한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    html_cache: dict[str, str] = {}
    manifest = {
        "source": BASE_URL,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "files": {},
    }
    for name, (path, index) in PAGES.items():
        if path not in html_cache:
            if html_cache:
                time.sleep(REQUEST_INTERVAL_SEC)
            html_cache[path] = fetch_html(session, path)
        df = parse_table(html_cache[path], index)
        df.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
        manifest["files"][name] = {"url": BASE_URL + path, "table_index": index, "rows": len(df)}
        print(f"[수집] {name:<24} {len(df):>3}행  ← {path}")

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {k: v["rows"] for k, v in manifest["files"].items()}


def main() -> None:
    collect()


if __name__ == "__main__":
    main()
