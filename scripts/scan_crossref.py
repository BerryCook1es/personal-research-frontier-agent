#!/usr/bin/env python3
"""Scan recent papers using CrossRef API (free, no key required).

Uses ISSN-based filtering for precise journal matching.
Output format is compatible with screen_by_profile.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

from _lib import ROOT, fetch_journal_papers


def today_iso() -> str:
    return dt.date.today().isoformat()


def main():
    parser = argparse.ArgumentParser(description="Scan recent papers via CrossRef API (ISSN-based)")
    parser.add_argument("--watchlist", type=Path, required=True, help="JSON watchlist file with ISSNs")
    parser.add_argument("--days", type=int, default=7, help="Look back N days")
    parser.add_argument("--from-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--pools", nargs="+", default=None, help="Filter by pool labels")
    parser.add_argument("--max-per-journal", type=int, default=100, help="Max papers per journal")
    parser.add_argument("--output", type=Path, help="Output JSON file")
    parser.add_argument("--sleep", type=float, default=0.3, help="Seconds between journal requests")
    args = parser.parse_args()

    with open(args.watchlist, "r", encoding="utf-8") as f:
        watchlist = json.load(f)

    to_date = args.to_date or today_iso()
    from_date = args.from_date or (
        dt.date.fromisoformat(to_date) - dt.timedelta(days=args.days)
    ).isoformat()

    allowed_pools = set(args.pools) if args.pools else None

    journals_to_scan = []
    for entry in watchlist:
        pool = entry.get("pool", "")
        if allowed_pools and pool not in allowed_pools:
            continue
        issn = entry.get("issn", "")
        if not issn:
            print(f"  SKIP: {entry['journal']} — no ISSN in watchlist", file=sys.stderr)
            continue
        journals_to_scan.append({"journal": entry["journal"], "issn": issn, "pool": pool})

    print(f"Scanning {len(journals_to_scan)} journals via CrossRef...")
    print(f"Date range: {from_date} → {to_date}")
    print()

    all_papers = []
    source_errors = []

    for i, jinfo in enumerate(journals_to_scan):
        jname, issn, pool = jinfo["journal"], jinfo["issn"], jinfo["pool"]
        print(f"[{i+1}/{len(journals_to_scan)}] {jname} ...", end=" ", flush=True)

        try:
            papers = fetch_journal_papers(jname, issn, from_date, to_date, pool,
                                          max_results=args.max_per_journal)
            all_papers.extend(papers)
            print(f"{len(papers)} papers")
        except Exception as e:
            print(f"ERROR: {e}")
            source_errors.append({
                "journal": jname, "pool": pool, "status": "error", "error": str(e),
            })

        if i < len(journals_to_scan) - 1:
            time.sleep(args.sleep)

    # DOI 去重
    seen_doi = set()
    unique_papers = []
    for p in all_papers:
        doi = p.get("doi_raw", "")
        if doi and doi in seen_doi:
            continue
        if doi:
            seen_doi.add(doi)
        unique_papers.append(p)

    print(f"\nTotal: {len(unique_papers)} unique papers from {len(journals_to_scan)} journals")
    if source_errors:
        print(f"Errors: {len(source_errors)} journals")

    output = {
        "coverage": {"from": from_date, "to": to_date},
        "watchlist_journals": len(journals_to_scan),
        "pools": sorted(set(j["pool"] for j in journals_to_scan)),
        "state_file": str(ROOT / "state" / "reading_state.json"),
        "state_updated": False,
        "new": unique_papers,
        "already_seen": [],
        "needs_manual_verification": [],
        "excluded_non_research": [],
        "source_errors": source_errors,
        "data_source": "crossref",
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Saved: {args.output}")
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
