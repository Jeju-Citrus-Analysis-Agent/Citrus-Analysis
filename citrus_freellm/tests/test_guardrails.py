import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.guardrails import QUALITY_NOTE, render, request_for
from citrus_freellm.tools import production

REQUEST = {"variety": "천혜향", "start_year": 2019, "end_year": 2020}
QUESTION = "2019년과 2020년 천혜향 생산량 비교"


def call(request):
    return {"role": "assistant", "content": "면적 자료가 누락되어 생산량은 999999톤이다.",
            "tool_calls": [{"id": "p1", "type": "function", "function": {
                "name": "production", "arguments": json.dumps(request)}}]}


class GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.evidence = production(**REQUEST)

    def test_known_values_and_only_used_source(self):
        answer = render(self.evidence, REQUEST, QUESTION)
        for value in ("18,044", "18,614", "+570.00", "+3.16%"):
            self.assertIn(value, answer)
        self.assertNotIn("weather", answer)
        self.assertNotIn("ha", answer)

    def test_model_interpretation_never_printed(self):
        client = Mock()
        client.complete.return_value = call(REQUEST)
        answer = Agent(client).ask(QUESTION)
        self.assertNotIn("999999", answer)
        self.assertNotIn("누락", answer)

    def test_free_text_without_lookup_uses_verified_local_lookup(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "생산량은 999999톤"}
        answer = Agent(client).ask(QUESTION)
        self.assertNotIn("999999", answer)
        self.assertIn("18,044", answer)
        self.assertIn("18,614", answer)
        self.assertIn("+3.16%", answer)

    def test_wrong_request_is_not_executed(self):
        client = Mock()
        client.complete.return_value = call(dict(REQUEST, variety="레드향"))
        with patch("citrus_freellm.agent.execute") as execute:
            self.assertIn("보류", Agent(client).ask(QUESTION))
            execute.assert_not_called()

    def test_corrupt_evidence_is_rejected(self):
        for label in ("duplicate", "year", "variety", "unit", "nan", "negative", "missing", "source", "hierarchy"):
            data = copy.deepcopy(self.evidence)
            if label == "duplicate":
                data["rows"].append(data["rows"][0])
            elif label == "year":
                data["rows"][0]["연도"] = 2025
            elif label == "variety":
                data["rows"][0]["품종"] = "레드향"
            elif label == "unit":
                data["units"]["생산량_톤"] = "kg"
            elif label in ("nan", "negative"):
                data["rows"][0]["생산량_톤"] = float("nan") if label == "nan" else -1
            elif label == "missing":
                data["missing_years"] = [2019]
            elif label == "source":
                data["source"] = "fake.csv"
            else:
                data["rows"][0]["집계수준"] = "다른 집계"
            with self.subTest(label=label), self.assertRaises(ValueError):
                render(data, REQUEST, QUESTION)

    def test_missing_years_not_invented(self):
        request = dict(REQUEST, end_year=2021)
        answer = render(production(**request), request, "2019~2021 천혜향 생산량")
        self.assertIn("| 2021 | 자료 없음 |", answer)
        self.assertNotIn("변화율:", answer)

    def test_area_discontinuity(self):
        request = dict(REQUEST, start_year=2016, end_year=2017)
        data = production(**request)
        self.assertNotIn("생산면적_ha", data["change"])
        answer = render(data, request, "2016~2017 천혜향 면적 비교")
        self.assertIn(QUALITY_NOTE, answer)
        self.assertNotIn("면적 자료가 누락", answer)
        self.assertNotIn("변화율:", answer)

    def test_zero_and_null_baselines(self):
        for before in (0, None):
            # A real zero/null source value is allowed; changing only evidence is not.
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
                root = Path(folder)
                path = root / "data/raw/public/fruit_production.csv"
                path.parent.mkdir(parents=True)
                path.write_text("기준연도,품종대분류,품종소분류,생산면적(ha),생산량(톤)\n"
                                f"2019,만감류,천혜향,893,{'' if before is None else before}\n"
                                "2020,만감류,천혜향,894,18614\n", encoding="utf-8")
                with patch("citrus_freellm.tools.ROOT", root):
                    data = production(**REQUEST)
                    answer = render(data, REQUEST, QUESTION)
            self.assertNotIn("inf", answer)
            if before == 0:
                self.assertIn("계산하지 않음", answer)
            else:
                self.assertNotIn("변화율:", answer)

    def test_ambiguity_and_unsupported(self):
        for question in ("감귤 생산량", "2019년 천혜향과 레드향 비교", "천혜향 생산량 비교"):
            self.assertIsNotNone(request_for(question)[1])
        for question in ("2020년 천혜향 생산량 예측", "2019년 천혜향 생산량이 왜 줄었어?", "2019년 천혜향 생산량 합계"):
            client = Mock()
            self.assertIn("지원하지 않", Agent(client).ask(question))
            client.complete.assert_not_called()

    def test_followup_and_reset(self):
        request, blocked = request_for("그러면 2018년은?", REQUEST)
        self.assertIsNone(blocked)
        self.assertEqual({k: request[k] for k in REQUEST}, dict(REQUEST, start_year=2018, end_year=2018))
        agent = Agent(Mock())
        agent.previous_request = REQUEST
        agent.reset()
        self.assertIsNone(agent.previous_request)
        self.assertIn("명시", agent.ask("그러면 2018년은?"))
