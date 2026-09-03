#!/usr/bin/env python3
"""Compatibility CLI for bilingual HTML rendering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_frontier_agent.render.report import render_report
from research_frontier_agent.screening.llm_judge import fallback_judgment


def render_bilingual_html(data, title, profile_name, output_path, to_date=""):
    if "report_papers" not in data:
        papers = data.get("new", []) + data.get("already_seen", [])
        for paper in papers:
            paper.setdefault("keyword_tier", paper.get("tier", "other"))
            paper.update({k: paper.get(k, v) for k, v in fallback_judgment(paper).items()})
            paper.setdefault("venue", paper.get("journal", ""))
        stats = {"scanned": len(papers), "candidates": len(papers), "A": 0, "B": 0, "C": 0, "D": 0, "Ignore": 0}
        for paper in papers:
            stats[paper["priority"]] += 1
        data = {
            "profile": {"name": profile_name},
            "coverage": data.get("coverage", {"from": "", "to": to_date}),
            "stats": stats,
            "report_papers": [p for p in papers if p.get("priority") != "Ignore"],
        }
    return render_report(data, Path(output_path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="scholarly-kg-llm")
    parser.add_argument("--title")
    args = parser.parse_args()
    render_bilingual_html(json.loads(args.input.read_text(encoding="utf-8")), args.title or "Weekly Research Brief", args.profile, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
