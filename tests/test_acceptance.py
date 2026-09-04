from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from research_frontier_agent.config import load_config
from research_frontier_agent.pipeline import run_pipeline
from research_frontier_agent.providers.base import PaperProvider
from research_frontier_agent.render.report import render_report
from research_frontier_agent.screening.embedding_ranker import EmbeddingRanker
from research_frontier_agent.screening.venue_filter import is_excluded_journal
from research_frontier_agent.storage import FrontierDatabase
from research_frontier_agent.translation import Translator
from research_frontier_agent.utils import normalize_openai_api_base, openai_api_endpoint


SAMPLE_PAPERS = [
    {
        "title": "Document-level scientific knowledge graph construction with relation extraction",
        "abstract": "We study scholarly document processing and scientific claim extraction.",
        "publication_date": "2026-09-02",
        "venue": "Knowledge-Based Systems",
        "journal": "Knowledge-Based Systems",
        "authors": "Ada Researcher",
        "doi_raw": "10.1000/kg.1",
        "doi_url": "https://doi.org/10.1000/kg.1",
        "pool": "scientific-knowledge-graph",
        "source": "crossref",
    },
    {
        "title": "Responsible research evaluation using citation analysis",
        "abstract": "A scientometrics study of research assessment and scientific impact.",
        "publication_date": "2026-09-01",
        "venue": "Scientometrics",
        "journal": "Scientometrics",
        "authors": "Bo Scholar",
        "doi_raw": "10.1000/science.2",
        "doi_url": "https://doi.org/10.1000/science.2",
        "pool": "scientometrics-evaluation",
        "source": "crossref",
    },
    {
        "title": "Calibrating trust in human-AI decision making",
        "abstract": "We examine AI reliance, algorithm aversion, and human-AI collaboration.",
        "publication_date": "2026-08-31",
        "venue": "Computers in Human Behavior",
        "journal": "Computers in Human Behavior",
        "authors": "Chen Analyst",
        "doi_raw": "10.1000/hai.3",
        "doi_url": "https://doi.org/10.1000/hai.3",
        "pool": "human-ai-interaction",
        "source": "crossref",
    },
]


class FakeCrossrefProvider(PaperProvider):
    name = "crossref"

    def __init__(self, papers=None):
        self.papers = papers or SAMPLE_PAPERS

    def discover(self, from_date, to_date):
        return copy.deepcopy(self.papers), []


