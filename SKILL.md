---
name: frontier-tracker
description: Use when the user asks to track, scan, or monitor new papers from their custom journal watchlist (46 journals, 8 research-topic pools: patent-tech-mining, bibliometrics-evaluation, science-policy-innovation, info-methods-datamining, ai-usage-behavior, complex-network-analysis, knowledge-graph-semantic, comprehensive-high-impact). Generates a bilingual (Chinese-English) HTML weekly report. Covers patent bibliometrics, scientometrics, tech mining, AI usage behavior, and science policy.
---

# Frontier Tracker · 前沿论文周报追踪

Personal literature surveillance for patent bibliometrics, scientometrics, tech mining, AI usage behavior, and science policy research. Scans 46 journals across 8 research-topic pools weekly, generates a bilingual Chinese-English HTML report with tiered relevance classification.

## Quick start

```bash
cd frontier-tracker-顶刊前沿论文追踪（结合自身修改）

# 首次使用：配置 DeepSeek API Key（国内直连，翻译质量最佳）
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY=sk-你的key

# Full pipeline: scan → enrich → screen → translate → all formats
python -X utf8 scripts/frontier_tracker.py --enrich --output-modes html app excel

# 30-day window (catches more papers from slow-publishing journals)
python -X utf8 scripts/frontier_tracker.py --days 30

# Skip translation (use existing translations)
python -X utf8 scripts/frontier_tracker.py --skip-translate

# Skip scan (use existing data, re-render with different formats)
python -X utf8 scripts/frontier_tracker.py --skip-scan --skip-screen \
  --screened-file outputs/data/frontier_screened_<date>.json \
  --output-modes app
```

**Always use `-X utf8` on Windows** to avoid GBK encoding errors.

## Pipeline steps

The unified script `frontier_tracker.py` runs three sequential steps in-process (no subprocess overhead):

1. **Scan** — CrossRef API, ISSN-based journal filtering, free, no API key needed
2. **Screen** — Keyword matching against `references/patent-biblio-profile.md` → core / proxy / eco / other
3. **[Optional] Enrich** — OpenAlex metadata backfill (abstracts + topic tags), `--enrich` flag
4. **Translate + Render** — DeepSeek API (primary) → Ollama local → Google Translate cascade → multi-format output

Legacy per-step scripts (`scan_crossref.py`, `screen_by_profile.py`, `render_bilingual_report.py`) are kept for debugging but should not be used directly for normal operation.

## Journal pools (46 journals, 8 pools)

| Pool | 中文名 | Count | Strategy |
|------|--------|-------|----------|
| `patent-tech-mining` | 专利计量与技术挖掘 | 4 | World Patent Information, TFSC, Technovation, TASM |
| `bibliometrics-evaluation` | 文献计量与科学评价 | 11 | Scientometrics, J. Informetrics, JASIST, QSS, Research Evaluation 等 |
| `science-policy-innovation` | 科技政策与创新管理 | 5 | Research Policy, SPP, GIQ, Industry & Innovation, JKM |
| `info-methods-datamining` | 信息方法与数据挖掘 | 5 | IP&M, JIS, J. Documentation, DIM, IJIM |
| `ai-usage-behavior` | AI使用行为 | 11 | CHB, AI & Society, MIS Quarterly, NMI 等 |
| `complex-network-analysis` | 复杂网络分析 | 3 | Social Networks, Applied Network Science, J. Complex Networks |
| `knowledge-graph-semantic` | 知识图谱与语义技术 | 2 | Semantic Web, J. Web Semantics |
| `comprehensive-high-impact` | 综合高影响力 | 5 | Nature, Science, PNAS, Nature Comms, Nature Human Behaviour |

综合高影响力和AI使用行为池使用严格筛选模式（提高匹配阈值，降低误检）。

Watchlist: `outputs/data/custom_watchlist.json`. Add/remove journals by editing this file — no code changes needed. Each entry needs: `journal`, `issn`, `pool`, `family`, `scope_note`.

## Research profile

`references/patent-biblio-profile.md` contains three keyword tiers:

- **Core keywords** (~70): AI usage behavior, patent analysis, bibliometrics, tech mining, complex networks, key/core/bottleneck technology identification
- **Proxy keywords** (~60): BERTopic, knowledge graph, causal inference, TAM/UTAUT, network analysis methods
- **Eco-context keywords** (~27): Science policy, open science, triple helix, research collaboration

