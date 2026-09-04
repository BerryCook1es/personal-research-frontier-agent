from __future__ import annotations

from typing import Any

from ..profile import ResearchProfile


class KeywordRanker:
    """Stage 1 high-recall keyword screening with auditable hit evidence."""

    def __init__(self, profile: ResearchProfile):
        self.profile = profile

    @staticmethod
    def _hits(text: str, keywords: list[str]) -> list[str]:
        haystack = text.casefold()
        return [keyword for keyword in keywords if keyword.casefold() in haystack]

    def score(self, paper: dict[str, Any]) -> dict[str, Any]:
        text = f"{paper.get('title', '')} {paper.get('abstract', '')} {' '.join(paper.get('all_topics', []))}"
        core_hits = self._hits(text, self.profile.core_keywords)
        proxy_hits = self._hits(text, self.profile.proxy_keywords)
        eco_hits = self._hits(text, self.profile.eco_keywords)
        # Deliberately lenient: keywords are recall signals, not final decisions.
        if core_hits:
            tier = "core"
        elif proxy_hits:
            tier = "proxy"
        elif eco_hits:
            tier = "eco"
        else:
            tier = "other"
        paper.update({
            "keyword_tier": tier,
            "tier": tier,  # backward-compatible display field
            "core_hits": core_hits,
            "proxy_hits": proxy_hits,
            "eco_hits": eco_hits,
            "matched_keywords": list(dict.fromkeys(core_hits + proxy_hits + eco_hits)),
        })
        return paper

    def rank(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.score(dict(paper)) for paper in papers]
