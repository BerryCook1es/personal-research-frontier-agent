"""Apply journal exclusions consistently across providers and resumed scans."""

import re
import unicodedata
from typing import Any

from ..utils import normalize_doi


def _normalized_name(value: str) -> str:
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", value).casefold())


def is_excluded_journal(paper: dict[str, Any], excluded_journals: list[str]) -> bool:
    excluded = {_normalized_name(name) for name in excluded_journals if name.strip()}
    for key in ("venue", "journal", "journal_source"):
        if _normalized_name(str(paper.get(key) or "")) in excluded:
            return True
    # PLOS ONE records sometimes lack venue metadata. Its journal-specific DOI
    # namespace avoids excluding other PLOS journals or title keyword matches.
    if "plosone" in excluded:
        return any(
            normalize_doi(str(paper.get(key) or "")).startswith("10.1371/journal.pone.")
            for key in ("doi", "doi_raw", "doi_url")
        )
    return False
