#!/usr/bin/env python3
"""Screen frontier scan results by research profile using keyword-based tiering.

Classification tiers:
  core    — directly on-topic
  proxy   — adjacent methods/themes
  eco     — broader context
  other   — no match, excluded from digest

Usage:
  python -X utf8 scripts/screen_by_profile.py \
    --input outputs/data/frontier_scan_<date>.json \
    --profile references/profile-scholarly-kg-llm.md \
    --output outputs/data/frontier_screened_<date>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _lib import load_profile_keywords, screen_papers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Screen scan results by profile keywords.")
    parser.add_argument("--input", type=Path, required=True, help="Scan JSON file.")
    parser.add_argument("--profile", type=Path, help="Profile markdown with keyword sections.")
    parser.add_argument("--output", type=Path, help="Output screened JSON.")
    parser.add_argument("--field", default="new", help="Field to screen (new, already_seen, or both).")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    core_kw, proxy_kw, eco_kw = load_profile_keywords(args.profile)

    print(f"Profile: core={len(core_kw)} proxy={len(proxy_kw)} eco={len(eco_kw)} keywords",
          file=sys.stderr)

    fields = ["already_seen", "new"] if args.field == "both" else [args.field]

    stats = {"total": 0, "core": 0, "proxy": 0, "eco": 0, "other": 0}
    for field in fields:
        papers = data.get(field, [])
        if not papers:
            continue
        scored = screen_papers(papers, core_kw, proxy_kw, eco_kw)
        data[field] = scored
        for p in scored:
            stats["total"] += 1
            stats[p["tier"]] = stats.get(p["tier"], 0) + 1

    data["_screened"] = True
    data["_profile_stats"] = stats

    print(f"Total: {stats['total']} | core={stats['core']} proxy={stats['proxy']} "
          f"eco={stats['eco']} other={stats['other']}", file=sys.stderr)

    output_path = args.output or args.input
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