Edit this file to update research interests. Format: bullet list (`- keyword`) under `## Core keywords` / `## Proxy keywords` / `## Eco-context keywords` headings. Multiple sub-fields separated by `# ── label ──` comment lines.

## Tier classification

| Tier | Meaning | Color in report | Action |
|------|---------|-----------------|--------|
| Core | Directly on-topic | Green left border | Must read |
| Proxy | Methods/adjacent | Yellow left border | Should skim |
| Eco | Broader context | Blue left border | Optional |
| Other | No keyword match / non-research | Hidden from report | Skip |

## Multi-format output

Default output is bilingual HTML. Use `--output-modes` to generate additional formats:

```bash
# All five formats
python -X utf8 scripts/frontier_tracker.py --output-modes html excel app notes codex

# Excel + interactive HTML only
python -X utf8 scripts/frontier_tracker.py --output-modes excel app
```

| Mode | Description | Output path |
|------|-------------|-------------|
| `html` | Bilingual HTML report (default) | `outputs/reports/frontier_weekly_bilingual_<date>.html` |
| `excel` | Multi-sheet Excel dashboard with conditional formatting | `outputs/excel/frontier_dashboard_<date>.xlsx` |
| `app` | Interactive searchable/sortable HTML table | `outputs/app/frontier_app_<date>/index.html` |
| `notes` | Per-paper Markdown notes with YAML frontmatter | `outputs/notes/<date>/<tier>/` |
| `codex` | Markdown preview table (also printed to stdout) | `outputs/codex/frontier_preview_<date>.md` |

Translation happens once regardless of how many output modes are selected.

### Bilingual HTML report features

- English title (linked to DOI) → Chinese title → journal / date / authors → Chinese abstract → English abstract
- Pool badges: 8 research-topic color-coded badges (专利技术挖掘, 文献计量与评价, 科技政策与创新, etc.)
- Stats bar: total scanned + per-tier counts + per-pool counts
- Translation quality: 63-term academic glossary with protect→translate→restore pipeline

## Translation

**Backend priority:** DeepSeek API → Ollama local → Google Translate

| Backend | Setup | Network | Quality |
|---------|-------|---------|---------|
| DeepSeek | Set `DEEPSEEK_API_KEY` in `.env` | 国内直连 | 最佳（中文模型） |
| Ollama | Install [Ollama](https://ollama.com) + `ollama pull qwen2.5:7b` | 离线 | 良好 |
| Google | None (auto-fallback) | 需代理 | 一般 |

Backend auto-detects and cascades on failure. Key academic terms (63 entries: bibliometric, patent analysis, technology convergence, etc.) are protected via marker-based substitution before translation and restored after.

### Configuration

Copy `.env.example` to `.env` and set your key:

```bash
cp .env.example .env
# Edit .env: DEEPSEEK_API_KEY=sk-your-key
```

`.env` is in `.gitignore` — never committed. All API keys are loaded from environment or `.env` file, never hardcoded.

## Metadata enrichment (`--enrich`)

Add `--enrich` to backfill missing abstracts and add topic tags via OpenAlex API (free, no key):

```bash
python -X utf8 scripts/frontier_tracker.py --enrich
```

Enrichment runs automatically before screening when enabled, improving keyword match accuracy by filling in abstracts that CrossRef lacks (~50% coverage). Topic tags (OpenAlex concept classification) are displayed in the bilingual report and interactive app.

## Operating rules

- Use exact dates. Report coverage window in results.
- Do not invent rankings or metrics. Use watchlist data or JCR sources.
- Watchlist is the single source of truth for journal configuration.
- Profile keywords control relevance — adjust there, not in code.
- If a journal has 0 papers this cycle, that's normal (especially for bi-monthly/quarterly journals).
- AI behavior papers are tracked separately from patent/biblio papers via pool labels — they do not mix.

## Adding journals

Edit `outputs/data/custom_watchlist.json`:
```json
{
  "journal": "Journal Name",
  "issn": "XXXX-XXXX",
  "family": "Parent/Family",
  "pool": "<one of 8 research-topic pools: patent-tech-mining, bibliometrics-evaluation, science-policy-innovation, info-methods-datamining, ai-usage-behavior, complex-network-analysis, knowledge-graph-semantic, comprehensive-high-impact>",
  "scope_note": "Brief note on why this journal is tracked.",
  "source": "custom-watchlist"
}
```
ISSN must match CrossRef registration exactly. Run pipeline after editing — no rebuild needed.

## Full documentation

See `frontier-tracker-使用教程.docx` for complete user guide with journal metrics table (JCR quartile, impact factor, CAS partition).

