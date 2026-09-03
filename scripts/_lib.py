"""Frontier Tracker 共享库 — 常量、工具函数、翻译引擎、筛选逻辑。"""

from __future__ import annotations

import html as _html_mod
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# 路径与常量
# ══════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "frontier-tracker/2.0 (crossref; mailto:your-email@example.com)"
BASE_URL = "https://api.crossref.org/works"

# ── 加载 .env 文件（避免外部依赖，手写解析器） ──
def _load_dotenv() -> None:
    """从项目根目录 .env 加载环境变量（不覆盖已存在的环境变量）。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

_load_dotenv()

NON_RESEARCH_PATTERNS = (
    r"^author correction", r"^publisher correction", r"^correction:",
    r"^retraction:", r"^erratum", r"^editorial:",
    r"^news & views", r"^reply to", r"^response to",
)

# ══════════════════════════════════════════════════════════════
# 学术术语对照表（63条）—— 按长度降序，避免短词抢先匹配
# ══════════════════════════════════════════════════════════════

ACADEMIC_GLOSSARY = {
    "bibliometric": "文献计量学", "bibliometrics": "文献计量学",
    "scientometric": "科学计量学", "scientometrics": "科学计量学",
    "informetric": "信息计量学", "informetrics": "信息计量学",
    "patentometrics": "专利计量学", "altmetrics": "替代计量学",
    "science of science": "科学学", "metascience": "元科学",
    "web of science": "Web of Science", "scopus": "Scopus", "scival": "SciVal",
    "technology opportunity": "技术机会", "technological opportunity": "技术机会",
    "technology convergence": "技术融合", "technology fusion": "技术融合",
    "technology forecasting": "技术预测", "technology trajectory": "技术轨迹",
    "disruptive technology": "颠覆性技术", "emerging technology": "新兴技术",
    "technology transfer": "技术转移", "technology identification": "技术识别",
    "patent analysis": "专利分析", "patent citation": "专利引文",
    "patent landscape": "专利布局", "patent mining": "专利挖掘",
    "knowledge spillover": "知识溢出", "knowledge combination": "知识组合",
    "innovation measurement": "创新测度", "innovation diffusion": "创新扩散",
    "innovation system": "创新体系", "co-word analysis": "共词分析",
    "topic modeling": "主题建模", "link prediction": "链接预测",
    "citation analysis": "引文分析", "citation network": "引文网络",
    "network analysis": "网络分析", "text mining": "文本挖掘",
    "knowledge graph": "知识图谱", "causal inference": "因果推断",
    "natural language processing": "自然语言处理",
    "peer reviewers": "同行评议人", "peer reviewer": "同行评议人",
    "peer review": "同行评议", "open access": "开放获取",
    "open science": "开放科学", "open data": "开放数据",
    "research evaluation": "科研评估", "research assessment": "科研评估",
    "research integrity": "科研诚信", "research funding": "科研资助",
    "science policy": "科技政策", "r&d": "研发", "s&t": "科技",
    "matthew effect": "马太效应", "citation impact": "引文影响力",
    "citation count": "被引次数", "h-index": "h指数", "impact factor": "影响因子",
    "gini": "基尼", "reproducibility": "可重复性",
    "interdisciplinary": "跨学科", "scientific collaboration": "科研合作",
    "scientific careers": "科研职业生涯", "research productivity": "科研生产力",
    "scholarly communication": "学术交流", "data sharing": "数据共享",
}
GLOSSARY_SORTED = sorted(ACADEMIC_GLOSSARY.items(), key=lambda x: -len(x[0]))
_GLOSSARY_PATTERNS = [(re.compile(re.escape(en), re.IGNORECASE), cn) for en, cn in GLOSSARY_SORTED]

# ══════════════════════════════════════════════════════════════
# 双语 UI 标签
# ══════════════════════════════════════════════════════════════

UI = {
    "title": "前沿论文周报 · Frontier Weekly Report",
    "stats_scanned": "扫描论文总数 Total scanned",
    "stats_core": "核心 Core", "stats_proxy": "邻近 Proxy", "stats_eco": "背景 Eco",
    "section_core": "核心论文 Core Papers",
    "section_proxy": "邻近论文 Proxy Papers",
    "section_eco": "背景论文 Eco Context",
    "journal": "期刊", "authors": "作者",
    "generated": "生成时间", "profile": "筛选方案",
    "and_more": "篇未显示", "view_doi": "查看原文",
}

TIER_LABELS = {
    "core": "核心 Core",
    "proxy": "邻近 Proxy",
    "eco": "背景 Eco",
    "other": "其他 Other",
}

POOL_LABELS = {
    "patent-tech-mining": "专利技术挖掘",
    "bibliometrics-evaluation": "文献计量与评价",
    "science-policy-innovation": "科技政策与创新",
    "info-methods-datamining": "信息方法与数据挖掘",
    "ai-usage-behavior": "AI使用行为",
    "complex-network-analysis": "复杂网络分析",
    "knowledge-graph-semantic": "知识图谱与语义",
    "comprehensive-high-impact": "综合高影响力",
}

# ══════════════════════════════════════════════════════════════
# CrossRef API 工具
# ══════════════════════════════════════════════════════════════

def request_json(url: str, timeout: float = 30.0) -> dict:
    """GET CrossRef API，带 429 重试。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            print(f"  HTTP {e.code}", file=sys.stderr)
            return {}
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            print(f"  Error: {e}", file=sys.stderr)
            return {}
    return {}


