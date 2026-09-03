from __future__ import annotations

from pathlib import Path
from typing import Any


def _esc(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def render_preview(papers: list[dict[str, Any]], stats: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Weekly Research Brief",
        f"Scanned: {stats.get('scanned', 0)} | Candidates: {stats.get('candidates', 0)} | A: {stats.get('A', 0)} | B: {stats.get('B', 0)} | C: {stats.get('C', 0)}",
        "",
        "| Priority | Score | Project | Title | Why relevant | Action |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for paper in papers:
        lines.append(
            f"| {_esc(paper.get('priority'))} | {_esc(paper.get('relevance_score'))} | "
            f"{_esc(paper.get('related_project'))} | {_esc(paper.get('title_cn') or paper.get('title'))} | "
            f"{_esc(paper.get('why_relevant'))} | {_esc(paper.get('recommended_action'))} |"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path

