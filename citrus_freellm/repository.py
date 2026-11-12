"""참조 저장소 위치 탐색과 정제 모듈 로딩. 원자료 검증기는 이 모듈을 쓰지 않는다."""
import importlib
import os
import sys
from pathlib import Path


def repository_root(package=None):
    """현재의 형제 폴더 배치와 Git 저장소 내부 배치를 모두 지원한다."""
    if configured := os.getenv("CITRUS_REPO_PATH"):
        return Path(configured).expanduser().resolve()
    parent = (package or Path(__file__).resolve().parent).parent
    for candidate in (parent, parent / "Citrus-Analysis"):
        if (candidate / "src/jeju_citrus/data/clean_quality.py").is_file():
            return candidate.resolve()
    return (parent / "Citrus-Analysis").resolve()


def cleaning_rules(root):
    """조회용 정제 규칙을 로드하되 반복 질문마다 sys.path를 늘리지 않는다."""
    source = str(root / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    return importlib.import_module("jeju_citrus.data.clean_quality")
