import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.insights import FOLDER, explain, load_knowledge, interpret_topic
from citrus_freellm.reporting import save_report


class InsightReportTests(unittest.TestCase):
    def test_five_core_questions_and_qualifications(self):
        client = Mock()
        agent = Agent(client)
        for question, phrase in (("어떤 품종이 면적당 매출이 높나?", "4.6배"),
                                 ("언제 팔면 비싼가?", "0.67~1.01배"),
                                 ("생산량이 늘면 가격은?", "인과 법칙이 아닙니다"),
                                 ("날씨는 영향이 있나?", "상관이 인과를 뜻하지"),
                                 ("2026년산 가격은?", "11월 8일")):
            answer = agent.ask(question)
            self.assertIn(phrase, answer)
            for label in ("적용 범위", "해석:", "대안:", "한계:", "출처:"):
                self.assertIn(label, answer)
        client.complete.assert_not_called()

    def test_timing_does_not_repeat_known_overstatement(self):
        answer = explain("언제 팔면 비싼가?")["text"]
        self.assertIn("대체로 낮거나 비슷", answer)
        self.assertNotIn("매년 반드시", answer)

    def test_2026_snapshot_not_other_variety_forecast(self):
        answer = explain("2026년산 천혜향 가격은?")["text"]
        self.assertIn("품종의 2026년 가격으로 확정할 근거는 없습니다", answer)
        self.assertIn("노지온주", answer)
        self.assertIn("실시간 시세가 아닙니다", answer)
        self.assertNotIn("1,580", answer)

    def test_source_integrity_failure(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            root = Path(directory)
            for relative in ("cards.json", "manifest.json"):
                (root / relative).write_bytes((FOLDER / relative).read_bytes())
            (root / "cards.json").write_text("{}", encoding="utf-8")
            with patch("citrus_freellm.insights.FOLDER", root), self.assertRaises(ValueError):
                load_knowledge()

    def test_unsafe_retrieval_ids_are_rejected(self):
        client = Mock()
        client.complete.return_value = {"tool_calls": [{"function": {"name": "select_analysis_evidence", "arguments": '{"evidence_ids":["execute_python"]}'}}]}
        self.assertEqual(interpret_topic("기온이 귤에 어떤 영향을 주니?", client), [])

    def test_semantic_retrieval_only_uses_known_evidence(self):
        client = Mock()
        client.complete.return_value = {"tool_calls": [{"function": {"name": "select_analysis_evidence", "arguments": '{"evidence_ids":["revenue_area"]}'}}]}
        answer = Agent(client).ask("감귤 농사로 돈을 벌려면 어떤 품종을 골라야 해?")
        self.assertIn("매출", answer)
        self.assertIn("순이익", answer)
        self.assertIn("확보", answer)

    def test_report_without_result_does_not_write(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            output = Path(directory) / "reports"
            with patch("citrus_freellm.reporting.OUTPUT", output):
                self.assertIn("먼저", Agent(Mock()).ask("리포트 저장"))
                self.assertFalse(output.exists())

    def test_report_export_scenario_and_insight_with_sources(self):
        agent = Agent(Mock())
        agent.ask("판매량 1000kg, 단가 4000원, 총비용 300만원, 단가 10% 하락 이익")
        agent.ask("날씨는 영향이 있나?")
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            with patch("citrus_freellm.reporting.OUTPUT", Path(directory)):
                paths = save_report(agent.results, all_results=True)
                self.assertEqual(len(paths), 3)
                payload = json.loads(Path(next(p for p in paths if p.endswith('.json'))).read_text(encoding="utf-8"))
                self.assertEqual([r["kind"] for r in payload["results"]], ["user_scenario", "analysis_explanation"])
                self.assertIn("sha256", payload["results"][1]["sources"][0])
                markdown = Path(next(p for p in paths if p.endswith('.md'))).read_text(encoding="utf-8")
                self.assertIn("600,000", markdown)
                self.assertIn("상관이 인과", markdown)

    def test_report_html_escapes_question_and_does_not_overwrite(self):
        record = {"kind": "user_scenario", "question": "<script>alert(1)</script>", "conditions": {}, "sources": [], "text": "검증된 결과"}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            with patch("citrus_freellm.reporting.OUTPUT", Path(directory)):
                first = save_report([record])
                second = save_report([record])
                self.assertNotEqual(first, second)
                body = Path(next(p for p in first if p.endswith('.html'))).read_text(encoding="utf-8")
                self.assertNotIn("<script>", body)
                self.assertIn("&lt;script&gt;", body)

    def test_failed_analysis_not_recorded_as_success(self):
        agent = Agent(Mock())
        agent.ask("2021년 만감류 생산량 순위")
        self.assertEqual(agent.results, [])

    def test_report_from_verified_lookup_has_source_hash(self):
        client = Mock()
        client.complete.return_value = {"role": "assistant", "content": "OK"}
        agent = Agent(client)
        agent.ask("2019년과 2020년 천혜향 생산량 비교")
        self.assertEqual(agent.results[-1]["kind"], "verified_lookup")
        self.assertEqual(len(agent.results[-1]["sources"][0]["sha256"]), 64)

    def test_report_from_local_calculation(self):
        agent = Agent(Mock())
        agent.ask("2019~2020년 천혜향 생산량 평균")
        self.assertEqual(agent.results[-1]["kind"], "verified_calculation")
        self.assertIn("18,329", agent.results[-1]["text"])

    def test_source_snapshot_change_is_not_ignored(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            root = Path(directory)
            for name in ("cards.json", "manifest.json"):
                (root / name).write_bytes((FOLDER / name).read_bytes())
            (root / "sources").mkdir()
            for path in (FOLDER / "sources").glob("*.md"):
                (root / "sources" / path.name).write_bytes(path.read_bytes())
            path = root / "sources/public_analysis.md"
            path.write_text("값이 변조됨", encoding="utf-8")
            with patch("citrus_freellm.insights.FOLDER", root):
                answer = Agent(Mock()).ask("날씨는 영향이 있나?")
            self.assertIn("보류", answer)
