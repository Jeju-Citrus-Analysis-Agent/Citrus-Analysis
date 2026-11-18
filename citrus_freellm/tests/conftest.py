"""Skip checks that need 제주농산물수급관리센터(jasdc) data when it is not present.

That data may not be copied or redistributed without the centre's consent, so it is kept
out of git and out of the submission archive. After following the collection steps in the
manual, the files exist and every test below runs as usual.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JASDC_FILES = (
    ROOT / 'data' / 'processed' / 'citrus_production_yearly.csv',
    ROOT / 'data' / 'processed' / 'citrus_price_daily.csv',
    ROOT / 'data' / 'external' / 'cost' / 'standard_income.csv',
)
NEEDS_JASDC = {
    'test_consult.py::ConsultTest::test_consultation_uses_verified_numbers_profile_and_choices',
    'test_consult.py::ConsultTest::test_invented_number_is_retried_then_dropped',
    'test_consult.py::ConsultTest::test_plain_data_question_stays_local',
    'test_data_catalog.py::DataCatalogTests::test_processed_columns_take_units_from_their_names',
    'test_web.py::WebTests::test_long_explanation_shows_conclusion_and_chart_before_folded_details',
    'test_comparisons.py::ComparisonTests::test_real_registered_queries_add_comparisons',
    'test_local_tools.py::LocalToolTests::test_all_twenty_examples_work_without_model_or_key',
}


def pytest_collection_modifyitems(config, items):
    missing = [path.name for path in JASDC_FILES if not path.exists()]
    if not missing:
        return
    skip = pytest.mark.skip(reason='수급센터 자료 없음(이용약관상 미포함): ' + ', '.join(missing))
    for item in items:
        if item.nodeid.split('tests/', 1)[-1] in NEEDS_JASDC:
            item.add_marker(skip)
