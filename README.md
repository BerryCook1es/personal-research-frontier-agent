# Frontier Tracker · 前沿论文周报追踪

个性化顶刊文献监控流水线——从 46 本目标期刊自动抓取新论文，按 8 个研究方向池分级筛选，生成中英双语周报及多种格式输出。

## 功能概览

1. **扫描** — CrossRef API 按 ISSN + 日期抓取，免费、无需 API Key
2. **筛选** — 对照自定义研究 Profile 的关键词，分为 core / proxy / eco / other 四档
3. **翻译** — DeepSeek API（含 63 条学术术语保护，自动级联 Ollama / Google），生成中英双语内容
4. **输出** — 五种格式：双语 HTML 报告、Excel 仪表盘、交互 HTML 表格、Markdown 笔记、终端预览

## 快速上手

### 1. 克隆后初始化

```bash
# 安装依赖
pip install -r requirements.txt

# 配置翻译 API（可选但推荐，否则用 Google 翻译）
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key（https://platform.deepseek.com 免费注册）

# 复制个人 Profile（关键词匹配规则）
cp references/example-profile.md references/patent-biblio-profile.md
# 编辑 profile，替换为自己的研究关键词

# 复制期刊 Watchlist
cp outputs/data/custom_watchlist.example.json outputs/data/custom_watchlist.json
# 编辑 watchlist，增删期刊或调整研究方向池
```

### 2. 运行

```bash
cd frontier-tracker-顶刊前沿论文追踪（结合自身修改）

# 一键运行（默认最近 7 天，仅生成双语 HTML 报告）
python -X utf8 scripts/frontier_tracker.py

# 30 天窗口 + 全格式输出
python -X utf8 scripts/frontier_tracker.py --days 30 --output-modes html excel app notes codex

# 跳过翻译（无需 VPN）
python -X utf8 scripts/frontier_tracker.py --skip-translate

# 跳过扫描，使用已有数据
python -X utf8 scripts/frontier_tracker.py --skip-scan --scan-file outputs/data/frontier_scan_<date>.json
```

> Windows 下务必使用 `python -X utf8`，否则中文期刊名/论文标题会触发 GBK 编码错误。

## 输出格式

| 格式 | 命令参数 | 输出位置 | 说明 |
|------|----------|----------|------|
| 双语 HTML 报告 | `html` | `outputs/reports/` | 中英对照，四级分类着色，池来源标记 |
| Excel 仪表盘 | `excel` | `outputs/excel/` | 多 Sheet（Summary/Core/Proxy/Eco/All），条件格式，DOI 超链接 |
| 交互 HTML 表格 | `app` | `outputs/app/` | 搜索+筛选单页应用，无需服务器 |
| Markdown 笔记 | `notes` | `outputs/notes/` | 每篇论文一个 .md，YAML frontmatter，按 tier 分目录 |
| 终端预览 | `codex` | `outputs/codex/` | Markdown 表格，同时打印到 stdout |

## 项目结构

```
frontier-tracker/
├── scripts/
│   ├── _lib.py                     # 共享库（API、筛选、翻译引擎）
│   ├── frontier_tracker.py         # 统一入口（扫描→筛选→翻译→输出）
│   ├── scan_crossref.py            # CrossRef 期刊扫描（可独立运行）
│   ├── screen_by_profile.py        # 关键词筛选（可独立运行）
│   ├── render_bilingual_report.py  # 双语 HTML 报告渲染（可独立运行）
│   ├── render_outputs.py           # 多格式输出渲染（可独立运行）
│   └── generate_user_guide.py      # 生成使用教程 .docx
├── references/
│   └── patent-biblio-profile.md    # 研究兴趣关键词（core/proxy/eco 三级）
├── outputs/
│   ├── data/                       # 中间数据 JSON（gitignored）
│   ├── reports/                    # HTML 报告
│   ├── excel/                      # Excel 仪表盘
│   ├── app/                        # 交互 HTML 表格
│   ├── notes/                      # Markdown 笔记
│   └── codex/                      # 终端预览
├── state/                          # 持久化状态（gitignored）
├── SKILL.md                        # Skill 使用说明
├── README.md
└── LICENSE
```

## 配置

### 研究 Profile

编辑 `references/patent-biblio-profile.md`，在 `## Core keywords`、`## Proxy keywords`、`## Eco-context keywords` 下用 `- keyword` 格式维护关键词。修改后无需改代码，下次运行自动生效。

### 期刊 Watchlist

编辑 `outputs/data/custom_watchlist.json`，每条记录包含：

```json
{
  "journal": "Journal Name",
  "issn": "XXXX-XXXX",
  "family": "Parent/Family",
  "pool": "<patent-tech-mining | bibliometrics-evaluation | science-policy-innovation | info-methods-datamining | ai-usage-behavior | complex-network-analysis | knowledge-graph-semantic | comprehensive-high-impact>",
  "scope_note": "Brief note.",
  "source": "custom-watchlist"
}
```

ISSN 必须与 CrossRef 注册信息完全一致。

### 八个研究方向池（46 本期刊）

| 池 | 数量 | 研究方向 |
|----|------|----------|
| `patent-tech-mining` | 4 | 专利计量与技术挖掘 |
| `bibliometrics-evaluation` | 11 | 文献计量与科学评价 |
| `science-policy-innovation` | 5 | 科技政策与创新 |
| `info-methods-datamining` | 5 | 信息方法与数据挖掘 |
| `ai-usage-behavior` | 11 | AI使用行为 |
| `complex-network-analysis` | 3 | 复杂网络分析 |
| `knowledge-graph-semantic` | 2 | 知识图谱与语义 |
| `comprehensive-high-impact` | 5 | 综合高影响力 |

## 四级分类

| 级别 | 含义 | 报告中颜色 | 建议动作 |
|------|------|-----------|----------|
| Core | 直接相关 | 绿色 | 必读 |
| Proxy | 方法/邻近 | 黄色 | 浏览 |
| Eco | 背景上下文 | 蓝色 | 可选 |
| Noise | 无匹配 | 隐藏 | 跳过 |

## 依赖

- Python 3.10+
- 见 `requirements.txt`，一行安装：`pip install -r requirements.txt`
- 所有 API 调用使用 Python 内置 `urllib`，无需额外 HTTP 库

## 许可

MIT License — 见 [LICENSE](LICENSE)。

