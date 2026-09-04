---
name: research-frontier-agent
description: Discover and screen scholarly papers for personal Research Profiles and optional projects, generate bilingual research reports, and record reading feedback. Use for literature tracking, paper triage, and doctoral reading reports, not as a source of verified full-text findings.
---

# Research Frontier Agent

Use the repository pipeline to turn recent metadata into an auditable, personalized reading queue. Treat provider metadata and model judgments as evidence that still requires researcher verification.

## Locate and prepare the installation

Locate the project root containing this file, `config.example.json`, `scripts/`, and
`research_frontier_agent/`; run commands from that root. A copy of SKILL.md alone
is not a working installation. The repo-scoped entrypoint is
`.agents/skills/research-frontier-agent/SKILL.md`.

Use the project's `.venv` Python if available (Windows: `.venv/Scripts/python.exe`;
Linux/macOS: `.venv/bin/python`). Otherwise check Python 3.9+ and follow the
installation section in README.md. Create config.local.json from the example only
if it does not already exist; never overwrite an existing private configuration.
Never print configuration secrets. With no API credentials, keep the paid stages
disabled and report that judgments are keyword-only.

## Choose context

Select exactly one Profile for each run. Available profiles live in `references/profile-*.md` and may run independently on the same date because every intermediate and final path includes the profile name.

Optionally select one or more files under `references/projects/`. Read each selected Project Context before judging papers. Do not infer a project name that is not supplied.

## Run the pipeline

Prefer the single entrypoint:

```bash
python -X utf8 scripts/frontier_tracker.py --config config.local.json
```

Keep `--config config.local.json` when adding `--profile`, repeatable `--project`, `--days`, optional `--enrich`, `--embedding`, `--llm-judge`, and `--output-modes`.
Honor excluded_journals across providers and resumed scans. Report API errors and
fallbacks rather than treating an exit code of zero as proof that every source succeeded.
Do not create a schedule or publish reports unless the user asks for those actions.

The decision sequence is:

1. Discover real records through configured providers. CrossRef and Semantic Scholar Academic Graph are implemented; OpenAlex enriches DOI records. Respect Semantic Scholar's configured request interval and never expose its API key.
2. Upsert to `state/frontier.db`, using normalized DOI first and stable title hash otherwise.
3. Run keyword recall and retain `core_hits`, `proxy_hits`, `eco_hits`, and `matched_keywords`.
4. If enabled, compute semantic similarity through the configured `EmbeddingRanker`. A missing optional model must fall back to keyword-only screening.
5. If enabled, ask `ResearchJudge` for strict JSON. Reuse completed SQLite checkpoints; preserve raw and parsed responses; let a single-paper failure fall back without aborting the run.
6. Rank by research relevance. Capacity limits apply to the reading queue, Markdown notes and preview. HTML, Excel and App intentionally retain all classified candidates, including background papers, for filtering.
7. Translate independently from judgment, then generate the requested report, workbook, app, notes, and preview.

## Judgment rules

Use A only for work directly tied to the Profile or an active project, B for a transferable method, C for frontier awareness, D for background, and Ignore for no clear value. Explain which track and project match, what part of the project may use the paper, and whether the action is `deep-read`, `skim`, `save`, or `ignore`.

Never invent a research question, method, contribution, venue, DOI, ISSN, or API result. When the abstract is insufficient, say so in the structured field instead of filling gaps from assumptions.

## Feedback and long-term state

The interactive app stores edits locally and exports `feedback.json`. Import it with:

```bash
python -X utf8 scripts/import_feedback.py path/to/feedback.json
```

Use ratings and reading status as durable evidence for later Profile revision. Do not silently rewrite Profile keywords from one feedback item; summarize repeated patterns and propose bounded edits for researcher review.
There is no automatic interest-weight training or autonomous Profile update in this
beta. Feedback persistence is not equivalent to a trained personalization model.
arXiv has no independent provider yet; incidental Semantic Scholar arXiv records
do not imply complete preprint coverage.

## Configuration and safety

Copy `config.example.json` to ignored `config.local.json`. Pass API keys, bases, and model names through that file or explicit core-function arguments. Never add real keys to tracked files or depend on implicit environment variables in core logic.

Keep `LICENSE` and `THIRD_PARTY_NOTICES.md` when redistributing substantial portions. Do not write to or open changes against the upstream repository.
