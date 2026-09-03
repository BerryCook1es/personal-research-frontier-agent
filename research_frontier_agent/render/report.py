from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any

from .common import POOL_LABELS


PRIORITY_LABELS = {
    "A": "A · 必读",
    "B": "B · 方法",
    "C": "C · 前沿",
    "D": "D · 背景",
    "Ignore": "暂不推荐",
}

PROFILE_TOPICS = {
    "scholarly-kg-llm": "学术文本挖掘 / 科学知识图谱 / LLM 与 Agent 方法",
    "scientometrics-evaluation": "文献计量 / 科学计量 / 科研评价",
    "human-ai-algorithm": "人机交互 / 算法认知 / AI 使用行为",
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
        if link
        else title
    )
    project = str(paper.get("related_project") or "").strip()
    pool = str(paper.get("pool") or "")
    source = str(paper.get("source") or "")
    venue = str(paper.get("venue") or paper.get("journal") or "")
    pub_date = str(paper.get("publication_date") or "")
    relevance = int(paper.get("relevance_score") or 0)
    semantic = paper.get("semantic_score")
    semantic_text = "未启用" if semantic is None else f"{float(semantic):.3f}"

    contributions = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in paper.get("main_contributions") or []
    ) or "<li>摘要信息不足或未提取到明确贡献。</li>"
    topics = paper.get("matched_topics") or paper.get("matched_keywords") or []
    topic_badges = "".join(_badge(str(topic), "badge-topic") for topic in topics[:6])
    search_text = " ".join(
        str(paper.get(key) or "")
        for key in ("title", "title_cn", "authors", "venue", "journal", "research_track")
    ).lower()

    return f"""<article class="paper-card priority-{priority}" data-date="{html.escape(pub_date)}" data-priority="{html.escape(priority)}" data-venue="{html.escape(venue)}" data-source="{html.escape(source)}" data-relevance="{relevance}" data-search="{html.escape(search_text)}">
  <div class="card-body">
    <div class="card-badges">
      {_badge(PRIORITY_LABELS.get(priority, priority), f'badge-{priority}')}
      {_badge(POOL_LABELS.get(pool, pool), f'badge-pool badge-pool-{pool}') if pool else ''}
      {_badge(f'相关度 {relevance}/100', 'badge-score')}
      {_badge(str(paper.get('research_track') or ''), 'badge-track')}
      {_badge(f'项目 · {project}', 'badge-project') if project else ''}
    </div>
    <div class="card-title-en">{title_html}</div>
    <div class="card-title-cn">{_value(paper, 'title_cn', '中文标题暂缺')}</div>
    <div class="card-meta">
      <span class="card-meta-item">{html.escape(pub_date or '?')}</span><span class="card-meta-dot"></span>
      <span class="card-meta-item">{html.escape(venue or '?')}</span><span class="card-meta-dot"></span>
      <span class="card-meta-item">{_value(paper, 'authors', '作者信息暂缺')}</span>
      {_badge(f'摘要来源 · {str(paper.get("abstract_source") or "")}', 'badge-source') if paper.get('abstract_source') else ''}
    </div>
    <div class="card-topics">{topic_badges}</div>
    <div class="card-abstract">
      <p class="abs-cn">{_value(paper, 'abstract_cn', '中文摘要暂缺。')}</p>
      <p class="abs-en" lang="en">{_value(paper, 'abstract', 'Abstract not available from configured providers.')}</p>
    </div>
    <div class="research-analysis">
      <div class="analysis-item"><b>研究问题</b><p>{_value(paper, 'research_question', '摘要信息不足')}</p></div>
      <div class="analysis-item"><b>核心方法</b><p>{_value(paper, 'method_summary', '摘要信息不足')}</p></div>
      <div class="analysis-item analysis-wide"><b>主要贡献</b><ul>{contributions}</ul></div>
      <div class="analysis-item"><b>推荐理由</b><p>{_value(paper, 'why_relevant', '未分析')}</p></div>
      <div class="analysis-item"><b>可迁移价值</b><p>{_value(paper, 'methodological_value', '未发现明确可迁移价值')}</p></div>
      <div class="analysis-item"><b>潜在用途</b><p>{_value(paper, 'potential_use', '暂未发现')}</p></div>
      <div class="analysis-item"><b>阅读建议</b><p>{_value(paper, 'recommended_action', 'ignore')}</p></div>
    </div>
    <div class="screening-evidence">关键词层级：{_value(paper, 'keyword_tier', 'other')} · 语义得分：{semantic_text} · 命中词：{_value(paper, 'matched_keywords', '无')}</div>
    <div class="card-actions">{f'<a href="{html.escape(link)}" target="_blank" rel="noopener">查看原文 DOI</a><button class="copy-link" type="button" data-link="{html.escape(link)}" onclick="copyLink(this)">复制链接</button>' if link else ''}</div>
  </div>
</article>"""


