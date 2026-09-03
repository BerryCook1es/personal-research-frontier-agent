from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any

from .common import POOL_LABELS, PRIORITY_LABELS


SECTION_LABELS = {
    "A": "A · 必读 / Must Read",
    "B": "B · 方法 / Method",
    "C": "C · 前沿 / Frontier",
    "D": "D · 背景 / Background",
    "Ignore": "暂不推荐 / Ignore",
}


def _value(paper: dict[str, Any], key: str, fallback: str = "") -> str:
    value = paper.get(key, fallback)
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value)
    return html.escape(str(value or fallback))


def _paper_link(paper: dict[str, Any]) -> str:
    return str(
        paper.get("doi_url")
        or paper.get("semantic_scholar_url")
        or paper.get("crossref_url")
        or ""
    )


def _badge(text: str, css_class: str = "") -> str:
    if not text:
        return ""
    return f'<span class="badge {css_class}">{html.escape(text)}</span>'


def _card(paper: dict[str, Any]) -> str:
    priority = str(paper.get("priority") or "Ignore")
    title = _value(paper, "title", "Untitled")
    link = _paper_link(paper)
    title_html = (
        f'<a href="{html.escape(link)}" target="_blank" rel="noopener">{title}</a>'
        if link else title
    )
    project = str(paper.get("related_project") or "").strip()
    pool = str(paper.get("pool") or "")
    contributions = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in paper.get("main_contributions") or []
    ) or "<li>摘要信息不足或未提取到明确贡献。</li>"
    topics = paper.get("matched_topics") or paper.get("matched_keywords") or []
    topic_badges = "".join(_badge(str(topic), "badge-topic") for topic in topics[:6])
    project_badge = _badge(f"Project · {project}", "badge-project") if project else ""
    pool_badge = _badge(POOL_LABELS.get(pool, pool), "badge-pool") if pool else ""
    semantic = paper.get("semantic_score")
    semantic_text = "disabled" if semantic is None else f"{float(semantic):.3f}"
    abstract_source = str(paper.get("abstract_source") or "")
    source_note = _badge(f"Abstract · {abstract_source}", "badge-source") if abstract_source else ""
    pub_date = _value(paper, "publication_date")

    return f"""<article class="paper-card priority-{priority}" data-date="{pub_date}" data-priority="{priority}">
  <div class="paper-title-en">{title_html}</div>
  <div class="paper-title-cn">{_value(paper, 'title_cn', '中文标题暂缺')}</div>
  <div class="badges">
    {_badge(PRIORITY_LABELS.get(priority, priority), f'badge-{priority}')}
    {_badge(f"Relevance · {paper.get('relevance_score', 0)}/100", 'badge-score')}
    {_badge(str(paper.get('research_track') or ''), 'badge-track')}
    {project_badge}{pool_badge}
  </div>
  <div class="paper-meta">
    <span class="meta-label">期刊/会议：</span>{_value(paper, 'venue', paper.get('journal', ''))}
    <span class="dot">·</span>{pub_date}
    <span class="dot">·</span><span class="meta-label">作者：</span>{_value(paper, 'authors', '未提供')}
    {source_note}
  </div>
  <div class="paper-topics">{topic_badges}</div>
  <section class="recommendation">
    <div><b>为什么推荐 / Why Relevant</b><p>{_value(paper, 'why_relevant', '未分析')}</p></div>
    <div><b>建议 / Recommended Action</b><p>{_value(paper, 'recommended_action', 'ignore')}</p></div>
  </section>
  <div class="analysis-grid">
    <section><b>研究问题 / Research Question</b><p>{_value(paper, 'research_question', '摘要信息不足')}</p></section>
    <section><b>核心方法 / Method</b><p>{_value(paper, 'method_summary', '摘要信息不足')}</p></section>
    <section><b>可迁移方法价值 / Methodological Value</b><p>{_value(paper, 'methodological_value', '未发现明确可迁移价值')}</p></section>
    <section><b>潜在用途 / Potential Use</b><p>{_value(paper, 'potential_use', '暂未发现')}</p></section>
  </div>
  <section><b>主要贡献 / Main Contributions</b><ul>{contributions}</ul></section>
  <details class="abstracts"><summary>中英文摘要 / Abstract CN &amp; EN</summary>
    <div class="paper-abstract-cn"><b>中文：</b>{_value(paper, 'abstract_cn', '中文摘要暂缺')}</div>
    <div class="paper-abstract-en"><b>English:</b> {_value(paper, 'abstract', 'Abstract not available from configured providers.')}</div>
  </details>
  <div class="evidence">Keyword tier: {_value(paper, 'keyword_tier', 'other')} · Semantic: {semantic_text} · Matched: {_value(paper, 'matched_keywords', 'none')}</div>
</article>"""


