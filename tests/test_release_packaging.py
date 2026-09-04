import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_release import allowed, check_content
from scripts.check_skill import check_skill
from research_frontier_agent.utils import ROOT


class PackagingTests(unittest.TestCase):
    def test_private_paths_cannot_enter_export(self):
        for name in ("config.local.json", ".env", "state/frontier.db", "outputs/report.html",
                     "references/projects/my-private-project.md", "release/github/copy.py",
                     "scripts/__pycache__/cache.py", "scripts/../config.local.json"):
            with self.subTest(name=name):
                self.assertFalse(allowed(name))
        self.assertTrue(allowed("scripts/frontier_tracker.py"))
        self.assertTrue(allowed(".agents/skills/research-frontier-agent/SKILL.md"))
        self.assertTrue(allowed("references/projects/project-template.md"))

    def test_secret_detector_rejects_tokens_without_printing_them(self):
        secret = ("sk-" + "x" * 30).encode()
        with self.assertRaises(ValueError) as error:
            check_content("example.txt", secret, [])
        self.assertNotIn(secret.decode(), str(error.exception))
        with self.assertRaises(ValueError):
            check_content("example.txt", b"custom-private-value", [b"custom-private-value"])

    def test_example_keys_are_empty(self):
        data = (ROOT / "config.example.json").read_bytes()
        check_content("config.example.json", data, [])
        with self.assertRaises(ValueError):
            check_content("config.example.json", json.dumps({"api_key": "not-empty"}).encode(), [])

    def test_skill_links_resolve_and_incomplete_install_is_rejected(self):
        check_skill()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises((ValueError, FileNotFoundError)):
                check_skill(Path(folder))
