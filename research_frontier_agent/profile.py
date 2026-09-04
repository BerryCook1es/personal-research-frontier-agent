from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .utils import slugify


@dataclass
class ResearchProfile:
    name: str
    path: Path
    description: str
    core_keywords: list[str] = field(default_factory=list)
    proxy_keywords: list[str] = field(default_factory=list)
    eco_keywords: list[str] = field(default_factory=list)
    weekly_reading_capacity: int = 25
    max_a: int = 5
    max_b: int = 10
    max_c: int = 10


@dataclass
class ProjectContext:
    name: str
    path: Path
    research_question: str = ""
    current_method: str = ""
    current_problems: str = ""
    keywords: list[str] = field(default_factory=list)
    need_to_track: str = ""

    def to_prompt(self) -> str:
        return (
            f"Project: {self.name}\nResearch Question: {self.research_question}\n"
            f"Current Method: {self.current_method}\nCurrent Problems: {self.current_problems}\n"
            f"Keywords: {', '.join(self.keywords)}\nNeed to Track: {self.need_to_track}"
        )


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ims)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)", text
    )
    return match.group(1).strip() if match else ""


def _bullets(text: str) -> list[str]:
    return [m.strip() for m in re.findall(r"(?m)^\s*[-*]\s+(.+?)\s*$", text)]


def _metadata(text: str, label: str, default: str = "") -> str:
    match = re.search(rf"(?im)^-\s*\*\*{re.escape(label)}:\*\*\s*(.+?)\s*$", text)
    return match.group(1).strip() if match else default


def load_profile(path: Path) -> ResearchProfile:
    text = path.read_text(encoding="utf-8")
    name = _metadata(text, "Profile name", slugify(path.stem.removeprefix("profile-")))
    description = _section(text, "Research Description")
    if not description:
        description = re.sub(r"(?s)^#.*?\n", "", text).split("##", 1)[0].strip()
    cap = int(_metadata(text, "Weekly reading capacity", "25").split()[0])
    return ResearchProfile(
        name=slugify(name),
        path=path,
        description=description,
        core_keywords=_bullets(_section(text, "Core keywords")),
        proxy_keywords=_bullets(_section(text, "Proxy keywords")),
        eco_keywords=_bullets(_section(text, "Eco-context keywords")),
        weekly_reading_capacity=cap,
        max_a=int(_metadata(text, "Max A", "5")),
        max_b=int(_metadata(text, "Max B", "10")),
        max_c=int(_metadata(text, "Max C", "10")),
    )


def load_project(path: Path) -> ProjectContext:
    text = path.read_text(encoding="utf-8")
    title = re.search(r"(?m)^#\s+(.+)$", text)
    return ProjectContext(
        name=title.group(1).strip() if title else path.stem,
        path=path,
        research_question=_section(text, "Research Question"),
        current_method=_section(text, "Current Method"),
        current_problems=_section(text, "Current Problems"),
        keywords=_bullets(_section(text, "Keywords")),
        need_to_track=_section(text, "Need to Track"),
    )
