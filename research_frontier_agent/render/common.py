from __future__ import annotations

from pathlib import Path

from ..utils import ROOT


POOL_LABELS = {
    "scholarly-text-mining": "学术文本挖掘",
    "scientific-knowledge-graph": "科学知识图谱",
    "llm-agent-methods": "LLM 与 Agent 方法",
    "scientometrics-evaluation": "科学计量与科研评价",
    "human-ai-interaction": "人机智能交互",
    "science-policy": "科学政策",
    "comprehensive-high-impact": "综合高影响力",
}

PRIORITY_LABELS = {
    "A": "A · Must Read",
    "B": "B · Method",
    "C": "C · Frontier",
    "D": "D · Background",
    "Ignore": "Ignore",
}


def output_paths(profile_name: str, date_tag: str, output_root: Path | None = None) -> dict[str, Path]:
    base = output_root or (ROOT / "outputs")
    return {
        "scan": base / "data" / f"frontier_scan_{profile_name}_{date_tag}.json",
        "screened": base / "data" / f"frontier_screened_{profile_name}_{date_tag}.json",
        "judged": base / "data" / f"frontier_judged_{profile_name}_{date_tag}.json",
        "html": base / "reports" / f"frontier_weekly_bilingual_{profile_name}_{date_tag}.html",
        "excel": base / "excel" / f"frontier_dashboard_{profile_name}_{date_tag}.xlsx",
        "app": base / "app" / f"frontier_app_{profile_name}_{date_tag}",
        "notes": base / "notes" / profile_name / date_tag,
        "codex": base / "codex" / f"frontier_preview_{profile_name}_{date_tag}.md",
    }
