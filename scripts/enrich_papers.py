#!/usr/bin/env python3
"""Compatibility CLI for OpenAlex enrichment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_frontier_agent.providers.openalex import OpenAlexEnricher


def reconstruct_abstract(index):
    return OpenAlexEnricher.reconstruct_abstract(index)


def enrich_papers(papers):
    return OpenAlexEnricher().enrich(papers)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich paper JSON through OpenAlex")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--field", default="new")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    fields = ["new", "already_seen"] if args.field == "both" else [args.field]
    for field in fields:
        data[field] = enrich_papers(data.get(field, []))
    target = args.output or args.input
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