def render_report(data: dict[str, Any], output_path: Path) -> Path:
    profile = data["profile"]
    selected = data.get("report_papers") or []
    all_candidates = data.get("all_candidates") or []
    stats = data.get("stats") or {}
    judged_stats = data.get("judged_stats") or stats
    coverage = data.get("coverage") or {}

    sections = {
        priority: [paper for paper in selected if paper.get("priority") == priority]
        for priority in ("A", "B", "C")
    }
    sections["D"] = [paper for paper in all_candidates if paper.get("priority") == "D"]
    sections["Ignore"] = [paper for paper in all_candidates if paper.get("priority") == "Ignore"]

    top_five = sorted(selected, key=lambda paper: paper.get("relevance_score", 0), reverse=True)[:5]
    top_html = "".join(
        f"<li><b>{_value(paper, 'title_cn', paper.get('title', ''))}</b>"
        f"<span>{_value(paper, 'why_relevant', '关键词召回候选')}</span></li>"
        for paper in top_five
    ) or "<li class=\"empty\">本窗口没有达到 A/B/C 推荐标准的论文；D 与 Ignore 候选仍保留在下方供核查。</li>"

    pool_counts: dict[str, int] = {}
    for paper in all_candidates:
        pool = str(paper.get("pool") or "")
        if pool:
            pool_counts[pool] = pool_counts.get(pool, 0) + 1
    pool_html = "".join(
        _badge(f"{POOL_LABELS.get(pool, pool)} · {count}", "badge-pool")
        for pool, count in sorted(pool_counts.items(), key=lambda item: -item[1])
    )

    section_html = []
    for priority in ("A", "B", "C"):
        papers = sections[priority]
        cards = "".join(_card(paper) for paper in papers)
        empty = '<p class="empty-section">本类别暂无论文。</p>' if not papers else ""
        section_html.append(
            f'<section class="priority-section" data-section="{priority}"><h2>{SECTION_LABELS[priority]} '
            f'（<span class="section-count" data-count="{priority}">{len(papers)}</span>）</h2>{cards}{empty}</section>'
        )

    background_cards = "".join(_card(paper) for priority in ("D", "Ignore") for paper in sections[priority])
    background_count = len(sections["D"]) + len(sections["Ignore"])
    other_html = f"""<details class="other-section" open>
  <summary>其他候选 / Background &amp; Ignore（<span class="section-count" data-count="other">{background_count}</span>）</summary>
  {background_cards or '<p class="empty-section">暂无其他候选。</p>'}
</details>"""

    today = date.today().isoformat()
    ref_date = html.escape(str(coverage.get("to") or today))
    content = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>个人前沿论文追踪周报 · {html.escape(profile['name'])}</title>
