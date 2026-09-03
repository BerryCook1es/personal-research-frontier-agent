#!/usr/bin/env python3
"""Frontier Tracker — 单文件周报流水线：扫描 → [丰富] → 筛选 → 翻译 → 多格式输出。

Usage:
  python -X utf8 scripts/frontier_tracker.py                         # 默认 7 天，仅双语 HTML
  python -X utf8 scripts/frontier_tracker.py --days 30               # 30 天窗口
  python -X utf8 scripts/frontier_tracker.py --enrich                 # 启用 OpenAlex 元数据丰富
  python -X utf8 scripts/frontier_tracker.py --skip-translate         # 不翻译
  python -X utf8 scripts/frontier_tracker.py --output-modes html excel app notes codex  # 全格式
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from datetime import date
from pathlib import Path

from _lib import (
    POOL_LABELS, ROOT, TIER_LABELS, UI,
    fetch_journal_papers, load_profile_keywords, screen_papers, translate_papers,
)
from render_bilingual_report import render_bilingual_html
from render_outputs import render_app as _render_app
from render_outputs import render_codex as _render_codex
from render_outputs import render_excel as _render_excel
from render_outputs import render_notes as _render_notes
from enrich_papers import enrich_papers as _enrich_papers

# ══════════════════════════════════════════════════════════════
# 路径常量
# ══════════════════════════════════════════════════════════════

OUTPUTS_DATA = ROOT / "outputs" / "data"
OUTPUTS_REPORTS = ROOT / "outputs" / "reports"
WATCHLIST_FILE = OUTPUTS_DATA / "custom_watchlist.json"
PROFILE_FILE = ROOT / "references" / "patent-biblio-profile.md"
POOLS_STR = ("patent-tech-mining bibliometrics-evaluation science-policy-innovation "
             "info-methods-datamining ai-usage-behavior complex-network-analysis "
             "knowledge-graph-semantic comprehensive-high-impact")

AVAILABLE_MODES = ("html", "excel", "app", "notes", "codex")

# ══════════════════════════════════════════════════════════════
# 主流水线
# ══════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Frontier Tracker — 单文件周报流水线")
    parser.add_argument("--days", type=int, default=7, help="回溯天数（默认 7）")
    parser.add_argument("--from-date", type=str, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--to-date", type=str, default=date.today().isoformat(),
                        help="结束日期 YYYY-MM-DD")
    parser.add_argument("--pools", type=str, default=POOLS_STR,
                        help="追踪池（空格分隔）")
    parser.add_argument("--max-per-journal", type=int, default=50, help="每刊最多拉取论文数")
    parser.add_argument("--sleep", type=float, default=0.3, help="跨刊请求间隔（秒）")
    parser.add_argument("--profile", type=Path, default=PROFILE_FILE, help="Profile 文件路径")
    parser.add_argument("--skip-scan", action="store_true", help="跳过扫描，使用已有数据")
    parser.add_argument("--skip-screen", action="store_true", help="跳过筛选")
    parser.add_argument("--skip-translate", action="store_true", help="跳过翻译")
    parser.add_argument("--enrich", action="store_true", help="OpenAlex 回填缺失摘要 + 补充主题标签")
    parser.add_argument("--scan-file", type=Path, help="已有扫描数据文件（配合 --skip-scan）")
    parser.add_argument("--screened-file", type=Path, help="已有筛选数据文件（配合 --skip-screen）")
    parser.add_argument("--output-modes", type=str, default="",
                        help=f"输出格式（空格分隔）：{' '.join(AVAILABLE_MODES)}；留空则交互选择")
    args = parser.parse_args()

    # ── 解析日期 ──
    try:
        to_date_dt = date.fromisoformat(args.to_date)
    except ValueError:
        print(f"[ERROR] Invalid --to-date format: {args.to_date} (use YYYY-MM-DD)", file=sys.stderr)
        return 1
    to_date = args.to_date
    if args.from_date:
        try:
            from_date_dt = date.fromisoformat(args.from_date)
        except ValueError:
            print(f"[ERROR] Invalid --from-date format: {args.from_date} (use YYYY-MM-DD)", file=sys.stderr)
            return 1
        if from_date_dt > to_date_dt:
            print(f"[ERROR] --from-date ({args.from_date}) 不能晚于 --to-date ({args.to_date})", file=sys.stderr)
            return 1
        from_date = args.from_date
    else:
        from_date = (to_date_dt - dt.timedelta(days=args.days)).isoformat()
    date_tag = to_date

    OUTPUTS_DATA.mkdir(parents=True, exist_ok=True)
    OUTPUTS_REPORTS.mkdir(parents=True, exist_ok=True)

    scan_file = args.scan_file or (OUTPUTS_DATA / f"frontier_scan_{date_tag}.json")
    screened_file = args.screened_file or (OUTPUTS_DATA / f"frontier_screened_{date_tag}.json")

    # ── Step 1: 扫描 ──
    if not args.skip_scan:
        print(f"\n{'='*60}\n>>> Step 1/3: CrossRef 期刊扫描\n{'='*60}")
        print(f"Date range: {from_date} → {to_date}")

        if not WATCHLIST_FILE.exists():
            print(f"\n[ERROR] Watchlist file not found: {WATCHLIST_FILE}", file=sys.stderr)
            return 1
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                watchlist = json.load(f)
        except json.JSONDecodeError as e:
            print(f"\n[ERROR] Watchlist file is invalid JSON: {e}", file=sys.stderr)
            return 1

        allowed = set(args.pools.split())
        jobs = [
            {"journal": e["journal"], "issn": e["issn"], "pool": e["pool"]}
            for e in watchlist
            if e.get("issn", "") and e.get("pool", "") in allowed
        ]

        all_papers = []
        errors = []
        nj = len(jobs)
        print(f"Scanning {nj} journals...\n")

        for i, jinfo in enumerate(jobs):
            jname, issn, pool = jinfo["journal"], jinfo["issn"], jinfo["pool"]
            print(f"[{i+1}/{nj}] {jname} ...", end=" ", flush=True)
            try:
                papers = fetch_journal_papers(jname, issn, from_date, to_date, pool,
                                              max_results=args.max_per_journal)
                all_papers.extend(papers)
                print(f"{len(papers)} papers")
            except Exception as e:
                print(f"ERROR: {e}")
                errors.append({"journal": jname, "pool": pool, "error": str(e)})
            if i < nj - 1:
                time.sleep(args.sleep)

        # DOI 去重
        seen = set()
        unique = []
        for p in all_papers:
            d = p.get("doi_raw", "")
            if d and d in seen:
                continue
            if d:
                seen.add(d)
            unique.append(p)

        print(f"\nTotal: {len(unique)} unique papers from {nj} journals")
        if errors:
            print(f"Errors: {len(errors)} journals")

        scan_data = {
            "coverage": {"from": from_date, "to": to_date},
            "watchlist_journals": nj,
            "pools": sorted(set(j["pool"] for j in jobs)),
            "new": unique,
            "already_seen": [],
            "needs_manual_verification": [],
            "excluded_non_research": [],
            "source_errors": errors,
            "data_source": "crossref",
        }
        scan_file.parent.mkdir(parents=True, exist_ok=True)
        scan_file.write_text(json.dumps(scan_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {scan_file}")
    else:
        # 同时跳过扫描和筛选时，直接从 screened_file 读取，不需要 scan_file
        if args.skip_screen:
            if not screened_file.exists():
                print(f"\n[ERROR] Screened file not found: {screened_file}", file=sys.stderr)
                return 1
            print(f"\n[SKIP] Step 1+2: Using existing screened file: {screened_file}")
            scan_data = json.loads(screened_file.read_text(encoding="utf-8"))
        else:
            if not scan_file.exists():
                print(f"\n[ERROR] Scan file not found: {scan_file}", file=sys.stderr)
                return 1
            print(f"\n[SKIP] Step 1/3: Using existing scan file: {scan_file}")
            scan_data = json.loads(scan_file.read_text(encoding="utf-8"))

    # ── Step 2: 筛选 ──
    if not args.skip_screen:
        # 先丰富元数据（回填摘要有助于关键词匹配），再筛选
        if args.enrich:
            print(f"\n{'='*60}\n>>> Step 1.5/3: OpenAlex 元数据丰富")
            for field in ["new", "already_seen"]:
                papers = scan_data.get(field, [])
                if papers:
                    scan_data[field] = _enrich_papers(papers)

        print(f"\n{'='*60}\n>>> Step 2/3: Profile 关键词筛选\n{'='*60}")
        core_kw, proxy_kw, eco_kw = load_profile_keywords(args.profile)
        print(f"Profile: core={len(core_kw)} proxy={len(proxy_kw)} eco={len(eco_kw)} keywords")

        stats = {"total": 0, "core": 0, "proxy": 0, "eco": 0, "other": 0}
        for field in ["new", "already_seen"]:
            papers = scan_data.get(field, [])
            if not papers:
                continue
            scored = screen_papers(papers, core_kw, proxy_kw, eco_kw)
            scan_data[field] = scored
            for p in scored:
                stats["total"] += 1
                stats[p["tier"]] = stats.get(p["tier"], 0) + 1

        scan_data["_screened"] = True
        scan_data["_profile_stats"] = stats
        print(f"Total: {stats['total']} | core={stats['core']} proxy={stats['proxy']} "
              f"eco={stats['eco']} other={stats['other']}")

        screened_file.parent.mkdir(parents=True, exist_ok=True)
        screened_file.write_text(
            json.dumps(scan_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {screened_file}")
    else:
        # 如果 scan 步骤已直接从 screened_file 加载，跳过重复加载
        if not args.skip_scan:
            if not screened_file.exists():
                print(f"\n[ERROR] Screened file not found: {screened_file}", file=sys.stderr)
                return 1
            print(f"\n[SKIP] Step 2/3: Using existing screened file: {screened_file}")
            scan_data = json.loads(screened_file.read_text(encoding="utf-8"))
        else:
            print(f"\n[SKIP] Step 2/3: Screened data already loaded (via scan step)")

        # 丰富已筛选数据（回填摘要 + 主题标签）
        if args.enrich:
            print(f"\n{'='*60}\n>>> Step 2.5/3: OpenAlex 元数据丰富（已筛选数据）")
            for field in ["new", "already_seen"]:
                papers = scan_data.get(field, [])
                if papers:
                    scan_data[field] = _enrich_papers(papers)
            scan_data["_enriched"] = True
            screened_file.write_text(
                json.dumps(scan_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Updated: {screened_file}")

    # ── Step 3: 翻译 + 多格式输出 ──
    if args.output_modes.strip():
        modes = set(args.output_modes.split())
    else:
        # 交互式选择输出格式
        print(f"\n{'='*60}\n>>> 选择输出格式")
        print(f"\n可选格式（输入编号多选，空格分隔，回车=全部）：")
        labels = {
            "html": "HTML 双语报告（中英对照，按 tier 分段）",
            "excel": "Excel 仪表盘（多 sheet，条件格式，DOI 超链接）",
            "app": "交互 HTML 表格（可搜索、筛选、排序）",
            "notes": "Markdown 笔记（每篇论文一个 .md，按 tier 分目录）",
            "codex": "终端预览（Markdown 表格，按 tier 分组）",
        }
        for i, mode in enumerate(AVAILABLE_MODES, 1):
            print(f"  [{i}] {mode:<6} — {labels[mode]}")
        try:
            choice = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""
        if not choice:
            modes = set(AVAILABLE_MODES)
        else:
            idx_map = {str(i): m for i, m in enumerate(AVAILABLE_MODES, 1)}
            modes = set()
            for token in choice.split():
                if token in idx_map:
                    modes.add(idx_map[token])
                elif token in AVAILABLE_MODES:
                    modes.add(token)
        if not modes:
            print("未选择任何格式，默认输出 html", file=sys.stderr)
            modes = {"html"}

    invalid = modes - set(AVAILABLE_MODES)
    if invalid:
        print(f"[WARNING] Unknown output modes ignored: {invalid}", file=sys.stderr)
        modes &= set(AVAILABLE_MODES)
    if not modes:
        print("未选择任何有效输出格式，默认输出 html", file=sys.stderr)
        modes = {"html"}

    papers = scan_data.get("new", []) + scan_data.get("already_seen", [])
    stats = scan_data.get("_profile_stats", {})
    profile_name = args.profile.stem if args.profile else "patent-biblio-profile"

    # 翻译：所有输出模式都需要中文翻译
    need_translate = not args.skip_translate and bool(modes)
    if args.skip_translate and bool(modes):
        # 检查数据是否已有翻译，有则可以继续生成 HTML
        has_translations = any(p.get("title_cn") for p in papers if p.get("tier") != "other")
        if has_translations:
            print("\n[INFO] --skip-translate but papers have existing translations, output will proceed",
                  file=sys.stderr)
        else:
            print("\n[WARNING] --skip-translate but no translations found in data. "
                  "Chinese content will be missing.",
                  "\n         建议移除 --skip-translate 以生成中文翻译。",
                  file=sys.stderr)

    if need_translate:
        print(f"\n{'='*60}\n>>> Step 3/3: 翻译 + 多格式输出\n{'='*60}")
        other_count = stats.get("other", 0)
        print(f"Translating {len(papers)} papers (titles only for {other_count} other)...")
        output_papers = translate_papers(papers)
        # 翻译结果持久化：new + already_seen 合并翻译后全部写入 new
        scan_data["new"] = output_papers
        scan_data["already_seen"] = []
        scan_data["_translated"] = True
        screened_file.write_text(
            json.dumps(scan_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Translations saved to: {screened_file}", file=sys.stderr)
    elif modes:
        output_papers = papers  # 不需要翻译，直接使用原始数据
        print(f"\n[SKIP] Translation skipped. Generating: {modes}")
    else:
        print(f"\n[SKIP] Step 3/3: No output modes selected")
        output_papers = None

    # ── 生成各格式输出 ──
    if output_papers and modes:
        title = f"{UI['title']} · {date_tag}"
        render_data = dict(scan_data)
        render_data["new"] = output_papers

        if "html" in modes:
            report_file = OUTPUTS_REPORTS / f"frontier_weekly_bilingual_{date_tag}.html"
            print(f"\n--- HTML 双语报告 ---")
            render_bilingual_html(render_data, title, profile_name, report_file, to_date)

        if "excel" in modes:
            print(f"\n--- Excel 仪表盘 ---")
            excel_path = ROOT / "outputs" / "excel" / f"frontier_dashboard_{date_tag}.xlsx"
            _render_excel(output_papers, stats, output_path=excel_path)

        if "app" in modes:
            print(f"\n--- 交互 HTML 表格 ---")
            app_path = ROOT / "outputs" / "app" / f"frontier_app_{date_tag}"
            _render_app(output_papers, stats, output_path=app_path, ref_date=to_date, from_date=from_date)

        if "notes" in modes:
            print(f"\n--- Markdown 笔记 ---")
            notes_path = ROOT / "outputs" / "notes" / date_tag
            _render_notes(output_papers, stats, output_path=notes_path)

        if "codex" in modes:
            print(f"\n--- 终端预览 ---")
            codex_path = ROOT / "outputs" / "codex" / f"frontier_preview_{date_tag}.md"
            _render_codex(output_papers, stats, output_path=codex_path)

    # ── Summary ──
    print(f"\n{'='*60}\n>>> Pipeline complete!")
    print(f"    Scan      : {scan_file}")
    print(f"    Screened  : {screened_file}")
    if "html" in modes:
        print(f"    Report    : {OUTPUTS_REPORTS / f'frontier_weekly_bilingual_{date_tag}.html'}")
    if "excel" in modes:
        print(f"    Excel     : {ROOT / 'outputs' / 'excel' / f'frontier_dashboard_{date_tag}.xlsx'}")
    if "app" in modes:
        print(f"    App       : {ROOT / 'outputs' / 'app' / f'frontier_app_{date_tag}'}")
    if "notes" in modes:
        print(f"    Notes     : {ROOT / 'outputs' / 'notes' / date_tag}")
    if "codex" in modes:
        print(f"    Codex     : {ROOT / 'outputs' / 'codex' / f'frontier_preview_{date_tag}.md'}")
    print(f"    Results   : {stats.get('total', '?')} scanned → "
          f"Core={stats.get('core', '?')} "
          f"Proxy={stats.get('proxy', '?')} "
          f"Eco={stats.get('eco', '?')} "
          f"Other={stats.get('other', '?')}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

