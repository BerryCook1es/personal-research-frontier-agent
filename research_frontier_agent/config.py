from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .utils import ROOT


DEFAULT_CONFIG: dict[str, Any] = {
    "profile": "references/profile-scholarly-kg-llm.md",
    "projects": [],
    "days": 7,
    "from_date": None,
    "to_date": None,
    "data_sources": ["crossref"],
    "watchlist": "references/journal-watchlist.json",
    "conference_watchlist": "references/conference-watchlist.json",
    "enrich": False,
    "embedding_enabled": False,
    "embedding_backend": "sentence-transformers",
    "embedding_model": "BAAI/bge-m3",
    "embedding_api_base": "",
    "embedding_api_key": "",
    "embedding_threshold": 0.45,
    "llm_judge_enabled": False,
    "llm_model": "",
    "api_base": "",
    "api_key": "",
    "temperature": 0.1,
    "translation_enabled": False,
    "translation_backend": "auto",
    "translation_model": "",
    "translation_api_base": "",
    "translation_api_key": "",
    "output_modes": ["html"],
    "output_root": "outputs",
    "reading_capacity": {"max_A": 5, "max_B": 10, "max_C": 10},
    "database": "state/frontier.db",
    "request_timeout": 30,
    "request_retries": 3,
    "max_per_venue": 50,
    "request_sleep": 0.2,
}


def _merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        config = _merge(config, loaded)
    if overrides:
        config = _merge(config, {k: v for k, v in overrides.items() if v is not None})
    return config


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path
