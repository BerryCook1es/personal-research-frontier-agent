#!/usr/bin/env python3
"""OpenAlex 元数据丰富：回填缺失摘要 + 补充主题标签。

批量查询（50 DOI/次），无需 API key，polite pool 自动启用。

Usage:
  python -X utf8 scripts/enrich_papers.py \
    --input outputs/data/frontier_scan_<date>.json \
    --output outputs/data/frontier_enriched_<date>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

from _lib import ROOT, request_json as _request_json

OPENALEX_BASE = "https://api.openalex.org/works"
BATCH_SIZE = 50  # OpenAlex 单次最大 DOI 数
SLEEP_BETWEEN = 0.15  # polite pool 10 req/s，保守用 0.15s


# ══════════════════════════════════════════════════════════════
# Abstract 重建
# ══════════════════════════════════════════════════════════════

def reconstruct_abstract(inverted_index: dict | None) -> str:
    """OpenAlex abstract_inverted_index → 纯文本。"""
    if not inverted_index:
        return ""
    positions = []
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions.append((pos, word))
    positions.sort()
    return " ".join(w for _, w in positions)


# ══════════════════════════════════════════════════════════════
# Topic 提取
# ══════════════════════════════════════════════════════════════

def extract_topics(work: dict) -> dict:
    """从 OpenAlex work 对象提取主题标签。"""
    primary = work.get("primary_topic") or {}
    all_topics = work.get("topics") or []

    return {
        "primary_topic": (primary.get("display_name") or ""),
        "topic_subfield": ((primary.get("subfield") or {}).get("display_name") or ""),
        "topic_field": ((primary.get("field") or {}).get("display_name") or ""),
        "all_topics": [t.get("display_name", "") for t in all_topics if t.get("display_name")],
    }


# ══════════════════════════════════════════════════════════════
# OpenAlex 批量查询
# ══════════════════════════════════════════════════════════════

def fetch_openalex_batch(dois: list[str]) -> dict[str, dict]:
    """批量查询 OpenAlex，返回 {doi_lower: work} 映射。"""
    if not dois:
        return {}

    doi_filter = "|".join(dois)
    params = {
        "filter": f"doi:{doi_filter}",
        "per-page": str(BATCH_SIZE),
        "mailto": "your-email@example.com",
        "select": "doi,abstract_inverted_index,primary_topic,topics",
    }
    url = f"{OPENALEX_BASE}?{urllib.parse.urlencode(params)}"

    data = _request_json(url)
    if not data:
        return {}

    results = {}
    for work in data.get("results", []):
        doi_raw = (work.get("doi") or "").lower().removeprefix("https://doi.org/")
        if doi_raw:
            results[doi_raw] = work
    return results


def enrich_papers(papers: list[dict]) -> list[dict]:
    """批量丰富：回填摘要 + 补充主题标签。"""
    # 提取需要处理的 DOI
    doi_map: dict[str, list[int]] = {}  # doi_lower → [paper indices]
    no_doi_count = 0
    for i, p in enumerate(papers):
        doi = (p.get("doi_raw") or "").strip().lower()
        if doi:
            doi_map.setdefault(doi, []).append(i)
        else:
            no_doi_count += 1

    dois = list(doi_map.keys())
    print(f"Enriching {len(papers)} papers ({len(dois)} unique DOIs) via OpenAlex...",
          file=sys.stderr)
    if no_doi_count:
        print(f"  Warning: {no_doi_count} papers have no DOI, cannot enrich", file=sys.stderr)

    # 分批查询
    enriched_count = 0
    abstract_filled = 0

    for batch_start in range(0, len(dois), BATCH_SIZE):
        batch_dois = dois[batch_start:batch_start + BATCH_SIZE]
        batch_results = fetch_openalex_batch(batch_dois)

        for doi_lower, work in batch_results.items():
            indices = doi_map.get(doi_lower, [])
            for idx in indices:
                p = papers[idx]

                # 1. 回填摘要
                if not p.get("abstract"):
                    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                    if abstract:
                        p["abstract"] = abstract
                        p["abstract_source"] = "openalex"
                        abstract_filled += 1

                # 2. 补充主题标签
                topics = extract_topics(work)
                p["primary_topic"] = topics["primary_topic"]
                p["topic_subfield"] = topics["topic_subfield"]
                p["topic_field"] = topics["topic_field"]
                p["all_topics"] = topics["all_topics"]

                enriched_count += 1

        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(dois) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches}: "
              f"{len(batch_results)}/{len(batch_dois)} found", file=sys.stderr)

        if batch_start + BATCH_SIZE < len(dois):
            time.sleep(SLEEP_BETWEEN)

    print(f"Enriched: {enriched_count} papers | "
          f"Abstracts backfilled: {abstract_filled}", file=sys.stderr)
    return papers


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich scan results with OpenAlex metadata (abstract + topics)."
    )
    parser.add_argument("--input", type=Path, required=True, help="Scan JSON file.")
    parser.add_argument("--output", type=Path, help="Output enriched JSON file.")
    parser.add_argument("--field", default="new", help="Field to enrich (new, already_seen, or both).")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[ERROR] Input not found: {args.input}", file=sys.stderr)
        return 1

    data = json.loads(args.input.read_text(encoding="utf-8"))
    fields = ["already_seen", "new"] if args.field == "both" else [args.field]

    total = 0
    for field in fields:
        papers = data.get(field, [])
        if not papers:
            continue
        print(f"\nField: {field} ({len(papers)} papers)", file=sys.stderr)
        data[field] = enrich_papers(papers)
        total += len(papers)

    data["_enriched"] = True

    output_path = args.output or args.input
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

