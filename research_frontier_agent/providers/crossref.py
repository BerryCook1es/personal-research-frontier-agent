from __future__ import annotations

import html
import re
import time
import urllib.parse
from datetime import date
from typing import Any

from .base import PaperProvider
from ..utils import normalize_doi, request_json, strip_markup


NON_RESEARCH_PATTERNS = (
    r"^author correction", r"^publisher correction", r"^correction:",
    r"^retraction:", r"^erratum", r"^editorial:", r"^news & views", r"^reply to",
)


class CrossrefProvider(PaperProvider):
    name = "crossref"
    base_url = "https://api.crossref.org/works"

    def __init__(self, venues: list[dict[str, Any]], *, max_per_venue: int = 50,
                 timeout: float = 30.0, retries: int = 3, sleep: float = 0.2):
        self.venues = venues
        self.max_per_venue = max_per_venue
        self.timeout = timeout
        self.retries = retries
        self.sleep = sleep

    def discover(self, from_date: str, to_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        papers: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for index, venue in enumerate(self.venues):
            try:
                papers.extend(self._fetch_venue(venue, from_date, to_date))
            except Exception as exc:  # one venue must not abort a run
                errors.append({"source": self.name, "venue": venue.get("journal") or venue.get("venue"), "error": str(exc)})
            if index + 1 < len(self.venues):
                time.sleep(self.sleep)
        unique: dict[str, dict[str, Any]] = {}
        for paper in papers:
            key = normalize_doi(paper.get("doi_raw", "")) or re.sub(r"\W+", "", paper.get("title", "").casefold())
            unique.setdefault(key, paper)
        return list(unique.values()), errors

    def _fetch_venue(self, venue: dict[str, Any], from_date: str, to_date: str) -> list[dict[str, Any]]:
        offset = 0
        rows = min(100, self.max_per_venue)
        collected: list[dict[str, Any]] = []
        is_conference = venue.get("kind") == "conference"
        while offset < self.max_per_venue:
            filters = [f"from-pub-date:{from_date}", f"until-pub-date:{to_date}"]
            params: dict[str, Any] = {"rows": rows, "offset": offset}
            if venue.get("issn"):
                filters.insert(0, f"issn:{venue['issn']}")
            if is_conference:
                filters.append("type:proceedings-article")
                params["query.container-title"] = venue.get("query") or venue.get("venue")
            params["filter"] = ",".join(filters)
            data = request_json(
                f"{self.base_url}?{urllib.parse.urlencode(params)}",
                timeout=self.timeout,
                retries=self.retries,
            )
            items = data.get("message", {}).get("items", [])
            if not items:
                break
            for item in items:
                paper = self._normalize(item, venue, to_date)
                if paper and (not is_conference or self._conference_matches(paper, venue)):
                    collected.append(paper)
                    if len(collected) >= self.max_per_venue:
                        return collected
            offset += rows
            if offset >= int(data.get("message", {}).get("total-results", 0)):
                break
        return collected

    @staticmethod
    def _conference_matches(paper: dict[str, Any], venue: dict[str, Any]) -> bool:
        container = paper.get("journal", "").casefold()
        aliases = [venue.get("venue", ""), *(venue.get("aliases") or [])]
        return any(alias.casefold() in container for alias in aliases if len(alias) > 3)

    @staticmethod
    def _normalize(item: dict[str, Any], venue: dict[str, Any], to_date: str) -> dict[str, Any] | None:
        title = html.unescape((item.get("title") or [""])[0]).strip()
        if not title or any(re.match(pattern, title.casefold()) for pattern in NON_RESEARCH_PATTERNS):
            return None
        date_parts = (
            item.get("published-print", {}).get("date-parts", [[]])[0]
            or item.get("published-online", {}).get("date-parts", [[]])[0]
            or item.get("created", {}).get("date-parts", [[]])[0]
        )
        publication_date = ""
        try:
            if len(date_parts) >= 3:
                publication_date = date(int(date_parts[0]), int(date_parts[1]), int(date_parts[2])).isoformat()
            elif len(date_parts) == 2:
                publication_date = f"{int(date_parts[0]):04d}-{int(date_parts[1]):02d}"
            elif len(date_parts) == 1:
                publication_date = str(int(date_parts[0]))
        except (TypeError, ValueError):
            publication_date = ""
        doi = normalize_doi(item.get("DOI", ""))
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author") or []]
        return {
            "title": title,
            "abstract": re.sub(r"^abstract\.?\s*", "", strip_markup(item.get("abstract", "")), flags=re.I),
            "publication_date": publication_date,
            "year": int(date_parts[0]) if date_parts else None,
            "venue": html.unescape((item.get("container-title") or [venue.get("journal") or venue.get("venue", "")])[0]),
            "journal": html.unescape((item.get("container-title") or [venue.get("journal") or venue.get("venue", "")])[0]),
            "journal_source": venue.get("journal") or venue.get("venue", ""),
            "pool": venue.get("pool", ""),
            "authors": "; ".join(authors[:8]) + (" et al." if len(authors) > 8 else ""),
            "doi": doi,
            "doi_raw": doi,
            "doi_url": f"https://doi.org/{doi}" if doi else "",
            "crossref_url": item.get("URL", ""),
            "type": item.get("type", ""),
            "citation_count": item.get("is-referenced-by-count", 0),
            "subject": item.get("subject", []),
            "source": "crossref",
            "abstract_source": "crossref" if item.get("abstract") else "",
        }
