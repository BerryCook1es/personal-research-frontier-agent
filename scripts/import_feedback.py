#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_frontier_agent.storage import FrontierDatabase


def main() -> int:
    parser = argparse.ArgumentParser(description="Import feedback.json into SQLite")
    parser.add_argument("feedback", type=Path)
    parser.add_argument("--database", type=Path, default=ROOT / "state" / "frontier.db")
    parser.add_argument("--profile")
    args = parser.parse_args()
    payload = json.loads(args.feedback.read_text(encoding="utf-8"))
    records = payload.get("feedback", payload) if isinstance(payload, dict) else payload
    profile = args.profile or (payload.get("profile") if isinstance(payload, dict) else None)
    db = FrontierDatabase(args.database)
    try:
        imported, errors = db.import_feedback(records, profile)
    finally:
        db.close()
    print(json.dumps({"imported": imported, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

