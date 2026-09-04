# Beta validation record

Validation performed on 2026-09-04. No private configuration, research outputs or
API credentials are included in this record or the release archive.

## Local and clean installation

- PASS: 27 deterministic tests on the existing Python 3.9 environment.
- PASS: new isolated Python 3.12.14 venv (`include-system-site-packages = false`),
  installing only requirements.txt; `pip check` reports no broken requirements.
- PASS: 27 tests against a separate, exported source snapshot, not the working
  repository's imports; compilation and CLI/Skill entrypoint checks.
- PASS: both root and repo-scoped SKILL.md pass skill-creator quick_validate.
  This checks structure, not whether every client's Skill selector has refreshed.
- PASS: README's small CrossRef smoke command with a fresh, empty-key config
  writes HTML and SQLite without API credentials. One-day window returned zero
  records and zero errors. A 30-day window (2026-08-05 through 2026-09-04), limited
  to one record per venue in the scientific-knowledge-graph pool, returned four
  real records and zero errors; none passed the keyword screen. Do not interpret
  this small sample as a benchmark of research relevance or source completeness.
- PASS: public example keys are empty; release export excludes private config,
  databases, generated outputs and custom projects. Current files and reachable
  Git history pass the configured credential detector. Local config is unchanged.

## Issues encountered and resolved

- The local Windows Python launcher `py` was not available: README uses `python`.
- Local Anaconda Python 3.9/pip hit TLS EOF errors. Clean Python 3.12 installed
  dependencies from PyPI through the existing local proxy without disabling TLS
  verification. No system proxy settings were changed. CI also installs from scratch.
- Initial Windows/Python 3.12 CI exposed two test SQLite connections left open:
  use contextlib.closing so temporary database cleanup is deterministic.
- Escaped embedded JavaScript regex backslashes to remove Python 3.12 SyntaxWarnings.

## Reproduce

```text
python -m pip install -r requirements.txt
python -m pip check
python -X utf8 -m unittest discover -s tests -v
python -X utf8 -m compileall -q research_frontier_agent scripts tests
python -X utf8 scripts/check_skill.py
python -X utf8 scripts/build_release.py --check-only --history
```

The final command requires a Git clone, not just an extracted source ZIP.
See the CI run linked from the PR/Release for final Windows/Linux Python 3.9/3.12
results on the tagged commit. Paid LLM/embedding services and local BGE downloads
were not re-run as part of this empty-key installation test.
