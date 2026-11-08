import pandas as pd

from jeju_citrus.data.preprocess import drop_total_rows, parse_crop_year


def test_parse_crop_year():
    s = pd.Series(["2025년산", "2021년산"])
    assert parse_crop_year(s).tolist() == [2025, 2021]


def test_drop_total_rows():
    df = pd.DataFrame({"품종": ["계", "한라봉", "소계", "천혜향"], "v": [1, 2, 3, 4]})
    assert drop_total_rows(df, "품종")["품종"].tolist() == ["한라봉", "천혜향"]
