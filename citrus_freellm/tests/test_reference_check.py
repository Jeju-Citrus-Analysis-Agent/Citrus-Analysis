"""Mutate only copies/temporary fixtures; original project data stay read-only."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.guardrails import render, validate_evidence
from citrus_freellm.tools import ROOT, production
from test_guardrails import REQUEST, QUESTION, call


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.data = production(**REQUEST)

    def reject(self, data):
        with self.assertRaises(ValueError):
            validate_evidence(data, REQUEST)

    def test_positive_but_fabricated_value(self):
        for metric in ("생산량_톤", "생산면적_ha"):
            data = copy.deepcopy(self.data)
            data["rows"][0][metric] = 99999
            self.reject(data)

    def test_values_swapped_between_years(self):
        data = copy.deepcopy(self.data)
        a, b = data["rows"]
        a["생산량_톤"], b["생산량_톤"] = b["생산량_톤"], a["생산량_톤"]
        self.reject(data)

    def test_deleted_row_and_consistent_missing_claim(self):
        data = copy.deepcopy(self.data)
        data["rows"] = data["rows"][1:]
        data["missing_years"] = [2019]
        self.reject(data)

    def test_all_rows_falsely_missing(self):
        data = copy.deepcopy(self.data)
        data.update(rows=[], missing_years=[2019, 2020])
        self.reject(data)

    def test_fake_row_in_year_absent_from_source(self):
        request = dict(REQUEST, end_year=2021)
        data = production(**request)
        fake = dict(data["rows"][-1], 연도=2021)
        data["rows"].append(fake)
        data["missing_years"] = []
        with self.assertRaises(ValueError):
            validate_evidence(data, request)

    def test_zero_or_null_substitution_is_not_missing_data(self):
        for value in (0, None):
            data = copy.deepcopy(self.data)
            data["rows"][0]["생산량_톤"] = value
            self.reject(data)

    def test_hash_mismatch(self):
        data = copy.deepcopy(self.data)
        data["source_sha256"] = "0" * 64
        self.reject(data)

    def test_raw_changed_after_lookup(self):
        original = (ROOT / self.data["source"]).read_bytes()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder)
            path = root / self.data["source"]
            path.parent.mkdir(parents=True)
            path.write_bytes(original.replace(b"18044", b"99999"))
            with patch("citrus_freellm.tools.ROOT", root):
                self.reject(self.data)

    def test_unreadable_source_fails_closed_in_agent(self):
        client = Mock()
        client.complete.return_value = call(REQUEST)
        with patch("citrus_freellm.agent.execute", return_value=self.data), \
             patch("citrus_freellm.reference_check.verify_reference", side_effect=OSError("unavailable")):
            self.assertIn("보류", Agent(client).ask(QUESTION))

    def test_corrupted_lookup_fails_closed_in_agent(self):
        client = Mock()
        client.complete.return_value = call(REQUEST)
        data = copy.deepcopy(self.data)
        data["rows"][0]["생산량_톤"] = 99999
        with patch("citrus_freellm.agent.execute", return_value=data):
            answer = Agent(client).ask(QUESTION)
        self.assertIn("원자료 대조", answer)
        self.assertIn("보류", answer)
        self.assertNotIn("99,999", answer)

    def test_all_varieties_agree_with_independent_reader(self):
        from jeju_citrus.data.clean_quality import FRUIT_CATEGORY_MAP
        for variety in FRUIT_CATEGORY_MAP:
            request = dict(REQUEST, variety=variety, start_year=2015)
            with self.subTest(variety=variety):
                data = production(**request)
                validate_evidence(data, request)

    def test_duplicate_source_and_unit_change(self):
        raw = (ROOT / self.data["source"]).read_text(encoding="utf-8-sig")
        line = next(line for line in raw.splitlines() if line.startswith("2019,") and "천혜향" in line)
        for changed in (raw + "\n" + line + "\n", raw.replace("생산량(톤)", "생산량(kg)")):
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
                root = Path(folder)
                path = root / self.data["source"]
                path.parent.mkdir(parents=True)
                path.write_text(changed, encoding="utf-8")
                data = copy.deepcopy(self.data)
                data["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                with patch("citrus_freellm.tools.ROOT", root):
                    self.reject(data)

    def test_tool_change_summary_cannot_override_verified_values(self):
        data = copy.deepcopy(self.data)
        data["change"]["생산량_톤"] = {"difference": 99999, "percent": 99999}
        answer = render(data, REQUEST, QUESTION)
        self.assertIn("+570.00", answer)
        self.assertIn("+3.16%", answer)
        self.assertNotIn("99,999", answer)