class FakeJudge:
    model = "fake-model"

    def __init__(self, interrupt_after=None):
        self.calls = 0
        self.interrupt_after = interrupt_after

    def judge(self, profile, paper, projects):
        self.calls += 1
        if self.interrupt_after and self.calls == self.interrupt_after:
            raise KeyboardInterrupt("simulated interruption")
        priority = "A" if paper.get("keyword_tier") == "core" else "B"
        parsed = {
            "relevance_score": 91,
            "research_track": profile.name,
            "priority": priority,
            "matched_topics": paper.get("matched_keywords", []),
            "research_question": "What can be learned from the supplied abstract?",
            "method_summary": "Method stated in the supplied abstract.",
            "main_contributions": ["Structured research judgment"],
            "why_relevant": "Matches the active Research Profile.",
            "methodological_value": "Potentially transferable.",
            "potential_use": "Related Work",
            "related_project": projects[0].name if projects else "",
            "recommended_action": "deep-read" if priority == "A" else "skim",
        }
        return json.dumps(parsed), parsed


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def config(self, profile="references/profile-scholarly-kg-llm.md"):
        return load_config(overrides={
            "profile": profile,
            "to_date": "2026-09-03",
            "from_date": "2026-08-27",
            "database": str(self.root / "frontier.db"),
            "output_root": str(self.root / "outputs"),
            "translation_enabled": False,
            "embedding_enabled": False,
            "llm_judge_enabled": False,
            "enrich": False,
            "output_modes": ["html"],
        })

    def test_1_base_keyword_translation_html(self):
        config = self.config()
        config["translation_enabled"] = True
        translator = Translator(translate_fn=lambda text: "中译:" + text)
        result = run_pipeline(config, providers=[FakeCrossrefProvider()], translator=translator)
        html_path = Path(result["paths"]["html"])
        self.assertTrue(html_path.exists())
        self.assertIn("前沿论文追踪周报·Frontier Weekly", html_path.read_text(encoding="utf-8"))
        self.assertTrue(all(p.get("core_hits") is not None for p in result["all_candidates"]))
        self.assertTrue(any(p.get("title_cn", "").startswith("中译:") for p in result["all_candidates"]))

    def test_journal_exclusion_matches_aliases_without_excluding_other_plos_journals(self):
        for paper in ({"venue": "PLoS ONE"}, {"journal": "PLOS  One"},
                      {"journal_source": "plos-one"},
                      {"doi_url": "https://doi.org/10.1371/journal.pone.0357186"}):
            with self.subTest(paper=paper):
                self.assertTrue(is_excluded_journal(paper, ["PLOS ONE"]))
        self.assertFalse(is_excluded_journal({"venue": "PLOS Biology", "doi": "10.1371/journal.pbio.123"}, ["PLOS ONE"]))
        self.assertFalse(is_excluded_journal({"title": "A study of PLOS ONE", "venue": "Scientometrics"}, ["PLOS ONE"]))
        self.assertFalse(is_excluded_journal({"venue": "PLOS ONE"}, []))

    def test_journal_exclusion_applies_before_analysis_and_to_resumed_scans(self):
        blocked = {**copy.deepcopy(SAMPLE_PAPERS[0]), "venue": "PLoS ONE",
                   "journal": "PLoS ONE", "doi_raw": "10.1371/journal.pone.123", "source": "semantic_scholar"}
        papers = [copy.deepcopy(SAMPLE_PAPERS[0]), blocked]
        for mode in ("live", "skip_scan", "skip_screen"):
            with self.subTest(mode=mode):
                config = self.config()
                if mode != "live":
                    source = self.root / (mode + ".json")
                    source.write_text(json.dumps({"new": papers, "already_seen": [], "papers": papers}), encoding="utf-8")
                    config[mode] = True
                    config["scan_file" if mode == "skip_scan" else "screened_file"] = str(source)
                result = run_pipeline(config, providers=[FakeCrossrefProvider(papers)])
                self.assertEqual(1, result["excluded_count"])
                self.assertEqual(1, result["stats"]["scanned"])
                self.assertFalse(any(is_excluded_journal(p, ["PLOS ONE"]) for p in result["all_candidates"]))
                self.assertNotIn('data-venue="PLoS ONE"', Path(result["paths"]["html"]).read_text(encoding="utf-8"))
        with sqlite3.connect(self.root / "frontier.db") as conn:
            self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM papers WHERE venue='PLoS ONE'").fetchone()[0])

    def test_2_three_profiles_do_not_overwrite(self):
        profiles = [
            "references/profile-scholarly-kg-llm.md",
            "references/profile-scientometrics-evaluation.md",
            "references/profile-human-ai-algorithm.md",
        ]
        paths = []
        for profile in profiles:
            config = self.config(profile)
            config["output_modes"] = ["html", "excel", "app", "notes", "codex"]
            result = run_pipeline(config, providers=[FakeCrossrefProvider()])
            generated = [Path(result["paths"][mode]) for mode in ("html", "excel", "app", "notes", "codex")]
            paths.extend(generated)
            self.assertTrue(all(path.exists() for path in generated))
        self.assertEqual(15, len(set(paths)))

    def test_3_incremental_run(self):
        first = run_pipeline(self.config(), providers=[FakeCrossrefProvider()])
        second = run_pipeline(self.config(), providers=[FakeCrossrefProvider()])
        self.assertEqual(3, first["new_count"])
        self.assertEqual(0, second["new_count"])
        self.assertEqual(3, second["already_seen_count"])

    def test_4_checkpoint_resume_skips_completed_judgment(self):
        config = self.config()
        config.update({"llm_judge_enabled": True, "llm_model": "fake-model"})
        interrupted = FakeJudge(interrupt_after=2)
        with self.assertRaises(KeyboardInterrupt):
            run_pipeline(config, providers=[FakeCrossrefProvider()], judge=interrupted)
        resumed = FakeJudge()
        result = run_pipeline(config, providers=[FakeCrossrefProvider()], judge=resumed)
        self.assertGreaterEqual(len(result["all_candidates"]), 2)
        self.assertEqual(len(result["all_candidates"]) - 1, resumed.calls)
        self.assertTrue(any(p.get("judge_checkpoint") == "reused" for p in result["all_candidates"]))

    def test_5_no_api_falls_back_without_aborting(self):
        config = self.config()
        config.update({"llm_judge_enabled": True, "llm_model": "", "api_base": "", "api_key": ""})
        result = run_pipeline(config, providers=[FakeCrossrefProvider()])
        self.assertTrue(Path(result["paths"]["html"]).exists())
        self.assertTrue(any(error.get("stage") == "llm_judge" for error in result["errors"]))
        self.assertTrue(all(p.get("judge_checkpoint") == "disabled" for p in result["all_candidates"]))

    def test_6_database_doi_dedupe_and_status(self):
        duplicate = copy.deepcopy(SAMPLE_PAPERS[0])
        duplicate["title"] = "Duplicate metadata title"
        config = self.config()
        result = run_pipeline(config, providers=[FakeCrossrefProvider(SAMPLE_PAPERS + [duplicate])])
        self.assertEqual(3, result["new_count"])
        with sqlite3.connect(self.root / "frontier.db") as connection:
            rows = connection.execute("SELECT doi,first_seen,last_seen,reading_status FROM papers").fetchall()
        self.assertEqual(3, len(rows))
        self.assertTrue(all(row[1] and row[2] and row[3] == "new" for row in rows))

    def test_cross_source_duplicate_merges_richer_metadata(self):
        crossref = copy.deepcopy(SAMPLE_PAPERS[0])
        crossref["abstract"] = ""
        semantic_scholar = copy.deepcopy(SAMPLE_PAPERS[0])
        semantic_scholar.update({
            "source": "semantic_scholar",
            "abstract": "A richer abstract supplied by the second provider for scientific knowledge graph construction.",
            "abstract_source": "semantic_scholar",
            "s2_paper_id": "s2-test",
        })
        result = run_pipeline(
            self.config(),
            providers=[FakeCrossrefProvider([crossref]), FakeCrossrefProvider([semantic_scholar])],
        )
        self.assertEqual(1, result["new_count"])
        self.assertEqual("crossref;semantic_scholar", result["all_candidates"][0]["source"])
        self.assertEqual("semantic_scholar", result["all_candidates"][0]["abstract_source"])
        self.assertEqual("s2-test", result["all_candidates"][0]["s2_paper_id"])

    def test_embedding_ranker_normalizes_and_ranks(self):
        ranker = EmbeddingRanker(
            backend="test", model="test",
            encoder=lambda texts: [[1.0, 0.0], [1.0, 0.0], [-1.0, 0.0]],
        )
        papers = [{"title": "near", "abstract": ""}, {"title": "far", "abstract": ""}]
        ranker.rank(papers, "profile")
        self.assertEqual(1.0, papers[0]["semantic_score"])
        self.assertEqual(0.0, papers[1]["semantic_score"])
        self.assertEqual(1, papers[0]["semantic_rank"])

    def test_embedding_ranker_does_not_treat_orthogonal_vectors_as_half_relevant(self):
        self.assertEqual(0.0, EmbeddingRanker._cosine([1.0, 0.0], [0.0, 1.0]))

    def test_openai_compatible_endpoint_normalization(self):
        root = "https://api.example.test/v1"
        self.assertEqual(root, normalize_openai_api_base(root + "/chat/completions"))
        self.assertEqual(root, normalize_openai_api_base(root + "/embeddings"))
        self.assertEqual(root, normalize_openai_api_base(f"[{root}/chat/completions]({root}/chat/completions)"))
        self.assertEqual(root + "/chat/completions", openai_api_endpoint(root, "chat/completions"))
        self.assertEqual(root + "/embeddings", openai_api_endpoint(root + "/chat/completions", "embeddings"))

    def test_html_report_matches_reference_style_and_keeps_all_candidates(self):
        output = self.root / "report.html"
        background = {
            **copy.deepcopy(SAMPLE_PAPERS[0]),
            "priority": "D",
            "relevance_score": 35,
            "semantic_score": 0.46,
            "keyword_tier": "other",
            "title_cn": "科学论文知识图谱构建",
            "abstract_cn": "中文摘要。",
            "research_track": "scholarly communication",
            "research_question": "How are scholarly structures studied?",
            "method_summary": "Document analysis.",
            "main_contributions": ["Background evidence"],
            "why_relevant": "Useful background context.",
            "methodological_value": "Limited direct transfer.",
            "potential_use": "Discussion",
            "recommended_action": "save",
            "matched_keywords": [],
        }
        render_report({
            "profile": {"name": "scholarly-kg-llm"},
            "coverage": {"from": "2026-09-02", "to": "2026-09-03"},
            "stats": {"scanned": 1, "candidates": 1, "A": 0, "B": 0, "C": 0},
            "judged_stats": {"scanned": 1, "candidates": 1, "A": 0, "B": 0, "C": 0, "D": 1, "Ignore": 0},
            "report_papers": [],
            "all_candidates": [background],
        }, output)
        rendered = output.read_text(encoding="utf-8")
        self.assertIn("前沿论文追踪周报·Frontier Weekly", rendered)
        self.assertIn("覆盖周期：2026-09-02 → 2026-09-03", rendered)
        self.assertIn("主题：学术文本挖掘 / 科学知识图谱 / LLM 与 Agent 方法", rendered)
        self.assertIn("app-header", rendered)
        self.assertIn("🍪</span>BerryCook1es Research Radar · September 2026 Issue 1", rendered)
        self.assertIn("theme-scholarly-kg-llm", rendered)
        self.assertIn("class=\"star-field\"", rendered)
        self.assertIn("<span>✦</span>", rendered)
        self.assertNotIn("linear-gradient(32deg", rendered)
        self.assertIn("Curated for <strong>BerryCook1es</strong> · <span>Personal Research Frontier Agent</span>", rendered)
        self.assertIn("stat-chip", rendered)
        self.assertIn("class=\"pill active\"", rendered)
        self.assertIn("Number.isNaN(pub.getTime())", rendered)
        self.assertIn("T00:00:00", rendered)
        self.assertNotIn("本周扫描", rendered)
        self.assertNotIn("Top 5", rendered)
        self.assertIn("D · 背景", rendered)
        self.assertIn("可迁移价值", rendered)
        self.assertNotIn("Methodological Value", rendered)
        self.assertLess(rendered.index("中文摘要。"), rendered.index("研究问题"))
        self.assertNotIn("中英文摘要", rendered)
        self.assertEqual(1, rendered.count('<article class="paper-card'))

    def test_feedback_import_updates_sqlite(self):
        result = run_pipeline(self.config(), providers=[FakeCrossrefProvider()])
        paper = result["all_candidates"][0]
        db = FrontierDatabase(self.root / "frontier.db")
        try:
            imported, errors = db.import_feedback([{
                "paper_id": paper["paper_id"], "rating": 5, "reading_status": "reading",
                "note": "Useful method", "related_project": "StructGraph",
            }])
            status = db.connection.execute("SELECT reading_status FROM papers WHERE id=?", (paper["paper_id"],)).fetchone()[0]
        finally:
            db.close()
        self.assertEqual(1, imported)
        self.assertEqual([], errors)
        self.assertEqual("reading", status)


if __name__ == "__main__":
    unittest.main()
