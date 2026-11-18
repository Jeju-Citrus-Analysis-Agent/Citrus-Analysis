import pytest

from jeju_citrus.config import JEJU_REGION_NAME, PROCESSED_DIR, RAW_DIR
from jeju_citrus.data import load_processed, load_raw
from jeju_citrus.data.loader import PROCESSED_DATASETS
from jeju_citrus.data.make_dataset import filter_jeju


def test_data_dirs_exist():
    assert RAW_DIR.is_dir()
    assert PROCESSED_DIR.is_dir()


@pytest.mark.parametrize("name", list(PROCESSED_DATASETS))
def test_load_processed(name):
    try:
        df = load_processed(name)
    except FileNotFoundError:
        # 제주농산물수급관리센터 자료는 이용약관(복제·유통 금지) 때문에 저장소·제출본에 넣지 않는다.
        # 매뉴얼의 수집 절차로 만든 뒤에 이 검사가 실행된다.
        pytest.skip(f"{name}: 수급센터 자료라 포함하지 않음 (수집 후 검사)")
    assert not df.empty


def test_load_processed_unknown_name():
    with pytest.raises(KeyError):
        load_processed("not_exists")


def test_filter_jeju_matches_processed():
    raw = load_raw("crop_production.csv")
    jeju = filter_jeju(raw)
    assert (jeju["시도"] == JEJU_REGION_NAME).all()
    assert len(jeju) == len(load_processed("jeju_special_crops"))


def test_load_raw_finds_file_in_subfolder():
    from jeju_citrus.config import RAW_CROP_PRODUCTION
    from jeju_citrus.data.loader import find_raw

    if not RAW_CROP_PRODUCTION.exists():
        pytest.skip("crop_production.csv 없음")
    assert find_raw("crop_production.csv") == RAW_CROP_PRODUCTION
    assert find_raw("public/crop_production.csv") == RAW_CROP_PRODUCTION
