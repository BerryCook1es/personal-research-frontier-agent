from __future__ import annotations

import json
import re
from typing import Any

from ..profile import ProjectContext, ResearchProfile
from ..utils import normalize_openai_api_base, openai_api_endpoint, request_json


REQUIRED_FIELDS: dict[str, Any] = {
    "relevance_score": 0,
    "research_track": "",
    "priority": "Ignore",
    "matched_topics": [],
    "research_question": "",
    "method_summary": "",
    "main_contributions": [],
    "why_relevant": "",
    "methodological_value": "",
    "potential_use": "",
    "related_project": "",
    "recommended_action": "ignore",
}
VALID_PRIORITIES = {"A", "B", "C", "D", "Ignore"}
VALID_ACTIONS = {"deep-read", "skim", "save", "ignore"}
PRIORITY_SCORE_RANGES = {
    "A": (85, 100),
    "B": (65, 84),
    "C": (45, 64),
    "D": (25, 44),
    "Ignore": (0, 24),
}
JUDGE_SCHEMA_VERSION = "2026-09-v2"


class ResearchJudge:
    cache_version = JUDGE_SCHEMA_VERSION

    def __init__(self, *, model: str, api_base: str, api_key: str,
                 temperature: float = 0.1, timeout: float = 60.0, retries: int = 3):
        if not model or not api_base or not api_key:
            raise ValueError("llm_model, api_base and api_key are required when LLM Judge is enabled")
        self.model = model
        self.api_base = normalize_openai_api_base(api_base)
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        self.retries = retries

    def _prompt(self, profile: ResearchProfile, paper: dict[str, Any], projects: list[ProjectContext]) -> str:
        projects_text = "\n\n".join(project.to_prompt() for project in projects) or "No active project supplied."
        return f"""Act as a rigorous research judge for a doctoral student. Return JSON only.

Priority rubric: A=must read/directly relevant; B=transferable method; C=frontier awareness; D=background; Ignore=no clear value.
Score bands are mandatory: A=85-100, B=65-84, C=45-64, D=25-44, Ignore=0-24.
recommended_action must be deep-read, skim, save, or ignore.
When a project matches, potential_use should name Related Work, Method, Experiment, Discussion, New Idea, or a concrete problem it may solve.
If no active project is supplied, related_project must be an empty string. Never invent a project.

Research profile:
{profile.description}

Active projects:
{projects_text}

Paper:
Title: {paper.get('title', '')}
Abstract: {paper.get('abstract', '')}
Venue: {paper.get('venue') or paper.get('journal', '')}
Matched keywords: {paper.get('matched_keywords', [])}
Keyword tier: {paper.get('keyword_tier', '')}
Semantic score: {paper.get('semantic_score', '')}

Required JSON schema:
{json.dumps(REQUIRED_FIELDS, ensure_ascii=False)}"""

    @staticmethod
    def parse_response(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("No JSON object in response")
        parsed = json.loads(text[start:end + 1])
        result = {**REQUIRED_FIELDS, **parsed}
        result["relevance_score"] = max(0, min(100, int(result["relevance_score"])))
        if result["priority"] not in VALID_PRIORITIES:
            raise ValueError("Invalid priority")
        minimum, maximum = PRIORITY_SCORE_RANGES[result["priority"]]
        if not minimum <= result["relevance_score"] <= maximum:
            raise ValueError(f"relevance_score is inconsistent with priority {result['priority']}")
        if result["recommended_action"] not in VALID_ACTIONS:
            raise ValueError("Invalid recommended_action")
        for list_field in ("matched_topics", "main_contributions"):
            if not isinstance(result[list_field], list):
                raise ValueError(f"{list_field} must be a list")
        return result

    def judge(self, profile: ResearchProfile, paper: dict[str, Any], projects: list[ProjectContext]) -> tuple[str, dict[str, Any]]:
        prompt = self._prompt(profile, paper, projects)
        last_error: Exception | None = None
        raw = ""
        for _ in range(self.retries):
            try:
                response = request_json(
                    openai_api_endpoint(self.api_base, "chat/completions"),
                    method="POST",
                    payload={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "Return one valid JSON object and no prose."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": self.temperature,
                        "response_format": {"type": "json_object"},
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.timeout,
                    retries=1,
                )
                raw = response["choices"][0]["message"]["content"]
                parsed = self.parse_response(raw)
                if not projects:
                    parsed["related_project"] = ""
                return raw, parsed
            except Exception as exc:
                last_error = exc
                prompt += "\nYour previous response was invalid. Return a complete JSON object matching the schema exactly."
        raise RuntimeError(f"LLM Judge failed after {self.retries} attempts: {last_error}; last_response={raw[:500]}")


def fallback_judgment(paper: dict[str, Any]) -> dict[str, Any]:
    tier = paper.get("keyword_tier", "other")
    priority = {"core": "A", "proxy": "B", "eco": "C"}.get(tier, "Ignore")
    score = {"core": 85, "proxy": 65, "eco": 45}.get(tier, 0)
    return {
        **REQUIRED_FIELDS,
        "relevance_score": score,
        "priority": priority,
        "research_track": tier,
        "matched_topics": paper.get("matched_keywords", []),
        "why_relevant": "Keyword recall only; enable LLM Judge for a research rationale." if tier != "other" else "",
        "recommended_action": {"A": "deep-read", "B": "skim", "C": "save"}.get(priority, "ignore"),
    }