def render_report(data: dict[str, Any], output_path: Path) -> Path:
    profile = data["profile"]
    papers = data.get("all_candidates") or data.get("report_papers") or []
    coverage = data.get("coverage") or {}
    profile_name = str(profile.get("name") or "")
    topic = str(profile.get("topic") or PROFILE_TOPICS.get(profile_name) or profile_name)
    today = date.today().isoformat()
    ref_date = str(coverage.get("to") or today)

    priority_order = {"A": 0, "B": 1, "C": 2, "D": 3, "Ignore": 4}
    papers = sorted(
        papers,
        key=lambda paper: (
            priority_order.get(str(paper.get("priority") or "Ignore"), 5),
            -int(paper.get("relevance_score") or 0),
            str(paper.get("publication_date") or ""),
        ),
    )
    counts = {
        priority: sum(1 for paper in papers if str(paper.get("priority") or "Ignore") == priority)
        for priority in priority_order
    }
    priority_chips = "".join(
        f'<button class="stat-chip" data-priority="{priority}" onclick="filterByPriority(\'{priority}\',this)">{label}<span class="num">{counts[priority]}</span></button>'
        for priority, label in PRIORITY_LABELS.items()
    )
    venue_options = "".join(
        f'<option value="{html.escape(venue)}">{html.escape(venue)}</option>'
        for venue in sorted({str(p.get("venue") or p.get("journal") or "") for p in papers} - {""})
    )
    source_options = "".join(
        f'<option value="{html.escape(source)}">{html.escape(source)}</option>'
        for source in sorted({str(p.get("source") or "") for p in papers} - {""})
    )
    cards = "".join(_card(paper) for paper in papers)

    content = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>前沿论文追踪周报·Frontier Weekly</title>
