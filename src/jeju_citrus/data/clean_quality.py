"""데이터 품질 이슈(요구사항 정의서 §4 Q3~Q5) 정제 → data/interim.

원본(raw)과 processed 파일은 건드리지 않고, 정제한 결과만 ``data/interim/``에 저장한다.

생성 파일
- interim/varieties_summary_clean.csv  : [Q3] 전년비 → 증감률 변환
- interim/fruit_production_clean.csv   : [Q4] 품종 → 대분류 매핑 통일, 집계수준 표시
- interim/jeju_special_crops_clean.csv : [Q5] 중복·소계·미재배 행 제거, 단수 재계산·이상치 표시
"""

import numpy as np
import pandas as pd

from jeju_citrus.config import DEFAULT_ENCODING, INTERIM_DIR

# ------------------------------------------------------------------ Q3 varieties_summary
GROWTH_COLS = ("처리량", "조수입")


def fix_varieties_growth(df: pd.DataFrame) -> pd.DataFrame:
    """[Q3] ``*_증감률_퍼센트``(실제로는 전년비, 101 = +1%)를 바로잡는다.

    - 원래 값은 ``*_전년비_퍼센트``로 이름을 바꿔 남긴다.
    - ``*_증감률_퍼센트``는 2025·2024 원값으로 다시 계산한다(소수 1자리, +1.0 = 1% 증가).
      원본 전년비는 정수로 반올림되어 있어 -100 만 하면 최대 ±0.5%p 오차가 생기기 때문이다.
    """
    out = df.copy()
    for col in GROWTH_COLS:
        old = f"{col}_증감률_퍼센트"
        out = out.rename(columns={old: f"{col}_전년비_퍼센트"})
        cur = out[next(c for c in out.columns if c.startswith(f"{col}_2025_"))]
        prev = out[next(c for c in out.columns if c.startswith(f"{col}_2024_"))]
        out[old] = ((cur / prev - 1) * 100).round(1)
    return out


# ------------------------------------------------------------------ Q4 fruit_production
# 품종소분류 → (대분류, 집계수준)
#   감귤_재배형태 : 감귤 전체를 재배형태로 나눈 행 (합치면 감귤 전체)
#   만감류_품종   : 만감류노지 + 만감류하우스를 품종별로 다시 나눈 행
#                  (감귤_재배형태와 더하면 이중 집계)
#   기타과수     : 감귤이 아닌 과수
FRUIT_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "온주밀감노지": ("감귤", "감귤_재배형태"),
    "온주밀감하우스": ("감귤", "감귤_재배형태"),
    "온주밀감월동": ("감귤", "감귤_재배형태"),
    "만감류노지": ("감귤", "감귤_재배형태"),
    "만감류하우스": ("감귤", "감귤_재배형태"),
    "한라봉": ("만감류", "만감류_품종"),
    "천혜향": ("만감류", "만감류_품종"),
    "레드향": ("만감류", "만감류_품종"),
    "황금향": ("만감류", "만감류_품종"),
    "진지향": ("만감류", "만감류_품종"),
    "청견": ("만감류", "만감류_품종"),
    "금감": ("만감류", "만감류_품종"),
    "만감류기타": ("만감류", "만감류_품종"),
    "단감": ("기타", "기타과수"),
    "참다래": ("기타", "기타과수"),
    "망고": ("기타", "기타과수"),
    "매실": ("기타", "기타과수"),
    "블루베리": ("기타", "기타과수"),
    "무화과": ("기타", "기타과수"),
    "바나나": ("기타", "기타과수"),
    "용과": ("기타", "기타과수"),
    "구아바": ("기타", "기타과수"),
    "포도": ("기타", "기타과수"),
    "기타": ("기타", "기타과수"),
}


def clean_fruit_production(df: pd.DataFrame) -> pd.DataFrame:
    """[Q4] 제주 과수 생산량 표의 대분류를 연도와 무관하게 하나로 통일한다.

    원본은 2016년부터 ``레드향``(→기타)과 ``단감``(→만감류)의 대분류가 서로 뒤바뀌어 있고,
    2015년에는 만감류의 기타 품종이 ``만감류 / 기타``로 적혀 있다(2016년 이후 ``만감류기타``).
    """
    out = df.rename(
        columns={
            "기준연도": "연도",
            "품종대분류": "원본_대분류",
            "품종소분류": "품종",
            "생산면적(ha)": "생산면적_ha",
            "생산량(톤)": "생산량_톤",
        }
    ).copy()
    is_mandarin_etc = (out["원본_대분류"] == "만감류") & (out["품종"] == "기타")
    out.loc[is_mandarin_etc, "품종"] = "만감류기타"

    unknown = set(out["품종"]) - set(FRUIT_CATEGORY_MAP)
    if unknown:
        raise ValueError(f"FRUIT_CATEGORY_MAP에 없는 품종: {sorted(unknown)}")

    out["대분류"] = out["품종"].map(lambda v: FRUIT_CATEGORY_MAP[v][0])
    out["집계수준"] = out["품종"].map(lambda v: FRUIT_CATEGORY_MAP[v][1])
    out["대분류_보정"] = out["대분류"] != out["원본_대분류"]
    cols = ["연도", "대분류", "집계수준", "품종", "생산면적_ha", "생산량_톤", "원본_대분류"]
    return (
        out[cols + ["대분류_보정"]].sort_values(["연도", "집계수준", "품종"]).reset_index(drop=True)
    )


