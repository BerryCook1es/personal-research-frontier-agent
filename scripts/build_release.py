#!/usr/bin/env python3
"""Export only reviewed Git files; never copy the private working directory wholesale."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = {
    ".gitattributes", ".gitignore", "LICENSE", "README.md", "SKILL.md",
    "THIRD_PARTY_NOTICES.md", "requirements.txt", "config.example.json",
    "CHANGELOG.md", "SECURITY.md", "state/.gitkeep",
    "references/journal-watchlist.json", "references/conference-watchlist.json",
    "references/profile-scholarly-kg-llm.md", "references/profile-scientometrics-evaluation.md",
    "references/profile-human-ai-algorithm.md", "references/projects/project-template.md",
}
PUBLIC_DIRS = {"scripts", "tests", "research_frontier_agent", ".github", ".agents", "docs"}
TOKEN_PATTERN = re.compile(rb"\b(?:sk-|s2k-|ghp_|github_pat_)[A-Za-z0-9_-]{20,}")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE, timeout=60)


def allowed(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "__pycache__" in path.parts:
        return False
    return name in PUBLIC_FILES or (
        path.parts[0] in PUBLIC_DIRS and path.suffix in {".py", ".md", ".yml", ".yaml"}
    )


def local_secrets() -> list[bytes]:
    path = ROOT / "config.local.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [v.encode() for k, v in data.items() if "key" in k.lower() and isinstance(v, str) and v]


def check_content(name: str, data: bytes, secrets: list[bytes]) -> None:
    if TOKEN_PATTERN.search(data) or any(secret in data for secret in secrets):
        raise ValueError(f"Possible credential detected in {name}; value suppressed")
    if name == "config.example.json":
        config = json.loads(data)
        if any(value for key, value in config.items() if key.endswith("api_key")):
            raise ValueError("Public example API keys must be empty")


def collect(ref: str = "HEAD", history: bool = False) -> tuple[str, dict[str, bytes]]:
    sha = git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
    entries = git("ls-tree", "-rz", sha).split(b"\0")
    secrets = local_secrets()
    files = {}
    for entry in entries:
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        mode, kind, oid = meta.split()
        name = path.decode("utf-8")
        if mode not in {b"100644", b"100755"} or not allowed(name):
            raise ValueError(f"Unreviewed/private path in Git: {name}")
        data = git("cat-file", "blob", oid.decode())
        check_content(name, data, secrets)
        files[name] = data
    if history:
        # Inspect every reachable historical blob, not just the current checkout.
        for line in git("rev-list", "--objects", "--all").splitlines():
            parts = line.split(b" ", 1)
            if len(parts) != 2:
                continue
            oid, raw_name = parts
            if git("cat-file", "-t", oid.decode()).strip() != b"blob":
                continue
            name = raw_name.decode("utf-8", errors="replace")
            if PurePosixPath(name).name in {"config.local.json", ".env"}:
                raise ValueError("Private configuration exists in Git history")
            check_content(name, git("cat-file", "blob", oid.decode()), secrets)
    return sha, files


def export(ref: str, version: str) -> Path:
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", version):
        raise ValueError("Use a version such as v0.1.0-beta")
    sha, files = collect(ref)
    destination = ROOT / "release" / "github" / version
    archive = destination.with_suffix(destination.suffix + ".zip")
    manifest_path = destination.parent / (version + ".manifest.json")
    if destination.exists() or archive.exists() or manifest_path.exists():
        raise ValueError("Release destination already exists; choose a new version (no overwrite)")
    destination.mkdir(parents=True)
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {"version": version, "commit": sha, "files": {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
    }}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        for name, data in files.items():
            bundle.writestr("personal-research-frontier-agent/" + name, data)
    print(f"Exported {len(files)} public files from {sha} to {destination}")
    print(f"ZIP: {archive}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--version", default="v0.1.0-beta")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        sha, files = collect(args.ref, args.history)
        print(f"PASS: {len(files)} public files; credentials/path checks; commit {sha}")
    else:
        if args.history:
            collect(args.ref, True)
        export(args.ref, args.version)


if __name__ == "__main__":
    main()
