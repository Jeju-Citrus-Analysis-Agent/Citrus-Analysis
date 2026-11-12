import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from citrus_freellm.agent import Agent
from citrus_freellm.repository import repository_root
from citrus_freellm.insights import load_knowledge


class RepositoryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("git"), "Git 설치 시 체크아웃 검사 가능")
    def test_evidence_hashes_survive_windows_checkout(self):
        folder = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=folder / "tests") as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            shutil.copy2(folder / ".gitattributes", root / ".gitattributes")
            shutil.copytree(folder / "knowledge", root / "knowledge")
            subprocess.run(["git", "-C", str(root), "-c", "core.autocrlf=true", "add", "."], check=True, capture_output=True)
            checkout = root / "checkout"
            checkout.mkdir()
            subprocess.run(["git", "-C", str(root), "-c", "core.autocrlf=true", "checkout-index", "--all", "--prefix=" + checkout.as_posix() + "/"], check=True, capture_output=True)
            with patch("citrus_freellm.insights.FOLDER", checkout / "knowledge"):
                cards, _ = load_knowledge()
            self.assertEqual(len(cards), 5)

    @patch.dict(os.environ, {}, clear=True)
    def test_sibling_and_repository_internal_layout(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            package = root / "citrus_freellm"
            rules = root / "Citrus-Analysis/src/jeju_citrus/data/clean_quality.py"
            rules.parent.mkdir(parents=True)
            rules.touch()
            self.assertEqual(repository_root(package), root / "Citrus-Analysis")
            inside = root / "src/jeju_citrus/data/clean_quality.py"
            inside.parent.mkdir(parents=True)
            inside.touch()
            self.assertEqual(repository_root(package), root)

    def test_explicit_repository_path_wins(self):
        with patch.dict(os.environ, {"CITRUS_REPO_PATH": str(Path(__file__).parent)}):
            self.assertEqual(repository_root(), Path(__file__).parent.resolve())

    def test_missing_cleaning_dependency_has_actionable_answer(self):
        agent = Agent(Mock())
        with patch("citrus_freellm.analysis.categories", side_effect=ImportError):
            self.assertIn("CITRUS_REPO_PATH", agent.ask("2019년 천혜향 생산량"))
        self.assertEqual(agent.results, [])

    @unittest.skipUnless(shutil.which("git"), "Git 설치 시 제외 설정 검사 가능")
    def test_git_ignore_secrets_runtime_and_generated_reports(self):
        folder = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=folder / "tests") as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / ".gitignore").write_bytes((folder / ".gitignore").read_bytes())
            for path, ignored in ((".env", True), (".env.backup", True),
                                  ("local-credentials.json", True), ("runtime/data.db", True),
                                  ("reports/exported/private.json", True), ("server.log", True),
                                  (".env.example", False), ("web.py", False), ("knowledge/cards.json", False)):
                result = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", path])
                self.assertEqual(result.returncode == 0, ignored, path)