def strip_html(text: str) -> str:
    """去除 HTML/XML 标签（CrossRef 摘要常有 <jats:p>）。"""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_non_research(title: str) -> bool:
    """过滤 Editorial、Correction、News 等非研究文章。"""
    t = title.lower().strip()
    for pat in NON_RESEARCH_PATTERNS:
        if re.match(pat, t):
            return True
    return False


def fetch_journal_papers(journal: str, issn: str, from_date: str, to_date: str,
                         pool: str, max_results: int = 100) -> list[dict]:
    """从 CrossRef 按 ISSN + 日期范围抓取期刊论文。"""
    papers = []
    offset = 0
    rows = min(max_results, 100)
    while offset < max_results:
        params = {
            "filter": f"issn:{issn},from-pub-date:{from_date},until-pub-date:{to_date}",
            "rows": rows, "offset": offset,
        }
        url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
        data = request_json(url)
        if not data:
            break
        items = data.get("message", {}).get("items", [])
        if not items:
            break
        for item in items:
            title = _html_mod.unescape((item.get("title") or [""])[0])
            if not title or _is_non_research(title):
                continue
            author_list = item.get("author") or []
            author_names = [f"{a.get('given','')} {a.get('family','')}".strip() for a in author_list]
            authors_str = "; ".join(author_names[:8])
            if len(author_list) > 8:
                authors_str += " et al."
            pub_parts = (
                item.get("published-print", {}).get("date-parts", [[]])[0]
                or item.get("published-online", {}).get("date-parts", [[]])[0]
                or item.get("created", {}).get("date-parts", [[]])[0]
            )
            pub_date = ""
            if len(pub_parts) >= 3:
                y, m, d = int(pub_parts[0]), int(pub_parts[1]), int(pub_parts[2])
                # 校验：年份合理范围、月份 1-12、日期 1-31
                if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
                    pub_date = ""  # 异常日期丢弃
                else:
                    pub_date = f"{y:04d}-{m:02d}-{d:02d}"
            elif len(pub_parts) == 2:
                y, m = int(pub_parts[0]), int(pub_parts[1])
                if not (1900 <= y <= 2100 and 1 <= m <= 12):
                    pub_date = ""
                else:
                    pub_date = f"{y:04d}-{m:02d}"
            elif len(pub_parts) == 1:
                y = int(pub_parts[0])
                pub_date = str(y) if 1900 <= y <= 2100 else ""
            # 未来日期回退：超过查询截止日 30 天则丢弃（出版商预分配）
            if pub_date and pub_date > to_date:
                try:
                    pd = date.fromisoformat(pub_date) if len(pub_date) == 10 else date.fromisoformat(pub_date + "-01")
                    qd = date.fromisoformat(to_date)
                    if (pd - qd).days > 30:
                        pub_date = ""
                except ValueError:
                    pass
            doi_raw = item.get("DOI", "")
            doi_url = f"https://doi.org/{doi_raw}" if doi_raw else ""
            abstract_raw = item.get("abstract", "") or ""
            abstract = strip_html(abstract_raw)
            # 去掉出版商加在摘要开头的 "Abstract" / "Abstract." 前缀
            abstract = re.sub(r"^abstract\.?\s*", "", abstract, flags=re.IGNORECASE)
            # 解码 HTML 实体（如 &amp; → &），避免后续 html.escape 双重编码
            abstract = _html_mod.unescape(abstract)
            papers.append({
                "title": title, "abstract": abstract,
                "publication_date": pub_date,
                "year": int(pub_parts[0]) if pub_parts else None,
                "journal_source": journal,
                "journal": _html_mod.unescape((item.get("container-title") or [journal])[0]),
                "pool": pool, "authors": authors_str,
                "doi": doi_url, "doi_raw": doi_raw, "doi_url": doi_url,
                "crossref_url": item.get("URL", ""), "type": item.get("type", ""),
                "citation_count": item.get("is-referenced-by-count", 0),
                "subject": item.get("subject", []),
                "source": "crossref", "abstract_source": "crossref" if abstract else "",
            })
            if len(papers) >= max_results:
                break
        total = data.get("message", {}).get("total-results", 0)
        offset += rows
        if offset >= total:
            break
    return papers


