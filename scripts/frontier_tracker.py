#!/usr/bin/env python3
"""CLI entrypoint for Personal Research Frontier Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_frontier_agent.config import load_config
from research_frontier_agent.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal Research Frontier Agent")
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument("--profile", help="Research Profile markdown")
    parser.add_argument("--project", dest="projects", action="append", help="Project Context markdown; repeatable")
    parser.add_argument("--days", type=int)
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--data-sources", nargs="+")
    parser.add_argument("--enrich", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--embedding", dest="embedding_enabled", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--llm-judge", dest="llm_judge_enabled", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--skip-translate", action="store_true")
    parser.add_argument("--output-modes", nargs="+", choices=["html", "excel", "app", "notes", "codex"])
    parser.add_argument("--pools", nargs="+", help="Compatibility option; filter journal pools")
    parser.add_argument("--max-per-journal", dest="max_per_venue", type=int)
    parser.add_argument("--sleep", dest="request_sleep", type=float)
    parser.add_argument("--skip-scan", action="store_true")
    parser.add_argument("--skip-screen", action="store_true")
    parser.add_argument("--scan-file")
    parser.add_argument("--screened-file")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    overrides = {
        "profile": args.profile,
        "projects": args.projects,
        "days": args.days,
        "from_date": args.from_date,
        "to_date": args.to_date,
        "data_sources": args.data_sources,
        "enrich": args.enrich,
        "embedding_enabled": args.embedding_enabled,
        "llm_judge_enabled": args.llm_judge_enabled,
        "translation_enabled": False if args.skip_translate else None,
        "output_modes": args.output_modes,
        "max_per_venue": args.max_per_venue,
        "request_sleep": args.request_sleep,
        "skip_scan": args.skip_scan or None,
        "skip_screen": args.skip_screen or None,
        "scan_file": args.scan_file,
        "screened_file": args.screened_file,
    }
    config = load_config(args.config, overrides)
    if args.pools:
        watchlist_path = ROOT / config["watchlist"]
        venues = json.loads(watchlist_path.read_text(encoding="utf-8"))
        filtered = [venue for venue in venues if venue.get("pool") in set(args.pools)]
        temp = ROOT / "outputs" / "data" / "_filtered_watchlist.json"
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
        config["watchlist"] = str(temp)
        config["conference_watchlist"] = ""
    try:
        result = run_pipeline(config)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "run_id": result["run_id"], "profile": result["profile"]["name"],
        "coverage": result["coverage"], "stats": result["stats"],
        "new": result["new_count"], "already_seen": result["already_seen_count"],
        "errors": result["errors"], "paths": result["paths"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

