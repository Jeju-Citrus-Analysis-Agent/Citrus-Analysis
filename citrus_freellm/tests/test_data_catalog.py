import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.data_catalog import catalog, definitions, metadata_answer, profile, source_lines
from citrus_freellm.guardrails import request_for


class DataCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog()
        cls.records = {record["name"]: record for record in cls.data["datasets"]}

    def test_observed_periods_and_availability(self):
        fruit = self.records["fruit_production"]
        self.assertEqual(fruit["observed_period"]["values"], [2015, 2016, 2017, 2018, 2019, 2020])
        self.assertEqual(fruit["row_count"], 144)
        self.assertEqual(fruit["duplicate_key_rows"], 0)
        self.assertEqual(self.records["jeju_special_crops"]["observed_period"]["end"], 2023)
        self.assertEqual(self.records["weather_daily"]["observed_period"]["end"], "2026-11-07")

    def test_documented_period_not_claimed_as_local_coverage(self):
        record = self.records["citrus_production_yearly"]
        self.assertFalse(record["available"])
        self.assertEqual(record["documented_period"], "2004~2025")
        self.assertIsNone(record["observed_period"])
        self.assertEqual(record["status"], "파일 없음")

    def test_definitions_and_units_cover_present_columns(self):
        for record in self.data["datasets"]:
            if not record["available"]:
                continue
            for column in record["columns"]:
                with self.subTest(dataset=record["name"], column=column["name"]):
                    self.assertNotEqual(column["status"], "미확인")
                    self.assertIn("null_count", column)
        fruit = {c["name"]: c for c in self.records["fruit_production"]["columns"]}
        self.assertEqual(fruit["생산면적(ha)"]["unit"], "ha")
        self.assertIn("미확인", fruit["생산면적(ha)"]["status"])

    def test_partial_month_and_nulls_are_exposed(self):
        monthly = self.records["weather_monthly"]
        self.assertEqual(len(monthly["short_months"]), 4)
        self.assertTrue(all(row["month"] == "2026-11" and row["observed_days"] == 7 and row["calendar_days"] == 30 for row in monthly["short_months"]))
        daily = self.records["weather_daily"]
        self.assertEqual(len(daily["stations"]), 4)
        radiation = next(c for c in daily["columns"] if c["name"] == "일사량_mj_m2")
        self.assertGreater(radiation["null_count"], 0)

    def test_new_file_period_is_read_not_hardcoded(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            path = root / "data/raw/public/fruit_production.csv"
            path.parent.mkdir(parents=True)
            path.write_text("기준연도,품종대분류,품종소분류,생산면적(ha),생산량(톤)\n2022,만감류,한라봉,1,2\n", encoding="utf-8")
            record = profile(root, "fruit_production", definitions()["fruit_production"])
            self.assertEqual(record["observed_period"]["end"], 2022)
            self.assertEqual(record["documented_period"], "2015~2020")

    def test_unknown_column_not_given_an_invented_unit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            (root / "test.csv").write_text("unknown\n1\n", encoding="utf-8")
            record = profile(root, "test", {"path": "test.csv", "fields": {}})
            self.assertEqual(record["columns"][0]["status"], "미확인")
            self.assertIsNone(record["columns"][0]["unit"])

    def test_missing_and_corrupt_files_not_reported_as_valid(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            spec = definitions()["fruit_production"]
            self.assertFalse(profile(root, "fruit_production", spec)["available"])
            path = root / spec["path"]
            path.parent.mkdir(parents=True)
            path.write_bytes(b'\xff\xfe\xff')
            record = profile(root, "fruit_production", spec)
            self.assertEqual(record["status"], "검사 실패")
            self.assertIsNone(record["observed_period"])

    def test_metadata_questions_are_local_and_keep_context(self):
        client = Mock()
        agent = Agent(client)
        previous = request_for("2019년 천혜향 생산량")[0]
        agent.previous_request = previous
        for question, expected in (("생산량 데이터는 몇 년까지 있어?", "2015~2020"),
                                   ("기상 데이터 기간 알려줘", "7/30일"),
                                   ("생산면적과 수확면적은 같은 거야?", "정의가 같다는 근거는 확인되지"),
                                   ("가격 데이터 있어?", "파일 없음"),
                                   ("어떤 데이터가 있어?", "현재 로컬 파일 기준")):
            answer = agent.ask(question)
            self.assertIn(expected, answer)
            self.assertEqual(agent.previous_request, previous)
        client.complete.assert_not_called()

    def test_statistical_question_is_not_rerouted_to_metadata(self):
        for question in ("2019년과 2020년 천혜향 생산량 비교", "2019년과 2020년 천혜향 생산면적 차이는?", "둘 다 알려줘", "2016년 한라봉 수확면적", "2019년 천혜향 생산량 톤 단위로 알려줘"):
            self.assertIsNone(metadata_answer(question))

    def test_metadata_unavailable_root_does_not_claim_original_files_exist(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder, \
             patch("citrus_freellm.tools.ROOT", Path(folder)):
            data = catalog()
            self.assertTrue(all(not r["available"] for r in data["datasets"]))

    def test_general_production_question_includes_special_crops(self):
        answer = metadata_answer("생산량 데이터는 몇 년까지 있어?")
        self.assertIn("2010~2023", answer)
        self.assertIn("특용작물", answer)

    def test_price_question_excludes_processing_and_export(self):
        answer = metadata_answer("가격 데이터 있어?")
        self.assertIn("가격 관련 자료는 현재 로컬에 없습니다", answer)
        self.assertNotIn("citrus_processing_yearly.csv", answer)
        self.assertNotIn("citrus_processing_by_company.csv", answer)
        self.assertNotIn("citrus_export_yearly.csv", answer)

    def test_missing_paths_not_labeled_as_inspected_evidence(self):
        answer = metadata_answer("어떤 데이터가 있어? 자세히")
        actual_line = next(line for line in answer.splitlines() if line.startswith("실제 확인한 파일:"))
        self.assertIn("fruit_production.csv", actual_line)
        self.assertNotIn("noji_yearly.csv", actual_line)
        self.assertIn("문서에만 기재된 미보유 파일:", answer)

    def test_explicit_fruit_scope_does_not_include_special_crops(self):
        answer = metadata_answer("감귤 생산량 데이터는 몇 년까지 있어?")
        self.assertIn("2015~2020", answer)
        self.assertNotIn("jeju_special_crops.csv", answer)
        self.assertNotIn("특용작물", answer)

    def test_explicit_crop_scope_does_not_include_fruit(self):
        answer = metadata_answer("특용작물 생산량 데이터 기간 알려줘")
        self.assertIn("2010~2023", answer)
        self.assertNotIn("fruit_production.csv", answer)

    def test_unreadable_file_is_not_inspected_or_missing(self):
        records = [{"path": "good.csv", "available": True, "status": "파일 확인"},
                   {"path": "bad.csv", "available": True, "status": "검사 실패"},
                   {"path": "absent.csv", "available": False, "status": "파일 없음"}]
        lines = source_lines(records)
        self.assertEqual(lines[0], "실제 확인한 파일: good.csv")
        self.assertIn("문서에만 기재된 미보유 파일: absent.csv", lines)
        self.assertIn("존재하지만 검사에 실패한 파일: bad.csv", lines)

    def test_area_definition_with_absent_files_does_not_fake_evidence(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder, \
             patch("citrus_freellm.tools.ROOT", Path(folder)):
            answer = metadata_answer("생산면적과 수확면적은 같은 거야?")
        self.assertIn("실제 확인한 파일: 없음", answer)
        self.assertIn("문서에만 기재된 미보유 파일:", answer)

    def test_price_availability_message_changes_when_a_file_exists(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder, \
             patch("citrus_freellm.tools.ROOT", Path(folder)):
            path = Path(folder) / "data/processed/citrus_price_daily.csv"
            path.parent.mkdir(parents=True)
            path.write_text("일자,가격\n2026-01-01,1000\n", encoding="utf-8")
            answer = metadata_answer("가격 데이터 있어?")
        self.assertNotIn("가격 관련 자료는 현재 로컬에 없습니다", answer)
        self.assertIn("실제 확인한 파일: data/processed/citrus_price_daily.csv", answer)