# ══════════════════════════════════════════════════════════════
# Profile 关键词加载与筛选
# ══════════════════════════════════════════════════════════════

DEFAULT_CORE: list[str] = []
DEFAULT_PROXY: list[str] = []
DEFAULT_ECO: list[str] = []


def load_profile_keywords(profile_path: Path | None) -> tuple[list[str], list[str], list[str]]:
    """从 Markdown profile 提取 core / proxy / eco 关键词列表。"""
    if not profile_path or not profile_path.exists():
        print(f"[WARNING] Profile file not found: {profile_path}, ALL papers will be classified as other!",
              file=sys.stderr)
        return DEFAULT_CORE, DEFAULT_PROXY, DEFAULT_ECO
    text = profile_path.read_text(encoding="utf-8").lower()

    def _extract(heading: str) -> list[str]:
        pattern = rf"#+\s*{re.escape(heading)}.*?\n(.*?)(?=\n#+\s|\Z)"
        m = re.search(pattern, text, re.DOTALL)
        if not m:
            return []
        body = m.group(1)
        items = re.findall(
            r"(?:^|\n)\s*(?:[-*]|\d+[.)])\s+(.+?)(?=\n\s*(?:[-*]|\d+[.)])|\Z)",
            body, re.DOTALL,
        )
        if items:
            return [it.strip().strip('"').strip("'").strip() for it in items if it.strip()]
        return [line.strip().strip('"').strip("'").strip()
                for line in body.strip().split("\n") if line.strip()]

    core = (_extract("core topics") or _extract("core keywords") or _extract("core"))
    proxy = (_extract("proxy topics") or _extract("proxy keywords") or _extract("proxy"))
    eco = (_extract("secondary topics") or _extract("eco keywords")
           or _extract("eco-context") or _extract("eco"))
    return core, proxy, eco


def classify_paper(title: str, abstract: str,
                   core_kw: list[str], proxy_kw: list[str], eco_kw: list[str],
                   pool: str = "") -> str:
    """四级分类：core / proxy / eco / other。

    默认模式：单命中无支撑降一级（core→proxy, proxy→eco）。
    严格模式（comprehensive-high-impact + ai-usage-behavior）：需更强信号，
      core≥2→core, core=1→proxy, proxy≥2+eco→proxy, proxy=1→other, eco≥3→eco, eco≤2→other。
    """
    text = (title + " " + abstract).lower()
    core_hits = sum(1 for kw in core_kw if kw in text)
    proxy_hits = sum(1 for kw in proxy_kw if kw in text)
    eco_hits = sum(1 for kw in eco_kw if kw in text)

    # 综合期刊和AI行为池提高阈值，降低误检（大量论文与研究方向无关）
    strict = pool in ("comprehensive-high-impact", "ai-usage-behavior")

    if core_hits:
        if strict:
            return "core" if core_hits >= 2 else "proxy"
        return "core" if core_hits >= 2 or proxy_hits or eco_hits else "proxy"
    if proxy_hits:
        if strict:
            return "proxy" if proxy_hits >= 2 or eco_hits else "other"
        return "proxy" if proxy_hits >= 2 or eco_hits else "eco"
    if eco_hits:
        if strict:
            return "eco" if eco_hits >= 3 else "other"
        return "eco"
    return "other"


