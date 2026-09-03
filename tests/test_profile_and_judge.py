from __future__ import annotations

import unittest
from pathlib import Path

from research_frontier_agent.profile import load_profile, load_project
from research_frontier_agent.screening.keyword_ranker import KeywordRanker
from research_frontier_agent.screening.llm_judge import ResearchJudge
from research_frontier_agent.utils import ROOT, stable_paper_id


class UnitTests(unittest.TestCase):
    def test_profiles_are_independent_and_have_capacity(self):
        names = set()
        for filename in (
            "profile-scholarly-kg-llm.md", "profile-scientometrics-evaluation.md", "profile-human-ai-algorithm.md"
        ):
            profile = load_profile(ROOT / "references" / filename)
            names.add(profile.name)
            self.assertTrue(profile.description)
            self.assertGreater(len(profile.core_keywords), 10)
            self.assertEqual(5, profile.max_a)
        self.assertEqual(3, len(names))

    def test_keyword_evidence_is_preserved(self):
        profile = load_profile(ROOT / "references" / "profile-scholarly-kg-llm.md")
        paper = KeywordRanker(profile).score({
            "title": "Scientific knowledge graph construction", "abstract": "Relation extraction from scientific literature"
        })
        self.assertEqual("core", paper["keyword_tier"])
        self.assertIn("scientific knowledge graph", paper["core_hits"])
        self.assertIn("relation extraction", paper["proxy_hits"])
        self.assertEqual(set(paper["matched_keywords"]), set(paper["core_hits"] + paper["proxy_hits"]))

    def test_llm_json_validation(self):
        parsed = ResearchJudge.parse_response('```json\n{"relevance_score":94,"priority":"A","recommended_action":"deep-read"}\n```')
        self.assertEqual(94, parsed["relevance_score"])
        self.assertEqual([], parsed["main_contributions"])
        with self.assertRaises(ValueError):
            ResearchJudge.parse_response('{"relevance_score": 101, "priority": "urgent"}')

    def test_stable_title_hash_without_doi(self):
        a = stable_paper_id({"title": "A  Useful Paper"})
        b = stable_paper_id({"title": "a useful paper"})
        self.assertEqual(a, b)

    def test_project_template_parses(self):
        project = load_project(ROOT / "references" / "projects" / "project-template.md")
        self.assertEqual("Project Name", project.name)
        self.assertTrue(project.research_question)
        self.assertTrue(project.keywords)


if __name__ == "__main__":
    unittest.main()
