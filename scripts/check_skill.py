"""Dependency-free checks for the repository skill's metadata and linked runtime."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check_skill(root: Path = ROOT) -> None:
    entry = root / ".agents/skills/research-frontier-agent/SKILL.md"
    for path in (entry, root / "SKILL.md"):
        text = path.read_text(encoding="utf-8")
        front = re.match(r"\A---\r?\n(.*?)\r?\n---", text, re.S)
        if not front or not re.search(r"(?m)^name: research-frontier-agent$", front[1]):
            raise ValueError(f"Invalid skill name/frontmatter: {path.name}")
        if not re.search(r"(?m)^description: .+", front[1]):
            raise ValueError("Skill description missing")
    for relative in ("../../../SKILL.md", "../../../scripts/frontier_tracker.py", "../../../config.example.json"):
        if not (entry.parent / relative).resolve().is_file():
            raise ValueError("Incomplete Skill installation: full repository required")
    print("PASS: Skill metadata, workflow link and runtime entrypoint")


if __name__ == "__main__":
    check_skill()
