"""대회 제출용 zip을 만든다.

실행: python scripts/make_submission.py [--with-jasdc] [--out dist/감귤의신_제출.zip]

구성
  1_실행소스코드/            git에 올라간 파일 그대로 (git archive). .env·캐시·수급센터 자료는 빠진다.
  2_실행환경_및_매뉴얼/      docs/submission/01_*.pdf
  3_데이터_활용_명세/        docs/submission/02_*.pdf
  4_결과_설명_자료/          docs/submission/03_*.pdf
  README.txt                 폴더 안내

--with-jasdc: 제주농산물수급관리센터 자료(정제 CSV)를 1_실행소스코드/data 아래에 함께 넣는다.
  이용약관상 사전 승낙 없는 복제·유통이 금지되어 있으므로, 대회 규정·센터 승낙을 확인한 경우에만 쓴다.
"""
import argparse
import io
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "submission"
SECTIONS = {
    "01_": "2_실행환경_및_매뉴얼",
    "02_": "3_데이터_활용_명세",
    "03_": "4_결과_설명_자료",
}
JASDC_DATA = [
    "data/processed/citrus_*.csv",
    "data/processed/noji_*.csv",
    "data/processed/varieties_summary.csv",
    "data/interim/*.csv",
    "data/external/cost/*.csv",
]
README = """감귤의 신(神) - 데이터로 읽는 제주 감귤 수급 비서 : 제출물 안내

1_실행소스코드/        프로그램 전체 (실행 방법은 2번 문서, 또는 README.md)
2_실행환경_및_매뉴얼/  설치·데이터 준비·실행·검사 방법
3_데이터_활용_명세/    데이터 출처·이용 조건·가공 과정·컬럼 정의·품질 이슈
4_결과_설명_자료/      분석 결과와 에이전트 화면 설명

빠른 실행 (Python 3.10):
  cd 1_실행소스코드
  pip install -r requirements.txt -r citrus_freellm/requirements-ui.txt && pip install -e .
  python -m streamlit run citrus_freellm/web.py
  브라우저에서 http://127.0.0.1:8501

{jasdc_note}
"""
NOTE_WITHOUT = ("제주농산물수급관리센터 자료는 이용약관(사전 승낙 없는 복제·유통 금지) 때문에 넣지 않았습니다.\n"
                "자료 없이도 실행되며, 해당 질문에는 안내가 나옵니다. 받는 방법은 2번 문서 4.2절에 있습니다.")
NOTE_WITH = "제주농산물수급관리센터 자료(정제 CSV)를 포함했습니다. 출처: 제주농산물수급관리센터(jasdc.or.kr)."


def tracked_archive() -> bytes:
    """HEAD 커밋의 파일만 tar로 받는다 (작업 중인 변경·.env·캐시는 들어가지 않음)."""
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True)
    if status.stdout.strip():
        print("주의: 커밋하지 않은 변경이 있습니다. zip에는 마지막 커밋(HEAD) 내용만 들어갑니다.", file=sys.stderr)
    return subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--with-jasdc", action="store_true", help="수급센터 정제 자료 포함 (규정·승낙 확인 후에만)")
    parser.add_argument("--out", default=str(ROOT / "dist" / "감귤의신_제출.zip"))
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    import tarfile

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        names = set()
        with tarfile.open(fileobj=io.BytesIO(tracked_archive())) as tar:
            for member in tar.getmembers():
                if member.isfile():
                    zf.writestr(f"1_실행소스코드/{member.name}", tar.extractfile(member).read())
                    names.add(member.name)
        if args.with_jasdc:
            for pattern in JASDC_DATA:
                for path in sorted(ROOT.glob(pattern)):
                    rel = path.relative_to(ROOT).as_posix()
                    if rel not in names:
                        zf.write(path, f"1_실행소스코드/{rel}")
        for prefix, folder in SECTIONS.items():
            pdfs = sorted(DOCS.glob(prefix + "*.pdf"))
            if not pdfs:
                print(f"없음: docs/submission/{prefix}*.pdf", file=sys.stderr)
                return 1
            for pdf in pdfs:
                zf.write(pdf, f"{folder}/{pdf.name}")
        zf.writestr("README.txt", README.format(jasdc_note=NOTE_WITH if args.with_jasdc else NOTE_WITHOUT))

    with zipfile.ZipFile(out) as zf:
        leaked = [n for n in zf.namelist() if n.rsplit("/", 1)[-1] == ".env" or "__pycache__" in n]
        if leaked:
            print("오류: 넣으면 안 되는 파일이 들어갔습니다:", leaked, file=sys.stderr)
            return 1
        print(f"만듦: {out}  ({len(zf.namelist())}개 파일, {out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