<style>
:root{{--bg:#f2f4f7;--card-bg:#fff;--text:#1e293b;--text2:#64748b;--border:#dfe4ea;--radius:12px;--blue:#1e5a8a;--c-A:#c0392b;--c-B:#d68910;--c-C:#2980b9;--c-D:#7f8c8d;--c-Ignore:#b7c0c8}}
*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}body{{font-family:-apple-system,"Microsoft YaHei","PingFang SC","Noto Sans SC",system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;min-height:100vh;-webkit-font-smoothing:antialiased}}
.app-header{{background:linear-gradient(135deg,#0f2b3d 0%,#1a4a6e 40%,#1e5a8a 100%);color:#fff;padding:22px 32px;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(0,0,0,.15)}}
.header-inner{{width:100%}}.container{{max-width:1100px;margin:0 auto}}.app-header h1{{font-size:1.5em;line-height:1.3;margin:0 0 4px;font-weight:750;letter-spacing:-.02em}}.subtitle{{font-size:.83em;color:rgba(255,255,255,.68)}}
.header-filters{{display:flex;gap:10px;flex-wrap:wrap;margin-top:13px}}button{{font:inherit}}.stat-chip{{background:rgba(255,255,255,.12);color:#fff;padding:4px 14px;border-radius:20px;cursor:pointer;transition:all .2s;border:1px solid transparent;font-size:.84em;font-weight:500}}.stat-chip:hover{{background:rgba(255,255,255,.22);transform:translateY(-1px)}}.stat-chip.active{{background:rgba(255,255,255,.28);border-color:rgba(255,255,255,.45);box-shadow:0 0 0 2px rgba(255,255,255,.1)}}.stat-chip .num{{margin-left:4px;font-weight:700}}
.container{{padding:20px 18px 42px}}.toolbar{{display:grid;grid-template-columns:minmax(280px,1fr) 170px 250px;gap:10px;margin-bottom:12px}}.search-box{{position:relative}}.search-icon{{position:absolute;left:14px;top:50%;transform:translateY(-50%);opacity:.5}}.search-box input,select{{width:100%;height:38px;border:1px solid var(--border);border-radius:24px;background:var(--card-bg);color:var(--text);font-size:13px}}.search-box input{{padding:9px 14px 9px 38px}}select{{padding:8px 32px 8px 13px;cursor:pointer}}.search-box input:focus,select:focus{{outline:none;border-color:#2980b9;box-shadow:0 0 0 3px rgba(41,128,185,.1)}}
.filter-bar{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:13px}}.pill,.sort-btn{{padding:6px 18px;border-radius:20px;border:1px solid var(--border);background:var(--card-bg);cursor:pointer;font-size:.86em;color:var(--text2);font-weight:500;transition:all .18s}}.pill:hover,.sort-btn:hover{{border-color:#2980b9;color:#2980b9}}.pill.active{{background:var(--blue);color:#fff;border-color:var(--blue);font-weight:600}}.sort-btn.active{{background:#e8f0fe;border-color:#2980b9;color:#1a5276;font-weight:600}}.divider{{color:#cbd5e0;margin:0 4px}}.spacer{{flex:1}}#count{{color:var(--text2);font-size:.84em;font-weight:500}}
.paper-list{{display:flex;flex-direction:column;gap:12px}}.paper-card{{background:var(--card-bg);border-radius:var(--radius);box-shadow:0 1px 4px rgba(0,0,0,.05);overflow:hidden;transition:box-shadow .25s,transform .15s;border-left:5px solid transparent;position:relative}}.paper-card:hover{{box-shadow:0 4px 20px rgba(0,0,0,.1);transform:translateY(-2px)}}.paper-card.priority-A{{border-left-color:var(--c-A)}}.paper-card.priority-B{{border-left-color:var(--c-B)}}.paper-card.priority-C{{border-left-color:var(--c-C)}}.paper-card.priority-D{{border-left-color:var(--c-D)}}.paper-card.priority-Ignore{{border-left-color:var(--c-Ignore);opacity:.86}}.paper-card.hidden{{display:none}}.card-body{{padding:16px 20px}}
.card-badges{{display:flex;gap:7px;align-items:center;margin-bottom:9px;flex-wrap:wrap}}.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:.72em;font-weight:600;line-height:1.4}}.badge-A{{background:#fadbd8;color:#922b21}}.badge-B{{background:#fef3cd;color:#9a6700}}.badge-C{{background:#d6eaf8;color:#1a5276}}.badge-D{{background:#e5e8e8;color:#566573}}.badge-Ignore{{background:#eceff1;color:#777}}.badge-pool{{background:#f1f5f9;color:#475569}}.badge-topic{{font-size:.69em;background:#e8f0fe;color:#1a5276;border:1px solid #c5d9f0}}.badge-score{{background:#edf6f9;color:#216869}}.badge-track{{background:#f5eef8;color:#6c3483}}.badge-project{{background:#e8f8f5;color:#0e6655}}.badge-source{{padding:2px 8px;background:#f7f8fa;color:#8a94a2;font-weight:500}}
.card-title-en{{font-size:1.06em;font-weight:700;color:#1a3a4a;margin-bottom:2px;line-height:1.55}}.card-title-en a{{color:inherit;text-decoration:none}}.card-title-en a:hover{{color:#2980b9}}.card-title-cn{{font-size:.92em;color:#2c3e50;margin-bottom:9px;line-height:1.5;font-weight:400}}.card-meta{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;font-size:.8em;color:var(--text2);margin-bottom:7px}}.card-meta-item{{display:inline-flex;align-items:center}}.card-meta-dot{{width:4px;height:4px;border-radius:50%;background:#cbd5e0;flex-shrink:0}}.card-topics{{display:flex;gap:5px;flex-wrap:wrap}}
.card-abstract{{margin-top:10px;padding-top:10px;border-top:1px solid #eef1f5}}.card-abstract p{{margin:0;text-align:justify}}.abs-cn{{font-size:.88em;color:var(--text);line-height:1.72}}.abs-en{{font-size:.83em;color:var(--text2);line-height:1.62;margin-top:7px!important}}
.research-analysis{{display:grid;grid-template-columns:1fr 1fr;gap:0 24px;margin-top:14px;padding-top:12px;border-top:1px solid #eef1f5}}.analysis-item{{padding:4px 0 8px}}.analysis-item b{{display:block;color:#1a5276;font-size:.84em;margin-bottom:2px}}.analysis-item p,.analysis-item ul{{font-size:.85em;margin:0;color:#374151}}.analysis-item ul{{padding-left:20px}}.analysis-wide{{grid-column:1/-1}}.screening-evidence{{font-size:.75em;color:#94a3b8;margin-top:3px}}.card-actions{{display:flex;gap:16px;align-items:center;margin-top:10px}}.card-actions a,.copy-link{{font-size:.82em;color:#1e5a8a;text-decoration:none;font-weight:600}}.copy-link{{cursor:pointer;border:0;background:none;padding:0;color:#94a3b8}}.empty{{text-align:center;padding:80px 20px;color:#a8b2c0}}
.footer{{color:#999;margin-top:38px;font-size:.82em;text-align:center;border-top:1px solid #ddd;padding-top:15px}}.toast{{position:fixed;bottom:28px;left:50%;transform:translateX(-50%);background:#1e293b;color:#fff;padding:9px 22px;border-radius:24px;font-size:.84em;z-index:999;opacity:0;transition:opacity .25s;pointer-events:none}}.toast.show{{opacity:1}}
@media(max-width:760px){{.app-header{{padding:17px 16px;position:relative}}.app-header h1{{font-size:1.26em}}.container{{padding:14px 10px 30px}}.toolbar{{grid-template-columns:1fr}}.research-analysis{{grid-template-columns:1fr}}.analysis-wide{{grid-column:auto}}.card-body{{padding:13px 14px}}.divider{{display:none}}}}
</style></head><body>
<header class="app-header"><div class="header-inner">
  <h1>前沿论文追踪周报·Frontier Weekly</h1>
  <div class="subtitle">覆盖周期：{html.escape(str(coverage.get('from') or ''))} → {html.escape(ref_date)} · 主题：{html.escape(topic)}</div>
  <div class="header-filters"><button class="stat-chip active" data-priority="" onclick="filterByPriority('',this)">全部<span class="num">{len(papers)}</span></button>{priority_chips}</div>
</div></header>
<main class="container">
  <div class="toolbar">
    <label class="search-box"><span class="search-icon">⌕</span><input id="search" type="search" placeholder="搜索标题、期刊、作者或研究方向" oninput="applyFilters()"></label>
    <select id="source-filter" onchange="applyFilters()"><option value="">全部来源</option>{source_options}</select>
    <select id="venue-filter" onchange="applyFilters()"><option value="">全部期刊 / 会议</option>{venue_options}</select>
  </div>
  <div class="filter-bar">
    <button class="pill active" data-days="7" onclick="filterByDays(7,this)">近 7 天</button><button class="pill" data-days="30" onclick="filterByDays(30,this)">近 30 天</button><button class="pill" data-days="0" onclick="filterByDays(0,this)">全部时间</button>
    <span class="divider">|</span><button class="sort-btn" data-sort="date-desc" onclick="setSort('date-desc',this)">最新优先</button><button class="sort-btn" data-sort="date-asc" onclick="setSort('date-asc',this)">最早优先</button><button class="sort-btn active" data-sort="priority" onclick="setSort('priority',this)">按级别</button><span class="spacer"></span><span id="count"></span>
  </div>
  <div id="list" class="paper-list">{cards}</div><div id="empty" class="empty" hidden>没有匹配的论文，请调整筛选条件。</div>
  <div class="footer">生成日期：{today} · 主题配置：{html.escape(profile_name)} · LLM 判断请由研究者复核</div>
</main><div id="toast" class="toast">链接已复制</div>
<script>
let activePriority='',activeDays=7,activeSort='priority';const refDate=new Date('{html.escape(ref_date)}T23:59:59');
function filterByPriority(priority,btn){{activePriority=priority;document.querySelectorAll('.stat-chip').forEach(b=>b.classList.remove('active'));btn.classList.add('active');applyFilters();}}
function filterByDays(days,btn){{activeDays=days;document.querySelectorAll('.pill').forEach(b=>b.classList.remove('active'));btn.classList.add('active');applyFilters();}}
function setSort(sort,btn){{activeSort=sort;document.querySelectorAll('.sort-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');applyFilters();}}
function applyFilters(){{
  const query=document.getElementById('search').value.trim().toLowerCase(),source=document.getElementById('source-filter').value,venue=document.getElementById('venue-filter').value;
  const cards=[...document.querySelectorAll('.paper-card')];let visible=0;
  cards.forEach(card=>{{const raw=card.dataset.date,pub=raw?new Date(raw+'T00:00:00'):null,diff=pub?(refDate-pub)/86400000:0;const show=(!activePriority||card.dataset.priority===activePriority)&&(!source||card.dataset.source===source)&&(!venue||card.dataset.venue===venue)&&(!query||card.dataset.search.includes(query))&&(activeDays===0||!pub||diff<=activeDays);card.classList.toggle('hidden',!show);if(show)visible++;}});
  const order={{A:0,B:1,C:2,D:3,Ignore:4}};cards.sort((a,b)=>activeSort==='date-asc'?a.dataset.date.localeCompare(b.dataset.date):activeSort==='date-desc'?b.dataset.date.localeCompare(a.dataset.date):(order[a.dataset.priority]-order[b.dataset.priority]||Number(b.dataset.relevance)-Number(a.dataset.relevance)));const list=document.getElementById('list');cards.forEach(card=>list.appendChild(card));
  document.getElementById('count').textContent=visible+' / '+cards.length+' 篇';document.getElementById('empty').hidden=visible!==0;
}}
async function copyLink(btn){{try{{await navigator.clipboard.writeText(btn.dataset.link);showToast('链接已复制');}}catch(_err){{showToast('复制失败，请打开原文后复制地址');}}}}
function showToast(message){{const toast=document.getElementById('toast');toast.textContent=message;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),1600);}}
document.addEventListener('DOMContentLoaded',applyFilters);
</script></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
