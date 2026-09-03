from __future__ import annotations

import time
import urllib.parse
from typing import Any

from ..utils import normalize_doi, request_json


class OpenAlexEnricher:
    base_url = "https://api.openalex.org/works"

    def __init__(self, *, mailto: str = "", timeout: float = 30.0, retries: int = 3):
        self.mailto = mailto
        self.timeout = timeout
        self.retries = retries

    @staticmethod
    def reconstruct_abstract(index: dict[str, list[int]] | None) -> str:
        if not index:
            return ""
        tokens = sorted((position, word) for word, positions in index.items() for position in positions)
        return " ".join(word for _, word in tokens)

    def enrich(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_doi = {normalize_doi(p.get("doi_raw", "")): p for p in papers if normalize_doi(p.get("doi_raw", ""))}
        dois = list(by_doi)
        for start in range(0, len(dois), 50):
            batch = dois[start:start + 50]
            params = {
                "filter": "doi:" + "|".join(batch),
                "per-page": 50,
                "select": "doi,abstract_inverted_index,primary_topic,topics",
            }
            if self.mailto:
                params["mailto"] = self.mailto
            try:
                data = request_json(
                    f"{self.base_url}?{urllib.parse.urlencode(params)}",
                    timeout=self.timeout,
                    retries=self.retries,
                )
            except Exception:
                continue
            for work in data.get("results", []):
                doi = normalize_doi(work.get("doi", ""))
                paper = by_doi.get(doi)
                if not paper:
                    continue
                if not paper.get("abstract"):
                    abstract = self.reconstruct_abstract(work.get("abstract_inverted_index"))
                    if abstract:
                        paper["abstract"] = abstract
                        paper["abstract_source"] = "openalex"
                primary = work.get("primary_topic") or {}
                paper["primary_topic"] = primary.get("display_name", "")
                paper["topic_subfield"] = (primary.get("subfield") or {}).get("display_name", "")
                paper["topic_field"] = (primary.get("field") or {}).get("display_name", "")
                paper["all_topics"] = [t.get("display_name", "") for t in work.get("topics") or [] if t.get("display_name")]
            if start + 50 < len(dois):
                time.sleep(0.15)
        return papers