<style>
body{{font-family:-apple-system,"Microsoft YaHei","PingFang SC",system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:20px;background:#f8f9fa;color:#2c3e50;line-height:1.65}}
h1{{color:#1a5276;border-bottom:3px solid #2980b9;padding-bottom:8px;font-size:1.8em}}
h2{{color:#2c3e50;margin-top:30px;padding:8px 0;border-bottom:1px solid #ddd}}
a{{color:#2980b9;text-decoration:none}}a:hover{{text-decoration:underline}}
.subtitle{{color:#607080;margin-top:-8px}}.stats{{background:#eaf2f8;padding:15px;border-radius:8px;margin:18px 0}}
.stats-row{{display:flex;flex-wrap:wrap;gap:12px;align-items:center}}.stats-row strong{{font-size:1.05em}}
.stats-pools{{margin-top:10px;padding-top:10px;border-top:1px dashed #bdc3c7}}
.top-five{{background:white;border-left:4px solid #2980b9;padding:12px 18px;border-radius:6px}}.top-five li{{margin:8px 0}}.top-five li span{{display:block;color:#65717f;font-size:.9em}}
.date-filter{{text-align:center;margin:18px 0}}.date-btn{{padding:5px 15px;margin:0 4px;border:1px solid #bdc3c7;border-radius:15px;background:white;color:#555;cursor:pointer}}.date-btn.active{{background:#2980b9;color:white;border-color:#2980b9}}
.paper-card{{background:white;padding:16px 18px;margin:12px 0;border-radius:6px;border-left:5px solid #95a5a6;box-shadow:0 1px 5px #20305012}}
.priority-A{{background:#fff4f0;border-left-color:#d4380d}}.priority-B{{background:#fef9e7;border-left-color:#f39c12}}.priority-C{{background:#ebf5fb;border-left-color:#2980b9}}.priority-D{{background:#f4f6f7;border-left-color:#7f8c8d}}.priority-Ignore{{background:#fafafa;border-left-color:#bdc3c7}}
.paper-title-en{{font-weight:bold;font-size:1.02em;color:#4d5966}}.paper-title-cn{{font-weight:bold;font-size:1.12em;color:#1a5276;margin:3px 0 7px}}
.badges{{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0}}.badge{{display:inline-block;padding:2px 9px;border-radius:10px;font-size:.76em;border:1px solid #d7dde4;background:white}}
.badge-A{{background:#d4380d;color:white;border-color:#d4380d}}.badge-B{{background:#f39c12;color:white;border-color:#f39c12}}.badge-C{{background:#2980b9;color:white;border-color:#2980b9}}.badge-D{{background:#7f8c8d;color:white;border-color:#7f8c8d}}.badge-Ignore{{background:#bdc3c7;color:#34495e}}
.badge-topic{{background:#e8f0fe;color:#1a5276;border-color:#bdd7ee}}.badge-pool{{color:#6c3483;border-color:#c39bd3}}.badge-project{{color:#1e8449;border-color:#7dcea0}}.badge-source{{margin-left:5px;color:#777}}
.paper-meta{{color:#777;font-size:.87em;margin:7px 0}}.meta-label{{color:#999}}.dot{{margin:0 6px}}.paper-topics{{margin-bottom:8px}}
.recommendation{{display:grid;grid-template-columns:2fr 1fr;gap:12px;background:#fffdf2;border:1px solid #f4e6a6;border-radius:6px;padding:10px 12px;margin:10px 0}}
.analysis-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}section p{{margin:.25em 0}}section ul{{margin-top:.3em}}
.analysis-grid section{{padding:9px 11px;background:#f8fafc;border-radius:5px}}.abstracts{{background:#f8fafc;padding:9px 12px;border-radius:6px;margin-top:10px}}
.abstracts summary,.other-section summary{{cursor:pointer;font-weight:bold;color:#1a5276}}.paper-abstract-cn,.paper-abstract-en{{padding-left:9px;border-left:2px solid #bdc3c7;margin-top:9px}}.paper-abstract-en{{color:#666;border-left-color:#ecf0f1;font-size:.9em}}
.evidence{{color:#82909f;font-size:.82em;margin-top:10px}}.empty,.empty-section{{color:#8b96a3;font-style:italic}}.other-section{{margin-top:30px;padding-top:8px;border-top:1px solid #ddd}}.other-section>summary{{font-size:1.25em}}
.paper-card.hidden{{display:none}}footer{{color:#999;margin-top:40px;font-size:.84em;text-align:center;border-top:1px solid #ddd;padding-top:15px}}
@media(max-width:760px){{body{{padding:12px}}.analysis-grid,.recommendation{{grid-template-columns:1fr}}.paper-card{{padding:13px}}}}
</style></head><body>
<h1>个人前沿论文追踪周报 / Weekly Research Brief</h1>
<p class="subtitle">Profile：<b>{html.escape(profile['name'])}</b> · {html.escape(str(coverage.get('from', '')))} → {ref_date}</p>
<div class="stats"><div class="stats-row">
  <strong>本周扫描：{judged_stats.get('scanned', 0)}</strong><strong>候选：{judged_stats.get('candidates', 0)}</strong>
  <strong>A 必读：{stats.get('A', 0)}</strong><strong>B 方法：{stats.get('B', 0)}</strong><strong>C 前沿：{stats.get('C', 0)}</strong>
  <span>D 背景：{judged_stats.get('D', 0)}</span><span>Ignore：{judged_stats.get('Ignore', 0)}</span>
</div><div class="stats-row stats-pools">{pool_html}</div></div>
<h2>Top 5 推荐理由</h2><ol class="top-five">{top_html}</ol>
<div class="date-filter"><span>时间范围：</span><button class="date-btn active" data-days="7" onclick="filterByDays(7,this)">近 7 天</button><button class="date-btn" data-days="30" onclick="filterByDays(30,this)">近 30 天</button><button class="date-btn" data-days="0" onclick="filterByDays(0,this)">全部</button></div>
{''.join(section_html)}{other_html}
<footer>生成日期：{today} · Profile：{html.escape(profile['name'])} · 数据来自配置的学术数据源，LLM 判断请由研究者复核。</footer>
<script>
function filterByDays(days,btn){{
  document.querySelectorAll('.date-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');
  const refDate=new Date('{ref_date}T23:59:59');const counts={{A:0,B:0,C:0,other:0}};
  document.querySelectorAll('.paper-card').forEach(card=>{{
    const raw=card.dataset.date;const pub=raw?new Date(raw):null;const diff=pub?(refDate-pub)/86400000:0;
    const visible=days===0||!pub||diff<=days;card.classList.toggle('hidden',!visible);
    if(visible){{const p=card.dataset.priority;counts[p]!==undefined?counts[p]++:counts.other++;}}
  }});
  ['A','B','C'].forEach(p=>{{const el=document.querySelector('[data-count="'+p+'"]');if(el)el.textContent=counts[p];}});
  const other=document.querySelector('[data-count="other"]');if(other)other.textContent=counts.other;
}}
document.addEventListener('DOMContentLoaded',()=>filterByDays(7,document.querySelector('[data-days="7"]')));
</script></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
