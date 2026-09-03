#!/usr/bin/env python3
"""Render a bilingual (Chinese-English) weekly frontier report from screened data.

Usage:
  python -X utf8 scripts/render_bilingual_report.py \
    --input outputs/data/frontier_screened_<date>.json \
    --output outputs/reports/frontier_weekly_bilingual_<date>.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

from _lib import POOL_LABELS, TIER_LABELS, UI, translate_papers


def render_bilingual_html(
    data: dict,
    title: str,
    profile_name: str,
    output_path: Path,
    to_date: str = "",
) -> None:
    """Render a bilingual HTML report with Chinese translations."""
    stats = data.get("_profile_stats", {})
    today = date.today().isoformat()
    ref_date = to_date or today  # 日期过滤器参考日期（扫描截止日）

    papers = data.get("new", []) + data.get("already_seen", [])

    # 已有翻译的跳过，避免重复翻译
    non_other = [p for p in papers if p.get("tier") != "other"]
    already_translated = any(p.get("title_cn") for p in non_other)
    if already_translated:
        print(f"Papers already translated, skipping translation step.", file=sys.stderr)
        all_papers = papers
    else:
        print(f"Translating {len(papers)} papers (other tier: titles only)...", file=sys.stderr)
        all_papers = translate_papers(papers)

    # 池统计
    pool_counts: dict[str, int] = {}
    for p in all_papers:
        pool = p.get("pool", "")
        if pool and p.get("tier") != "other":
            pool_counts[pool] = pool_counts.get(pool, 0) + 1

    core_p = [p for p in all_papers if p.get("tier") == "core"]
    proxy_p = [p for p in all_papers if p.get("tier") == "proxy"]
    eco_p = [p for p in all_papers if p.get("tier") == "eco"]

    def render_paper(p: dict) -> str:
        t_en = html.escape(p.get("title", "Untitled"))
        t_cn = html.escape(p.get("title_cn", ""))
        journal = html.escape(p.get("journal", "") or p.get("journal_source", ""))
        authors = html.escape(p.get("authors", ""))
        pub_date = html.escape(p.get("publication_date", ""))
        doi = p.get("doi_url", "") or f"https://doi.org/{p.get('doi', '')}"
        abstract_en = (p.get("abstract") or "").strip()
        abstract_cn = (p.get("abstract_cn") or "").strip()
        tier = p.get("tier", "eco")

        tier_label = TIER_LABELS.get(tier, tier)
        badge_class = f"badge-{tier}"

        pool = p.get("pool", "")
        pool_label = POOL_LABELS.get(pool, "")
        pool_badge_html = ""
        if pool_label:
            pool_badge_html = (
                f' <span class="badge badge-pool badge-pool-{pool}">{pool_label}</span>'
            )

        title_html = (
            f'<div class="paper-title-en">'
            f'<a href="{html.escape(doi)}" target="_blank">{t_en}</a>'
            f' <span class="badge {badge_class}">{tier_label}</span>'
            f'{pool_badge_html}'
            f'</div>'
        )
        if t_cn:
            title_html += f'<div class="paper-title-cn">{t_cn}</div>'

        abstract_html = ""
        if abstract_en:
            abstract_html += f'<div class="paper-abstract-en">{html.escape(abstract_en)}</div>'
        elif tier == "other":
            abstract_html += (
                f'<div class="paper-abstract-en no-abstract">'
                f'非研究文章，无摘要 / Non-research article, no abstract</div>'
            )
        else:
            abstract_html += (
                f'<div class="paper-abstract-en no-abstract">'
                f'摘要未收录（CrossRef / OpenAlex 均缺失）/ '
                f'Abstract not available from CrossRef or OpenAlex</div>'
            )
        if abstract_cn:
            abstract_html += f'<div class="paper-abstract-cn">{html.escape(abstract_cn)}</div>'

        # 主题标签（英文在上，中文在下，逐对对齐）
        topic_html = ""
        primary_topic = p.get("primary_topic", "")
        primary_topic_cn = p.get("primary_topic_cn", "")
        all_topics = p.get("all_topics", [])
        all_topics_cn = p.get("all_topics_cn", [])
        if all_topics:
            cn_map = dict(zip(all_topics, all_topics_cn)) if all_topics_cn else {}
            pairs = []
            if primary_topic:
                pairs.append((primary_topic, primary_topic_cn or cn_map.get(primary_topic, "")))
            for t in all_topics:
                if t != primary_topic and len(pairs) < 4:
                    pairs.append((t, cn_map.get(t, "")))
            badges = "".join(
                f'<span class="topic-pair">'
                f'<span class="badge badge-topic">{html.escape(en)}</span>'
                f'<span class="badge badge-topic-cn">{html.escape(cn)}</span>'
                f'</span>'
                for en, cn in pairs
            )
            topic_html = f'<div class="paper-topics">{badges}</div>'

        abstract_source = p.get("abstract_source", "")
        source_note = ""
        if abstract_source == "openalex":
            source_note = ' <span class="abstract-source">[摘要来自 OpenAlex]</span>'

        return (
            f'<div class="paper-card tier-{tier}" data-date="{html.escape(pub_date)}">'
            f'{title_html}'
            f'<div class="paper-meta">'
            f'<span class="meta-label">{UI["journal"]}：</span>{journal} · {pub_date} · '
            f'<span class="meta-label">{UI["authors"]}：</span>{authors}'
            f'{source_note}'
            f'</div>'
            f'{topic_html}'
            f'{abstract_html}'
            f'</div>'
        ).replace("{", "&#123;").replace("}", "&#125;")  # 防 f-string 注入


    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{
  font-family: -apple-system, "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
  max-width: 1100px; margin: 0 auto; padding: 20px;
  background: #f8f9fa; color: #2c3e50;
}}
h1 {{ color: #1a5276; border-bottom: 3px solid #2980b9; padding-bottom: 8px; font-size: 1.8em; }}
h2 {{ color: #2c3e50; margin-top: 30px; padding: 8px 0; border-bottom: 1px solid #ddd; }}
.stats {{ background: #eaf2f8; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
.stats-row {{ display: flex; flex-wrap: wrap; gap: 15px; align-items: center; }}
.stats-row span {{ font-weight: bold; font-size: 1.05em; }}
.stats-pools {{ margin-top: 10px; padding-top: 10px; border-top: 1px dashed #bdc3c7; }}
.stats-pools .badge {{ font-size: 0.85em; padding: 3px 10px; }}
.paper-card {{ padding: 14px 16px; margin: 10px 0; border-radius: 6px; }}
.tier-core {{ background: #e8f8f5; border-left: 4px solid #27ae60; }}
.tier-proxy {{ background: #fef9e7; border-left: 4px solid #f39c12; }}
.tier-eco {{ background: #ebf5fb; border-left: 4px solid #2980b9; }}
.paper-title-cn {{ font-weight: bold; font-size: 1.1em; color: #1a5276; margin-bottom: 2px; }}
.paper-title-en {{ font-weight: bold; font-size: 1.0em; color: #555; margin-bottom: 6px; }}
.paper-meta {{ color: #777; font-size: 0.88em; margin-bottom: 8px; line-height: 1.5; }}
.meta-label {{ color: #999; }}
.paper-abstract-cn {{ color: #2c3e50; font-size: 0.92em; margin-top: 6px; margin-bottom: 4px; line-height: 1.65; padding-left: 8px; border-left: 2px solid #bdc3c7; }}
.paper-abstract-en {{ color: #666; font-size: 0.88em; line-height: 1.6; margin-top: 4px; padding-left: 8px; border-left: 2px solid #ecf0f1; }}
.no-abstract {{ color: #bbb; font-style: italic; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.78em; margin-left: 6px; font-weight: normal; }}
.badge-core {{ background: #27ae60; color: white; }}
.badge-proxy {{ background: #f39c12; color: white; }}
.badge-eco {{ background: #2980b9; color: white; }}
.badge-pool {{ font-size: 0.72em; border: 1px solid #ddd; background: white; }}
.badge-topic {{ font-size: 0.72em; background: #e8f0fe; color: #1a5276; border: 1px solid #bdd7ee; margin: 2px 4px 0 0; }}
.badge-topic-cn {{ font-size: 0.70em; background: #fef9e7; color: #7d6608; border: 1px solid #f9e79f; margin: 2px 4px 0 0; }}
.badge-pool-patent-tech-mining {{ color: #d35400; border-color: #d35400; }}
.badge-pool-bibliometrics-evaluation {{ color: #2471a3; border-color: #2471a3; }}
.badge-pool-science-policy-innovation {{ color: #1abc9c; border-color: #1abc9c; }}
.badge-pool-info-methods-datamining {{ color: #8e44ad; border-color: #8e44ad; }}
.badge-pool-ai-usage-behavior {{ color: #c0392b; border-color: #c0392b; }}
.badge-pool-complex-network-analysis {{ color: #1e8449; border-color: #1e8449; }}
.badge-pool-knowledge-graph-semantic {{ color: #6c3483; border-color: #6c3483; }}
.badge-pool-comprehensive-high-impact {{ color: #d4a017; border-color: #d4a017; }}
a {{ color: #2980b9; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.paper-topics {{ margin-bottom: 6px; }}
.topic-pair {{ display: inline-flex; flex-direction: column; align-items: center; margin: 2px 6px 0 0; vertical-align: top; }}
.abstract-source {{ color: #999; font-size: 0.8em; }}
.date-filter {{ text-align: center; margin: 12px 0 20px 0; }}
.date-filter-label {{ color: #666; font-size: 0.9em; margin-right: 6px; }}
.date-btn {{ padding: 4px 14px; margin: 0 4px; border: 1px solid #bdc3c7; border-radius: 15px; background: white; color: #555; cursor: pointer; font-size: 0.88em; }}
.date-btn.active {{ background: #2980b9; color: white; border-color: #2980b9; }}
.date-btn:hover {{ border-color: #2980b9; }}
.paper-card.hidden {{ display: none; }}
.section-count {{ color: #2980b9; }}
.footer {{ color: #999; margin-top: 40px; font-size: 0.85em; text-align: center; border-top: 1px solid #ddd; padding-top: 15px; }}
</style>
</head>
<body>

<h1>{html.escape(title)}</h1>

<div class="stats">
  <div class="stats-row">
    <span>{UI["stats_scanned"]}：{stats.get("total", "?")}</span>
    <span>{UI["stats_core"]}：{stats.get("core", "?")}</span>
    <span>{UI["stats_proxy"]}：{stats.get("proxy", "?")}</span>
    <span>{UI["stats_eco"]}：{stats.get("eco", "?")}</span>
  </div>
  <div class="stats-row stats-pools">
    {"".join(f'<span class="badge badge-pool badge-pool-{pool}">{POOL_LABELS.get(pool, pool)}：{count}</span>' for pool, count in sorted(pool_counts.items(), key=lambda x: -x[1]))}
  </div>
</div>

  <div class="date-filter">
    <span class="date-filter-label">时间范围：</span>
    <button class="date-btn active" data-days="7" onclick="filterByDays(7,this)">近 7 天</button>
    <button class="date-btn" data-days="30" onclick="filterByDays(30,this)">近 30 天</button>
  </div>

  <h2>{UI["section_core"]}（<span class="section-count">{len(core_p)}</span>）</h2>
{"".join(render_paper(p) for p in core_p)}


<h2>{UI["section_proxy"]}（<span class="section-count">{len(proxy_p)}</span>）</h2>
{"".join(render_paper(p) for p in proxy_p)}


<h2>{UI["section_eco"]}（<span class="section-count">{len(eco_p)}</span>）</h2>
{"".join(render_paper(p) for p in eco_p)}


<div class="footer">
  <p>{UI["generated"]}：{today} · {UI["profile"]}：{html.escape(profile_name)}</p>
</div>


<script>
function filterByDays(days, btn) {{
  document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const refDate = new Date('{ref_date}');
  const cards = document.querySelectorAll('.paper-card[data-date]');
  let visible = {{core: 0, proxy: 0, eco: 0}};
  cards.forEach(card => {{
    const d = card.getAttribute('data-date');
    if (!d || days === 0) {{
      card.classList.remove('hidden');
      const tier = card.className.match(/tier-(core|proxy|eco)/);
      if (tier) visible[tier[1]]++;
      return;
    }}
    const pub = new Date(d);
    const diff = (refDate - pub) / (1000 * 60 * 60 * 24);
    if (diff <= days) {{
      card.classList.remove('hidden');
      const tier = card.className.match(/tier-(core|proxy|eco)/);
      if (tier) visible[tier[1]]++;
    }} else {{
      card.classList.add('hidden');
    }}
  }});
  // Update section counts
  const tiers = ['core', 'proxy', 'eco'];
  document.querySelectorAll('.section-count').forEach((el, i) => {{
    if (i < tiers.length) el.textContent = visible[tiers[i]] || 0;
  }});
}}
// 页面加载时默认执行 7 天过滤
document.addEventListener('DOMContentLoaded', function() {{
  filterByDays(7, document.querySelector('.date-btn[data-days="7"]'));
}});
</script>

</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"\nSaved: {output_path}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a bilingual Chinese-English frontier report from screened data."
    )
    parser.add_argument("--input", type=Path, required=True, help="Screened JSON file.")
    parser.add_argument("--output", type=Path, required=True, help="Output HTML report path.")
    parser.add_argument("--title", default=None, help="Report title.")
    parser.add_argument("--profile", default="patent-biblio-profile", help="Profile name for footer.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    title = args.title or f"{UI['title']} · {date.today().isoformat()}"
    render_bilingual_html(data, title, args.profile, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

