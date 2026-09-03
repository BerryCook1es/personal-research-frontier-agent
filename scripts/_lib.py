"""Compatibility exports for the original per-step scripts.

New code should import from :mod:`research_frontier_agent` directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_frontier_agent.profile import ResearchProfile, load_profile
from research_frontier_agent.providers.crossref import CrossrefProvider
from research_frontier_agent.render.common import POOL_LABELS
from research_frontier_agent.screening.keyword_ranker import KeywordRanker
from research_frontier_agent.translation import Translator
from research_frontier_agent.translation.glossary import ACADEMIC_GLOSSARY, protect_terms, restore_terms
from research_frontier_agent.utils import request_json, strip_markup

TIER_LABELS = {"core": "核心 Core", "proxy": "邻近 Proxy", "eco": "背景 Eco", "other": "其他 Other"}
UI = {"title": "前沿论文周报 · Frontier Weekly Report"}


def fetch_journal_papers(journal, issn, from_date, to_date, pool, max_results=100):
    provider = CrossrefProvider(
        [{"journal": journal, "issn": issn, "pool": pool}], max_per_venue=max_results, sleep=0
    )
    papers, _ = provider.discover(from_date, to_date)
    return papers


def load_profile_keywords(profile_path):
    profile = load_profile(Path(profile_path))
    return profile.core_keywords, profile.proxy_keywords, profile.eco_keywords


def classify_paper(title, abstract, core_kw, proxy_kw, eco_kw, pool=""):
    profile = ResearchProfile("compat", Path("."), "", core_kw, proxy_kw, eco_kw)
    return KeywordRanker(profile).score({"title": title, "abstract": abstract, "pool": pool})["keyword_tier"]


def screen_papers(papers, core_kw, proxy_kw, eco_kw):
    profile = ResearchProfile("compat", Path("."), "", core_kw, proxy_kw, eco_kw)
    return KeywordRanker(profile).rank(papers)


def translate_papers(papers, workers=4):
    return Translator(backend="auto").translate_papers(papers, workers=workers)


def translate_text(text, max_retries=2):
    return Translator(backend="auto", retries=max_retries).translate(text)

