"""Matplotlib / Seaborn 공통 스타일 (한글 폰트 포함).

한글 폰트는 ``koreanize-matplotlib`` 패키지에 내장된 NanumGothic을 사용하므로
OS에 폰트를 따로 설치(sudo)하지 않아도 됩니다.
"""

import koreanize_matplotlib  # noqa: F401  (import 시 NanumGothic 등록)
import matplotlib.pyplot as plt
import seaborn as sns

KOREAN_FONT = "NanumGothic"


def set_korean_font(family: str = KOREAN_FONT) -> None:
    """한글 폰트를 설정하고 마이너스 기호 깨짐을 막는다."""
    plt.rc("font", family=family)
    plt.rcParams["axes.unicode_minus"] = False


def set_style(context: str = "notebook") -> None:
    """프로젝트 기본 그래프 스타일을 적용한다.

    ``sns.set_theme``은 폰트를 초기화하므로 반드시 그 뒤에 한글 폰트를 다시 지정한다.
    """
    sns.set_theme(style="whitegrid", context=context)
    set_korean_font()
    plt.rcParams["figure.figsize"] = (10, 5)
    plt.rcParams["figure.dpi"] = 100
