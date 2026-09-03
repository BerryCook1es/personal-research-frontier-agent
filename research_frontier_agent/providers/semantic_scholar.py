from __future__ import annotations

import time
import urllib.parse
from typing import Any

from .base import PaperProvider
from ..utils import normalize_doi, request_json


DEFAULT_BASE_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS = ",".join((
    "paperId", "externalIds", "url", "title", "abstract", "venue", "journal",
    "year", "authors", "citationCount", "publicationDate", "publicationTypes",
    "openAccessPdf", "fieldsOfStudy", "s2FieldsOfStudy",
))


class SemanticScholarProvider(PaperProvider):
    """Discover recent papers through Semantic Scholar Academic Graph bulk search."""

    name = "semantic_scholar"

    def __init__(
        self,
        queries: list[str],
        *,
        api_key: str = "",
        api_base: str = DEFAULT_BASE_URL,
        max_results_per_query: int = 100,
        timeout: float = 30.0,
        retries: int = 3,
        sleep: float = 1.1,
    ):
        self.queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))
        self.api_key = api_key.strip()
        self.api_base = api_base.rstrip("/")
        self.max_results_per_query = max(1, min(1000, int(max_results_per_query)))
        self.timeout = timeout
        self.retries = retries
        self.sleep = max(0.0, sleep)

    def discover(self, from_date: str, to_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        papers: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for index, query in enumerate(self.queries):
            try:
                papers.extend(self._search(query, from_date, to_date))
            except Exception as exc:
                errors.append({"source": self.name, "query": query, "error": str(exc)})
            if index + 1 < len(self.queries):
                time.sleep(self.sleep)
        return papers, errors

    def _search(self, query: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
        params = {
            "query": query,
            "publicationDateOrYear": f"{from_date}:{to_date}",
            "fields": FIELDS,
            "sort": "publicationDate:desc",
        }
        headers = {"x-api-key": self.api_key} if self.api_key else None
        data = request_json(
            f"{self.api_base}/paper/search/bulk?{urllib.parse.urlencode(params)}",
            headers=headers,
            timeout=self.timeout,
            retries=self.retries,
        )
        items = data.get("data", [])[:self.max_results_per_query]
        return [paper for item in items if (paper := self._normalize(item, query))]

    @staticmethod
    def _normalize(item: dict[str, Any], query: str) -> dict[str, Any] | None:
        title = str(item.get("title") or "").strip()
        if not title:
            return None
        external_ids = item.get("externalIds") or {}
        doi = normalize_doi(str(external_ids.get("DOI") or ""))
        journal = item.get("journal") or {}
        venue = str(item.get("venue") or journal.get("name") or "").strip()
        authors = [str(author.get("name") or "").strip() for author in item.get("authors") or []]
        authors = [author for author in authors if author]
        s2_fields = [
            str(field.get("category") or "").strip()
            for field in item.get("s2FieldsOfStudy") or [] if isinstance(field, dict)
        ]
        subjects = list(dict.fromkeys([
            *[str(value).strip() for value in item.get("fieldsOfStudy") or []],
            *[value for value in s2_fields if value],
        ]))
        pdf = item.get("openAccessPdf") or {}
        return {
            "title": title,
            "abstract": str(item.get("abstract") or "").strip(),
            "publication_date": str(item.get("publicationDate") or item.get("year") or ""),
            "year": item.get("year"),
            "venue": venue,
            "journal": venue,
            "journal_source": venue,
            "pool": "multi-source-discovery",
            "authors": "; ".join(authors[:8]) + (" et al." if len(authors) > 8 else ""),
            "doi": doi,
            "doi_raw": doi,
            "doi_url": f"https://doi.org/{doi}" if doi else "",
            "type": "; ".join(item.get("publicationTypes") or []),
            "citation_count": item.get("citationCount", 0),
            "subject": subjects,
            "source": "semantic_scholar",
            "abstract_source": "semantic_scholar" if item.get("abstract") else "",
            "s2_paper_id": item.get("paperId", ""),
            "semantic_scholar_url": item.get("url", ""),
            "open_access_pdf_url": pdf.get("url", "") if isinstance(pdf, dict) else "",
            "arxiv_id": external_ids.get("ArXiv", ""),
            "discovery_query": query,
        }
