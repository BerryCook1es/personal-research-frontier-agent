from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__


ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = f"personal-research-frontier-agent/{__version__}"


def normalize_openai_api_base(value: str) -> str:
    """Return an OpenAI-compatible API root from either a root or full endpoint URL."""
    value = (value or "").strip()
    markdown_link = re.fullmatch(r"\[[^\]]*\]\((https?://[^)]+)\)", value)
    if markdown_link:
        value = markdown_link.group(1)
    value = value.rstrip("/")
    for suffix in ("/chat/completions", "/embeddings"):
        if value.endswith(suffix):
            return value[:-len(suffix)].rstrip("/")
    return value


def openai_api_endpoint(api_base: str, resource: str) -> str:
    """Build one endpoint while accepting `/v1` or a previously full endpoint."""
    return f"{normalize_openai_api_base(api_base)}/{resource.strip('/')}"


def strip_markup(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_doi(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value.strip()


def stable_paper_id(paper: dict[str, Any]) -> str:
    doi = normalize_doi(str(paper.get("doi_raw") or paper.get("doi") or ""))
    if doi:
        return f"doi:{doi}"
    title = re.sub(r"\W+", " ", str(paper.get("title") or "").casefold()).strip()
    return "title:" + hashlib.sha256(title.encode("utf-8")).hexdigest()


def slugify(value: str, max_length: int = 80) -> str:
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return value[:max_length] or "item"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json")
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
        time.sleep(min(2 ** attempt, 8))
    return {}
