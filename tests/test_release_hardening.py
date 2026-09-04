from __future__ import annotations

import copy
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

import test_acceptance as acceptance
from research_frontier_agent.pipeline import run_pipeline
from research_frontier_agent.screening.llm_judge import ResearchJudge, REQUIRED_FIELDS


FakeCrossrefProvider = acceptance.FakeCrossrefProvider
FakeJudge = acceptance.FakeJudge
SAMPLE_PAPERS = acceptance.SAMPLE_PAPERS


class HardeningTests(unittest.TestCase):
    setUp = acceptance.AcceptanceTests.setUp
    tearDown = acceptance.AcceptanceTests.tearDown
    config = acceptance.AcceptanceTests.config
    def test_strict_judge_rejects_incomplete_and_wrong_types(self):
        invalid = [{}, {"priority": "Ignore"}]
        for key, value in (("relevance_score", True), ("relevance_score", 101),
                           ("method_summary", []), ("main_contributions", [3]), ("extra", "value")):
            invalid.append({**REQUIRED_FIELDS, key: value})
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                ResearchJudge.parse_response(json.dumps(item))

    def test_invalid_json_retries_and_failed_raw_is_persisted(self):
        config = self.config()
        config["llm_judge_enabled"] = True
        judge = ResearchJudge(model="test", api_base="https://example.test/v1", api_key="test", retries=2)
        response = {"choices": [{"message": {"content": "{" + "x" * 900}}]}
        with patch("research_frontier_agent.screening.llm_judge.request_json", return_value=response) as request:
            result = run_pipeline(config, providers=[FakeCrossrefProvider([SAMPLE_PAPERS[0]])], judge=judge)
        self.assertEqual(2, request.call_count)
        self.assertEqual("failed-fallback", result["all_candidates"][0]["judge_checkpoint"])
        with closing(sqlite3.connect(self.root / "frontier.db")) as db:
            status, raw = db.execute("SELECT status,raw_response FROM judgments").fetchone()
        self.assertEqual("failed", status)
        self.assertEqual([response["choices"][0]["message"]["content"]] * 2, json.loads(raw))
        valid = json.dumps(REQUIRED_FIELDS)
        with patch("research_frontier_agent.screening.llm_judge.request_json", return_value={"choices": [{"message": {"content": valid}}]}):
            resumed = run_pipeline(config, providers=[FakeCrossrefProvider([SAMPLE_PAPERS[0]])], judge=judge)
        self.assertEqual("completed", resumed["all_candidates"][0]["judge_checkpoint"])

    def test_changed_abstract_and_settings_invalidate_checkpoint(self):
        config = self.config()
        config["llm_judge_enabled"] = True
        judge = FakeJudge()
        paper = copy.deepcopy(SAMPLE_PAPERS[0])
        provider = FakeCrossrefProvider([paper])
        run_pipeline(config, providers=[provider], judge=judge)
        run_pipeline(config, providers=[provider], judge=judge)
        self.assertEqual(1, judge.calls)
        paper["abstract"] += " New evidence from an enriched abstract."
        run_pipeline(config, providers=[provider], judge=judge)
        self.assertEqual(2, judge.calls)
        config["temperature"] = 0.7
        run_pipeline(config, providers=[provider], judge=judge)
        self.assertEqual(3, judge.calls)
