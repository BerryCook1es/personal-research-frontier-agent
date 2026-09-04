# Personal Research Frontier Agent

面向博士生的个人前沿论文追踪系统：多源发现 → 增量去重 → 关键词粗召回 → 可选语义筛选 → 可选 LLM 科研判断 → 个性化排序 → 中英双语科研周报 → 阅读反馈 → SQLite 长期状态。

本项目基于 `shoucunren-tsy/frontier-tracker-LIS` 的 MIT 许可实现进行重构，复用了其 CrossRef 按 ISSN 抓取、OpenAlex 摘要回填、术语保护翻译、多格式输出和交互页面设计。出处与许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [LICENSE](LICENSE)。本仓库不会修改或向原作者仓库提交内容。

## 能回答什么

对每篇候选论文，系统保存并展示：相关研究方向、当前项目、研究问题、方法、主要贡献、推荐理由、可迁移用途、0–100 相关性、A/B/C/D/Ignore 优先级和阅读建议。LLM Judge 关闭时会退化为明确标注的关键词优先级，不伪装成深度判断。

## 架构

```text
CrossRef journals + proceedings
              │
              ▼
      DOI / title-hash dedupe ─────► SQLite papers + runs
              │
              ▼
   Stage 1 Keyword Recall (命中证据)
              │
              ▼
   Stage 2 Embedding Ranker (可关闭)
              │
              ▼
   Stage 3 LLM Research Judge (可关闭、重试、checkpoint)
              │
              ▼
    Capacity-aware A/B/C ranking
              │
              ├── bilingual HTML brief
              ├── Excel dashboard
              ├── interactive feedback app
              ├── Markdown notes
              └── Markdown terminal preview
                         │
                         ▼
          feedback.json → SQLite feedback
```

主程序只负责组合模块；实际职责位于 `research_frontier_agent/providers/`、`screening/`、`translation/`、`storage/` 和 `render/`。

## 第一次运行

Windows PowerShell：

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config.example.json config.local.json
.venv\Scripts\python.exe -X utf8 scripts/frontier_tracker.py --config config.local.json
```

`config.example.json` 默认关闭 Embedding、LLM Judge 和翻译，因而无需 Key 也能完成 CrossRef → Keyword → HTML/App/Excel/Notes。建议第一次把 `days` 临时设为 1、把 `max_per_venue` 设为 5，确认网络与输出后再恢复。

## 配置 API

`config.local.json` 已加入 `.gitignore`。核心代码不读取环境变量；所有敏感配置都显式传入：

```json
{
  "embedding_enabled": true,
  "embedding_backend": "openai-compatible",
  "embedding_model": "your-embedding-model",
  "embedding_api_base": "https://your-provider.example/v1",
  "embedding_api_key": "REPLACE_LOCALLY",
  "llm_judge_enabled": true,
  "llm_model": "your-chat-model",
  "api_base": "https://your-provider.example/v1",
  "api_key": "REPLACE_LOCALLY",
  "temperature": 0.1,
  "translation_enabled": true,
  "translation_backend": "openai-compatible",
  "translation_model": "your-chat-model",
  "translation_api_base": "https://your-provider.example/v1",
  "translation_api_key": "REPLACE_LOCALLY"
}
```

Semantic Scholar 发现配置使用独立 Key：

```json
{
  "data_sources": ["crossref", "semantic_scholar"],
  "semantic_scholar_api_base": "https://api.semanticscholar.org/graph/v1",
  "semantic_scholar_api_key": "REPLACE_LOCALLY",
  "semantic_scholar_queries": {
    "scholarly-kg-llm": ["scientific knowledge graph", "scientific information extraction"]
  },
  "semantic_scholar_max_results": 100,
  "semantic_scholar_request_sleep": 1.1,
  "semantic_scholar_request_retries": 5
}
```

查询按 Profile 选择，并用 `publicationDateOrYear` 限制本次日期窗口。默认查询间隔 1.1 秒，以适配新 API Key 常见的 1 RPS 初始额度；遇到 429 会进行最多 5 次指数退避重试。bulk search 返回后还会在客户端严格执行 `semantic_scholar_max_results` 上限，避免宽泛查询产生过多后续 LLM 调用。

OpenAI-compatible 地址既可填写 API 根地址（推荐，如 `https://api.siliconflow.cn/v1`），也可填写完整的 `/chat/completions` 或 `/embeddings` 端点；程序会规范化后调用正确资源。聊天与翻译请求发往 `chat/completions`，Embedding 请求发往 `embeddings`。