def validate_fruit_hierarchy(df: pd.DataFrame, tolerance: float = 0.01) -> pd.DataFrame:
    """만감류 품종 합계가 ``만감류노지 + 만감류하우스``와 맞는지 연도별로 확인한다.

    ``clean_fruit_production()`` 결과를 받는다. 매핑이 맞으면 모든 연도의 차이율이 1% 이내다.
    """
    total = df[df["품종"].isin(["만감류노지", "만감류하우스"])].groupby("연도")
    parts = df[df["집계수준"] == "만감류_품종"].groupby("연도")
    res = pd.DataFrame(
        {
            "재배형태합_ha": total["생산면적_ha"].sum(),
            "품종합_ha": parts["생산면적_ha"].sum(),
            "재배형태합_톤": total["생산량_톤"].sum(),
            "품종합_톤": parts["생산량_톤"].sum(),
        }
    )
    res["면적_차이율"] = (res["품종합_ha"] / res["재배형태합_ha"] - 1).round(4)
    res["생산량_차이율"] = (res["품종합_톤"] / res["재배형태합_톤"] - 1).round(4)
    res["통과"] = (res[["면적_차이율", "생산량_차이율"]].abs() <= tolerance).all(axis=1)
    return res.reset_index()


# ------------------------------------------------------------------ Q5 jeju_special_crops
# 2023년에만 나오는 품목군 소계 행 (개별 품목과 함께 있어 그대로 더하면 이중 집계)
SPECIAL_CROP_SUBTOTALS = ("기타특작", "기호작물", "버섯류", "섬유작물", "약용작물", "유지작물")
# 버섯은 면적 대신 재배사 기준이라 단수(kg/10a)를 다른 작물과 비교할 수 없다
MUSHROOMS = ("느타리", "새송이", "양송이", "팽이", "영지", "상황", "신령")
SMALL_AREA_HA = 3  # 1~2ha는 ha 단위 반올림만으로 단수가 25~50% 흔들린다 (3~4ha는 20% 넘는 차이 6%)
YIELD_GAP_LIMIT = 0.5  # 원본 단수가 계산 단수와 50% 넘게 다르면 이상치


def clean_special_crops(df: pd.DataFrame) -> pd.DataFrame:
    """[Q5] 제주 특용작물 생산현황 정제.

    1. 완전히 같은 중복행 제거 (2017년 '기타' 0값 행 1건)
    2. 2023년 품목군 소계 행 제거 (기호작물 = 차, 유지작물 = 유채+참깨+땅콩+들깨 등)
    3. 모든 값이 0인 행 제거 — 2018년부터 표에 전국 품목이 전부 실리면서 생긴 '제주 미재배' 행
    4. 단수 재계산: ``단수_계산 = 생산량 × 100 / 수확면적`` (kg/10a)
       원본 단수가 0인데 생산량이 있는 행은 원본 단수를 결측으로 본다
    5. ``단수_이상`` 표시: 버섯, 수확면적 < 3ha, 원본·계산 단수 50% 초과 차이
    """
    out = df.rename(
        columns={
            "기준 연도": "연도",
            "농가수[호]": "농가수_호",
            "재배면적[ha]": "재배면적_ha",
            "수확면적[ha]": "수확면적_ha",
            "단수[kg/10a]": "단수_kg_10a",
            "생산량[M/T]": "생산량_톤",
        }
    ).drop(columns="시도", errors="ignore")

    out = out.drop_duplicates()
    out = out[~out["품명"].isin(SPECIAL_CROP_SUBTOTALS)]
    values = ["농가수_호", "재배면적_ha", "수확면적_ha", "단수_kg_10a", "생산량_톤"]
    out = out[~(out[values].fillna(0) == 0).all(axis=1)].copy()

    zero_yield = (out["단수_kg_10a"] == 0) & (out["생산량_톤"] > 0)
    out.loc[zero_yield, "단수_kg_10a"] = np.nan

    area = out["수확면적_ha"].where(out["수확면적_ha"] > 0)
    out["단수_계산_kg_10a"] = (out["생산량_톤"] * 100 / area).round(1)

    gap = (out["단수_kg_10a"] / out["단수_계산_kg_10a"] - 1).abs()
    reasons = pd.Series("", index=out.index)
    reasons = reasons.mask(out["품명"].isin(MUSHROOMS), "버섯(단위 다름)")
    reasons = reasons.mask((reasons == "") & (out["수확면적_ha"] < SMALL_AREA_HA), "소면적")
    reasons = reasons.mask((reasons == "") & (gap > YIELD_GAP_LIMIT), "원본·계산 불일치")
    out["단수_이상"] = reasons.replace("", None)
    # 같은 해에 '기타'가 여러 번 나온다(원본에서 품목군 정보가 빠짐) → 순번으로 구분
    is_etc = out["품명"] == "기타"
    out.loc[is_etc, "품명"] = "기타_" + (out[is_etc].groupby("연도").cumcount() + 1).astype(str)
    return out.reset_index(drop=True)


# ------------------------------------------------------------------ 실행
def main() -> None:
    from jeju_citrus.config import RAW_FRUIT_PRODUCTION
    from jeju_citrus.data.loader import load_processed, load_raw

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "varieties_summary_clean": fix_varieties_growth(load_processed("varieties_summary")),
        "fruit_production_clean": clean_fruit_production(load_raw(RAW_FRUIT_PRODUCTION.name)),
        "jeju_special_crops_clean": clean_special_crops(load_processed("jeju_special_crops")),
    }
    for name, df in outputs.items():
        df.to_csv(INTERIM_DIR / f"{name}.csv", index=False, encoding=DEFAULT_ENCODING)
        print(f"[저장] interim/{name}.csv ({len(df)}행)")

    check = validate_fruit_hierarchy(outputs["fruit_production_clean"])
    if not check["통과"].all():
        print("⚠️ 만감류 품종 합계 ≠ 만감류노지+하우스:")
        print(check[~check["통과"]].to_string(index=False))


if __name__ == "__main__":
    main()