def screen_papers(papers: list[dict], core_kw: list[str],
                  proxy_kw: list[str], eco_kw: list[str]) -> list[dict]:
    return [
        {**p, "tier": classify_paper(
            p.get("title", "") or "", p.get("abstract", "") or "",
            core_kw, proxy_kw, eco_kw,
            p.get("pool", ""),
        )}
        for p in papers
    ]


# ══════════════════════════════════════════════════════════════
# 翻译引擎（术语保护 → Google 翻译 → 还原 + 补漏）
# ══════════════════════════════════════════════════════════════

def protect_terms(text: str) -> tuple[str, dict[str, str]]:
    """用标记替换已知学术术语，避免机翻破坏。"""
    if not text:
        return text, {}
    marker_map: dict[str, str] = {}
    for i, (pattern, cn_std) in enumerate(_GLOSSARY_PATTERNS):
        if pattern.search(text):
            marker = f"__GT{i}__"
            marker_map[marker] = cn_std
            text = pattern.sub(marker, text)
    return text, marker_map


def restore_terms(text: str, marker_map: dict[str, str]) -> str:
    """翻译后将标记替换回标准中文术语。"""
    if not text or not marker_map:
        return text
    for marker, cn_term in marker_map.items():
        text = text.replace(marker, cn_term)
    return text


def apply_glossary(text: str) -> str:
    """翻译后补漏：直接替换残留英文术语。"""
    if not text:
        return text
    for pattern, cn_std in _GLOSSARY_PATTERNS:
        text = pattern.sub(cn_std, text)
    return text


# ══════════════════════════════════════════════════════════════
# 翻译后端检测（优先级：DeepSeek > Ollama > Google）
# ══════════════════════════════════════════════════════════════

_translator_backend: str | None = None  # "deepseek" | "ollama" | "google" | None
DEEPSEEK_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY", "")
    or os.environ.get("DEEPSEEK_KEY", "")
    or ""  # 在 https://platform.deepseek.com 获取
)
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def _detect_translator() -> str:
    """检测可用的翻译后端：DeepSeek > Ollama 本地 > Google 在线。"""
    global _translator_backend
    if _translator_backend:
        return _translator_backend

    # 1. DeepSeek API（国内直连，中英翻译最佳）
    if DEEPSEEK_API_KEY:
        _translator_backend = "deepseek"
        print("  Using DeepSeek API for translation", file=sys.stderr)
        return _translator_backend

    # 2. Ollama 本地模型
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m.get("name", "") for m in data.get("models", [])]
            preferred = [m for m in models if "qwen" in m.lower()]
            if preferred:
                _translator_backend = "ollama"
                print(f"  Using Ollama local model: {preferred[0]}", file=sys.stderr)
                return _translator_backend
            elif models:
                _translator_backend = "ollama"
                print(f"  Using Ollama local model: {models[0]}", file=sys.stderr)
                return _translator_backend
    except Exception:
        pass

    # 3. 回退 Google
    _translator_backend = "google"
    print("  DeepSeek/Ollama not available, using Google Translate", file=sys.stderr)
    return _translator_backend


def _ollama_translate(text: str) -> str:
    """通过 Ollama API 调用本地模型翻译。"""
    prompt = (
        "Translate the following academic English text to Simplified Chinese. "
        "Preserve ALL technical terms exactly as marked (__GT markers). "
        "Maintain academic writing style. Output ONLY the Chinese translation, "
        "no explanations or notes.\n\n" + text
    )
    data = json.dumps({
        "model": "qwen2.5:7b",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return result.get("response", "").strip()


def _deepseek_translate(text: str) -> str:
    """通过 DeepSeek API 翻译（OpenAI 兼容接口，国内直连）。"""
    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": (
                "You are a professional academic translator. "
                "Translate the given English text to Simplified Chinese. "
                "Preserve ALL technical terms exactly as marked (__GT markers — do NOT translate them). "
                "Maintain rigorous academic writing style. "
                "Output ONLY the Chinese translation, no explanations or notes."
            )},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"].strip()