本地 BGE-M3 / sentence-transformers 模式：额外安装 `sentence-transformers`，设置 `embedding_backend` 为 `sentence-transformers`、`embedding_model` 为本地路径或模型标识。模型不可用时本次运行自动回退到关键词阶段并记录错误，不会报废整个流水线。

## 三个 Profile

```powershell
python -X utf8 scripts/frontier_tracker.py --profile references/profile-scholarly-kg-llm.md --days 7 --enrich --embedding --llm-judge --output-modes html excel app notes
python -X utf8 scripts/frontier_tracker.py --profile references/profile-scientometrics-evaluation.md --days 7 --enrich --embedding --llm-judge --output-modes html excel app notes
python -X utf8 scripts/frontier_tracker.py --profile references/profile-human-ai-algorithm.md --days 7 --enrich --embedding --llm-judge --output-modes html excel app notes
```

也可在 `config.local.json` 中切换 `profile`。每个 Profile 的扫描、筛选、判断和最终输出均包含 profile name，例如：

- `outputs/reports/frontier_weekly_bilingual_scholarly-kg-llm_2026-09-03.html`
- `outputs/excel/frontier_dashboard_scholarly-kg-llm_2026-09-03.xlsx`
- `outputs/app/frontier_app_scholarly-kg-llm_2026-09-03/`
- `outputs/notes/scholarly-kg-llm/2026-09-03/`
- `outputs/codex/frontier_preview_scholarly-kg-llm_2026-09-03.md`

## Project Context

Research Profile 表示长期、较宽的研究兴趣；Project Context 表示你正在推进的某一项具体工作，例如一篇投稿、一章博士论文或一个实验。它会告诉 Judge：当前研究问题是什么、正在用什么方法、卡在哪里，以及最近特别需要追踪什么。Project Context 是可选项；`projects: []` 时系统仍会正常运行，只是不做“与当前项目的直接关联”判断。

复制模板并填写：

```powershell
Copy-Item references/projects/project-template.md references/projects/structgraph.md
python -X utf8 scripts/frontier_tracker.py --profile references/profile-scholarly-kg-llm.md --project references/projects/structgraph.md --days 7 --llm-judge --output-modes html app
```

`--project` 可重复传入。Judge 会在 `related_project` 和 `potential_use` 中说明最适合 Related Work / Method / Experiment / Discussion / New Idea 的位置。

## 输出与反馈

### 排除不想追踪的期刊

在 `config.local.json` 中设置 `"excluded_journals": ["PLOS ONE"]`。
该规则对三个 Profile、所有发现源及读取扫描检查点的运行统一生效，在入库和科研分析之前过滤。
期刊名称匹配忽略大小写、空格和标点；PLOS ONE 还通过其专属 DOI 前缀补充识别，不排除其他 PLOS 期刊。
已有数据库历史与阅读反馈不会被删除。修改配置不会自动重写以前生成的报告。

交互 App 可编辑 1–5 星、`reading_status`、note 和 related project；浏览器把数据保存在 localStorage，并可下载 `feedback.json`：

```powershell
python -X utf8 scripts/import_feedback.py path\to\feedback.json
```

状态支持 `new`、`saved`、`reading`、`read`、`ignored`、`cited`。数据库位于 `state/frontier.db`，不提交 Git。

## Provider 状态

- CrossRef：已实现期刊 ISSN 查询和会议 proceedings 名称查询，含 timeout、重试、错误隔离。
- OpenAlex：已实现 DOI 批量 enrichment（摘要重建、主题标签）。
- arXiv：TODO；Provider 接口已具备，不返回假数据。
- Semantic Scholar：已实现 Academic Graph bulk search、日期过滤、`x-api-key` 认证、限流间隔、字段规范化和跨源 DOI/title 去重合并。

会议 watchlist 已覆盖 ACL、EMNLP、NAACL、COLING、SIGIR、CIKM、WWW、ISWC、ESWC、AAAI、IJCAI、KDD。CrossRef 对会议论文的登记并不完整，运行结果会真实反映其覆盖；Semantic Scholar 已用于扩展会议覆盖，后续再由 arXiv Provider 补齐预印本。

## 期刊与 ISSN

新增的 KBS、Information Sciences、ESWA、DKE、TOIS、TKDE、TIST、Artificial Intelligence 均在 2026-09-03 通过 CrossRef `/journals/{issn}` 精确核验。未核验的候选不进入 `references/journal-watchlist.json`。

## 开发与测试

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 -m compileall -q research_frontier_agent scripts tests
```

测试使用本地 fake provider / embedding / LLM / translator，不伪造生产输出，也不消耗 API 配额。
