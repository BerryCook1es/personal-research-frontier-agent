from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils import normalize_doi, stable_paper_id


READING_STATUSES = {"new", "saved", "reading", "read", "ignored", "cited"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FrontierDatabase:
    """SQLite state store for incremental discovery, checkpoints, runs, and feedback."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY,
            stable_id TEXT NOT NULL,
            doi TEXT,
            title TEXT NOT NULL,
            abstract TEXT DEFAULT '',
            publication_date TEXT DEFAULT '',
            venue TEXT DEFAULT '',
            source TEXT DEFAULT '',
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            profile TEXT NOT NULL,
            keyword_tier TEXT DEFAULT 'other',
            semantic_score REAL,
            relevance_score INTEGER,
            priority TEXT,
            research_track TEXT,
            related_project TEXT,
            reading_status TEXT NOT NULL DEFAULT 'new',
            paper_json TEXT NOT NULL,
            UNIQUE(profile, stable_id),
            CHECK(reading_status IN ('new','saved','reading','read','ignored','cited'))
        );
        CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
        CREATE INDEX IF NOT EXISTS idx_papers_profile ON papers(profile);
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            scanned INTEGER DEFAULT 0,
            candidates INTEGER DEFAULT 0,
            count_a INTEGER DEFAULT 0,
            count_b INTEGER DEFAULT 0,
            count_c INTEGER DEFAULT 0,
            count_d INTEGER DEFAULT 0,
            count_ignore INTEGER DEFAULT 0,
            errors_json TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL,
            rating INTEGER,
            action TEXT,
            note TEXT,
            project TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(paper_id) REFERENCES papers(id),
            CHECK(rating IS NULL OR rating BETWEEN 1 AND 5)
        );
        CREATE TABLE IF NOT EXISTS judgments (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL,
            context_hash TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            raw_response TEXT,
            parsed_json TEXT,
            error TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(paper_id, context_hash, model),
            FOREIGN KEY(paper_id) REFERENCES papers(id)
        );
        """)
        self.connection.commit()

    def start_run(self, profile: str, from_date: str, to_date: str) -> str:
        run_id = uuid.uuid4().hex
        self.connection.execute(
            "INSERT INTO runs(run_id,profile,from_date,to_date,started_at) VALUES(?,?,?,?,?)",
            (run_id, profile, from_date, to_date, utc_now()),
        )
        self.connection.commit()
        return run_id

    def finish_run(self, run_id: str, stats: dict[str, Any], errors: list[dict[str, Any]]) -> None:
        self.connection.execute(
            """UPDATE runs SET finished_at=?, scanned=?, candidates=?, count_a=?, count_b=?,
               count_c=?, count_d=?, count_ignore=?, errors_json=? WHERE run_id=?""",
            (
                utc_now(), stats.get("scanned", 0), stats.get("candidates", 0),
                stats.get("A", 0), stats.get("B", 0), stats.get("C", 0), stats.get("D", 0),
                stats.get("Ignore", 0), json.dumps(errors, ensure_ascii=False), run_id,
            ),
        )
        self.connection.commit()

    def upsert_paper(self, paper: dict[str, Any], profile: str) -> tuple[int, bool]:
        stable_id = stable_paper_id(paper)
        existing = self.connection.execute(
            "SELECT id,first_seen,reading_status FROM papers WHERE profile=? AND stable_id=?", (profile, stable_id)
        ).fetchone()
        now = utc_now()
        paper["stable_id"] = stable_id
        if existing:
            paper_id = int(existing["id"])
            paper["reading_status"] = existing["reading_status"]
            paper["first_seen"] = existing["first_seen"]
            paper["last_seen"] = now
            self.connection.execute(
                """UPDATE papers SET doi=?, title=?, abstract=?, publication_date=?, venue=?, source=?,
                   last_seen=?, paper_json=? WHERE id=?""",
                (
                    normalize_doi(paper.get("doi_raw") or paper.get("doi", "")), paper.get("title", ""),
                    paper.get("abstract", ""), paper.get("publication_date", ""),
                    paper.get("venue") or paper.get("journal", ""), paper.get("source", ""), now,
                    json.dumps(paper, ensure_ascii=False), paper_id,
                ),
            )
            is_new = False
        else:
            cursor = self.connection.execute(
                """INSERT INTO papers(stable_id,doi,title,abstract,publication_date,venue,source,
                   first_seen,last_seen,profile,paper_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    stable_id, normalize_doi(paper.get("doi_raw") or paper.get("doi", "")),
                    paper.get("title", ""), paper.get("abstract", ""), paper.get("publication_date", ""),
                    paper.get("venue") or paper.get("journal", ""), paper.get("source", ""), now, now,
                    profile, json.dumps(paper, ensure_ascii=False),
                ),
            )
            paper_id = int(cursor.lastrowid)
            is_new = True
            paper["reading_status"] = "new"
            paper["first_seen"] = now
            paper["last_seen"] = now
        self.connection.commit()
        paper["paper_id"] = paper_id
        return paper_id, is_new

    def update_analysis(self, paper_id: int, paper: dict[str, Any]) -> None:
        self.connection.execute(
            """UPDATE papers SET title=?, abstract=?, venue=?, keyword_tier=?, semantic_score=?,
               relevance_score=?, priority=?, research_track=?, related_project=?, paper_json=? WHERE id=?""",
            (
                paper.get("title", ""), paper.get("abstract", ""),
                paper.get("venue") or paper.get("journal", ""), paper.get("keyword_tier", "other"), paper.get("semantic_score"),
                paper.get("relevance_score"), paper.get("priority"), paper.get("research_track"),
                paper.get("related_project"), json.dumps(paper, ensure_ascii=False), paper_id,
            ),
        )
        self.connection.commit()

    def get_completed_judgment(self, paper_id: int, context_hash: str, model: str) -> tuple[str, dict[str, Any]] | None:
        row = self.connection.execute(
            """SELECT raw_response,parsed_json FROM judgments
               WHERE paper_id=? AND context_hash=? AND model=? AND status='complete'""",
            (paper_id, context_hash, model),
        ).fetchone()
        if not row:
            return None
        return row["raw_response"] or "", json.loads(row["parsed_json"])

    def save_judgment(self, paper_id: int, context_hash: str, model: str, *, status: str,
                      raw_response: str = "", parsed: dict[str, Any] | None = None, error: str = "") -> None:
        self.connection.execute(
            """INSERT INTO judgments(paper_id,context_hash,model,status,raw_response,parsed_json,error,updated_at)
               VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(paper_id,context_hash,model) DO UPDATE SET
               status=excluded.status,raw_response=excluded.raw_response,parsed_json=excluded.parsed_json,
               error=excluded.error,updated_at=excluded.updated_at""",
            (paper_id, context_hash, model, status, raw_response,
             json.dumps(parsed, ensure_ascii=False) if parsed is not None else None, error, utc_now()),
        )
        self.connection.commit()

    def import_feedback(self, records: list[dict[str, Any]], profile: str | None = None) -> tuple[int, list[str]]:
        imported = 0
        errors: list[str] = []
        for index, record in enumerate(records):
            try:
                rating = record.get("rating")
                if rating not in (None, ""):
                    rating = int(rating)
                    if rating not in range(1, 6):
                        raise ValueError("rating must be 1..5")
                status = record.get("reading_status") or record.get("action") or "saved"
                if status not in READING_STATUSES:
                    raise ValueError(f"invalid reading_status: {status}")
                paper_id = record.get("paper_id")
                if not paper_id and record.get("stable_id"):
                    query = "SELECT id FROM papers WHERE stable_id=?"
                    params: list[Any] = [record["stable_id"]]
                    if profile:
                        query += " AND profile=?"
                        params.append(profile)
                    row = self.connection.execute(query, params).fetchone()
                    paper_id = row["id"] if row else None
                if not paper_id:
                    raise ValueError("paper not found")
                self.connection.execute("UPDATE papers SET reading_status=? WHERE id=?", (status, paper_id))
                self.connection.execute(
                    "INSERT INTO feedback(paper_id,rating,action,note,project,timestamp) VALUES(?,?,?,?,?,?)",
                    (paper_id, rating, status, record.get("note", ""), record.get("related_project") or record.get("project", ""),
                     record.get("timestamp") or utc_now()),
                )
                imported += 1
            except Exception as exc:
                errors.append(f"record {index}: {exc}")
        self.connection.commit()
        return imported, errors
