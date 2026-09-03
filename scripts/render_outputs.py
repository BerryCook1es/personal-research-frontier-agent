#!/usr/bin/env python3
"""Compatibility CLI for standalone Excel/App/Notes/Preview rendering."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_frontier_agent.render import render_app, render_excel, render_notes, render_preview
from research_frontier_agent.render.common import output_paths


def _papers(data):
    return data.get("all_candidates") or data.get("report_papers") or data.get("new", []) + data.get("already_seen", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["excel", "app", "notes", "codex"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", default="scholarly-kg-llm")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    papers = _papers(data)
    stats = data.get("judged_stats") or data.get("stats") or {"scanned": len(papers), "candidates": len(papers)}
    coverage = data.get("coverage", {"from": "", "to": date.today().isoformat()})
    paths = output_paths(args.profile, coverage.get("to") or date.today().isoformat())
    target = args.output or paths[args.mode]
    if args.mode == "excel":
        result = render_excel(papers, stats, target)
    elif args.mode == "app":
        result = render_app(papers, stats, target, args.profile, coverage)
    elif args.mode == "notes":
        result = render_notes(papers, target)
    else:
        result = render_preview(papers[:args.limit], stats, target)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