def translate_text(text: str, max_retries: int = 3) -> str:
    """英 → 简中翻译（优先 DeepSeek → Ollama 本地 → Google 在线），含术语保护/还原/补漏。"""
    if not text or not text.strip():
        return ""
    protected, marker_map = protect_terms(text)

    # 按优先级逐个尝试，失败自动级联到下一个
    backends = []

    # 1. DeepSeek API（国内直连，中英翻译质量最高）
    if DEEPSEEK_API_KEY:
        backends.append(("deepseek", _deepseek_translate, 2))

    # 2. Ollama 本地模型（需本地运行 ollama serve）
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            if data.get("models"):
                backends.append(("ollama", _ollama_translate, 3))
    except Exception:
        pass

    # 3. Google 翻译（在线，国内可能不可用）
    backends.append(("google", None, 2))

    for name, translate_fn, retry_delay in backends:
        for attempt in range(max_retries):
            try:
                if name == "google":
                    from deep_translator import GoogleTranslator
                    t = GoogleTranslator(source="en", target="zh-CN")
                    result = t.translate(protected)
                else:
                    result = translate_fn(protected)
                result = restore_terms(result, marker_map)
                result = apply_glossary(result)
                if not result:
                    raise ValueError("empty translation")
                # 成功后缓存此后端，后续调用跳过检测
                global _translator_backend
                _translator_backend = name
                return result
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
        # 当前后端全部重试失败，输出提示并继续下一个
        if name == "google":
            print(f"  All translation backends failed", file=sys.stderr)
        else:
            print(f"  {name.capitalize()} failed, trying next backend...", file=sys.stderr)

    return ""


def _translate_merged(title: str, abstract: str) -> tuple[str, str]:
    """一次 API 调用同时翻译标题和摘要，返回 (title_cn, abstract_cn)。"""
    if not DEEPSEEK_API_KEY:
        # 无 DeepSeek 时逐个翻译
        return translate_text(title), translate_text(abstract)

    protected_title, marker_map_t = protect_terms(title)
    protected_abs, marker_map_a = protect_terms(abstract)
    combined_map = {**marker_map_t, **marker_map_a}

    prompt = (
        "Translate the following academic English to Simplified Chinese.\n"
        "Input: title, then '---', then abstract.\n"
        "Output: Chinese title, then '---', then Chinese abstract.\n"
        "Preserve ALL __GT markers. Maintain academic style. No extra text.\n\n"
        f"{protected_title}\n---\n{protected_abs[:2000]}"
    )
    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1, "max_tokens": 4096,
    }).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    text = result["choices"][0]["message"]["content"].strip()

    # 解析 "标题 --- 摘要" 格式
    if "---" in text:
        parts = text.split("---", 1)
        title_cn = parts[0].strip()
        abstract_cn = parts[1].strip()
    else:
        title_cn, abstract_cn = text, ""

    title_cn = restore_terms(title_cn, combined_map)
    title_cn = apply_glossary(title_cn)
    abstract_cn = restore_terms(abstract_cn, combined_map)
    abstract_cn = apply_glossary(abstract_cn)
    return title_cn, abstract_cn


