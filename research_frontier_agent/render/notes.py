from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..utils import slugify


def _yaml(value: Any) -> str:
    return str(value or "").replace('"', "'").replace("\n", " ")


def render_notes(papers: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.mkdir(parents=True, exist_ok=True)
    for paper in papers:
        priority = paper.get("priority", "D")
        if priority == "Ignore":
            continue
        folder = output_path / priority
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{paper.get('publication_date') or 'nodate'}_{slugify(paper.get('title', 'paper'))}.md"
        contributions = "\n".join(f"- {item}" for item in paper.get("main_contributions", [])) or "- (暂无)"
        text = f'''---
paper_id: "{paper.get('paper_id', '')}"
title: "{_yaml(paper.get('title'))}"
title_cn: "{_yaml(paper.get('title_cn'))}"
priority: "{priority}"
relevance_score: {paper.get('relevance_score', 0)}
related_project: "{_yaml(paper.get('related_project'))}"
reading_status: "{paper.get('reading_status', 'new')}"
doi: "{paper.get('doi_url', '')}"
---

# {paper.get('title_cn') or paper.get('title')}

## 推荐信息

- Priority: {priority}
- Relevance Score: {paper.get('relevance_score', 0)}/100
- Research Track: {paper.get('research_track', '')}
- Related Project: {paper.get('related_project', '')}
- Recommended Action: {paper.get('recommended_action', '')}

## 为什么值得读

{paper.get('why_relevant') or '(需人工判断)'}

## Research Question

{paper.get('research_question') or '(暂无)'}

## Method

{paper.get('method_summary') or '(暂无)'}

## Main Contributions

{contributions}

## Potential Use

{paper.get('potential_use') or '(暂无)'}

## Original Title

{paper.get('title', '')}

## Abstract EN

{paper.get('abstract') or '(No abstract)'}

## Abstract CN

{paper.get('abstract_cn') or '(暂无)'}

## 我的阅读笔记

- Rating (1-5):
- Reading status: new / saved / reading / read / ignored / cited
- Note:
'''
        path.write_text(text, encoding="utf-8")
    with (output_path / "_index.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["paper_id", "priority", "relevance_score", "related_project", "title", "doi_url"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for paper in papers:
            if paper.get("priority") != "Ignore":
                writer.writerow({key: paper.get(key, "") for key in fields})
    return output_path