def translate_papers(papers: list[dict], workers: int = 10) -> list[dict]:
    """并发翻译论文标题、摘要和主题标签（other 仅译标题，合并 title+abstract）。"""
    total = len(papers)

    # Step 1: 收集唯一主题标签并并发翻译（含 other 论文，确保全面覆盖）
    topic_set: set[str] = set()
    for p in papers:
        pt = p.get("primary_topic", "")
        if pt:
            topic_set.add(pt)
        for t in p.get("all_topics", []):
            topic_set.add(t)

    topic_cache: dict[str, str] = {}
    if topic_set:
        print(f"  Translating {len(topic_set)} unique topic labels "
              f"({min(workers, len(topic_set))} workers)...", file=sys.stderr)
        topics_list = list(topic_set)
        with ThreadPoolExecutor(max_workers=min(workers, len(topic_set))) as pool:
            futures = {pool.submit(translate_text, t): t for t in topics_list}
            for future in as_completed(futures):
                topic = futures[future]
                try:
                    topic_cache[topic] = future.result()
                except Exception as e:
                    print(f"  Topic translation error: {e}", file=sys.stderr)
                    topic_cache[topic] = topic

    # Step 2: 收集任务（合并 title+abstract 为一次调用）
    single_tasks: list[tuple[int, str, str]] = []  # other 标题单独翻
    merged_tasks: list[tuple[int, str, str]] = []  # (idx, title, abstract) 合并翻

    for i, p in enumerate(papers):
        p = dict(p)
        papers[i] = p
        tier = p.get("tier", "other")

        if tier == "other":
            if not p.get("title_cn") and p.get("title"):
                single_tasks.append((i, "title_cn", p["title"]))
            else:
                p.setdefault("title_cn", "")
            if not p.get("abstract_cn") and p.get("abstract"):
                single_tasks.append((i, "abstract_cn", p["abstract"][:1500]))
            else:
                p.setdefault("abstract_cn", "")
        elif p.get("title_cn") and p.get("abstract_cn"):
            pass
        elif p.get("title_cn"):
            if p.get("abstract"):
                single_tasks.append((i, "abstract_cn", p["abstract"][:1500]))
            else:
                p["abstract_cn"] = ""
        elif DEEPSEEK_API_KEY and p.get("title") and p.get("abstract"):
            merged_tasks.append((i, p["title"], p["abstract"][:2000]))
        else:
            if p.get("title"):
                single_tasks.append((i, "title_cn", p["title"]))
            else:
                p["title_cn"] = ""
            if p.get("abstract"):
                single_tasks.append((i, "abstract_cn", p["abstract"][:1500]))
            else:
                p["abstract_cn"] = ""

    total_tasks = len(single_tasks) + len(merged_tasks)
    if total_tasks == 0:
        print("  All papers already translated, skipping.", file=sys.stderr)
    else:
        merged_saved = len(merged_tasks)  # 每个 merged 省一次 API 调用
        print(f"  Translating {total_tasks} calls "
              f"(merged {merged_saved} title+abstract pairs, saved {merged_saved} calls) "
              f"with {workers} workers...", file=sys.stderr)
        done = 0

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures: dict = {}
            for idx, field, text in single_tasks:
                futures[pool.submit(translate_text, text)] = ("single", idx, field)
            for idx, title, abstract in merged_tasks:
                futures[pool.submit(_translate_merged, title, abstract)] = ("merged", idx, None)

            for future in as_completed(futures):
                task_type, idx, field = futures[future]
                try:
                    if task_type == "single":
                        papers[idx][field] = future.result()
                    else:
                        title_cn, abs_cn = future.result()
                        papers[idx]["title_cn"] = title_cn
                        papers[idx]["abstract_cn"] = abs_cn
                except Exception as e:
                    print(f"  Translation error [{idx}]: {e}", file=sys.stderr)
                    if task_type == "single":
                        papers[idx][field] = papers[idx].get(field, "")
                    else:
                        papers[idx].setdefault("title_cn", "")
                        papers[idx].setdefault("abstract_cn", "")

                done += 1
                if done % 100 == 0:
                    print(f"    Progress: {done}/{total_tasks}", file=sys.stderr)

    # Step 3: 附加主题中文翻译（强制覆盖，确保非英文 fallback）
    for p in papers:
        pt = p.get("primary_topic", "")
        if pt:
            cn = topic_cache.get(pt, "")
            if cn and cn != pt:
                p["primary_topic_cn"] = cn
            elif not p.get("primary_topic_cn"):
                p["primary_topic_cn"] = ""
        # 始终重建 all_topics_cn，确保不会残留英文 fallback
        p["all_topics_cn"] = [topic_cache.get(t, t) for t in p.get("all_topics", [])]

    return papers

