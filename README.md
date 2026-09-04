# Personal Research Frontier Agent

当前版本：**v0.1.0-beta**。支持 Python 3.9+；建议新安装使用 Python 3.12。
这是可运行的公开测试版，不是完整覆盖所有文献来源的生产服务。

面向博士生的个人前沿论文追踪系统：多源发现 → 增量去重 → 关键词粗召回 → 可选语义筛选 → 可选 LLM 科研判断 → 个性化排序 → 中英双语科研周报 → 阅读反馈 → SQLite 长期状态。

本项目基于 `shoucunren-tsy/frontier-tracker-LIS` 的 MIT 许可实现进行重构，复用了其 CrossRef 按 ISSN 抓取、OpenAlex 摘要回填、术语保护翻译、多格式输出和交互页面设计。出处与许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [LICENSE](LICENSE)。本仓库不会修改或向原作者仓库提交内容。

## 能回答什么

对每篇候选论文，系统保存并展示：相关研究方向、当前项目、研究问题、方法、主要贡献、推荐理由、可迁移用途、0–100 相关性、A/B/C/D/Ignore 优先级和阅读建议。LLM Judge 关闭时会退化为明确标注的关键词优先级，不伪装成深度判断。

## 架构

```text
CrossRef journals + proceedings / Semantic Scholar
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
git clone https://github.com/BerryCook1es/personal-research-frontier-agent.git
cd personal-research-frontier-agent
git checkout v0.1.0-beta
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path config.local.json)) { Copy-Item config.example.json config.local.json }
.venv\Scripts\python.exe -X utf8 scripts/frontier_tracker.py --config config.local.json
```

`config.example.json` 默认关闭 Embedding、LLM Judge 和翻译，因而无需 Key 也能完成 CrossRef → Keyword → HTML/App/Excel/Notes。建议第一次把 `days` 临时设为 1、把 `max_per_venue` 设为 5，确认网络与输出后再恢复。

想先进行更小的联网检查，可以用下面的命令替代最后一行（不修改配置文件）：

```powershell
.venv\Scripts\python.exe -X utf8 scripts/frontier_tracker.py --config config.local.json --days 1 --max-per-journal 1 --pools scientific-knowledge-graph --no-enrich --output-modes html
```

Linux/macOS 使用 `python3 -m venv .venv`，之后将命令中的 Python 路径换为
`.venv/bin/python`，并在 config.local.json 不存在时执行
`cp -n config.example.json config.local.json`。所有命令在项目根目录运行。
退出码 0 表示流水线结束，不代表每个来源都成功：请检查终端 JSON 中的 `errors`
和各阶段降级信息。没有论文也可能只是窗口很短，不能当作抓取成功的充分证据。

## Skill 安装与使用

完整克隆仓库或解压 Release ZIP 后，在 Codex 中打开项目根目录。
仓库已提供 `.agents/skills/research-frontier-agent/SKILL.md` 自动发现入口，
它引用根目录 SKILL.md 的完整流程，避免维护两份不同的业务说明。
不需要把私人配置或整个项目复制到用户全局 Skill 目录。

在支持 Skill 选择的客户端选择 `research-frontier-agent`；CLI/IDE 可用
`$research-frontier-agent`。如果当前会话未刷新技能列表，重新打开项目或重启客户端。
也可以明确要求：“阅读本项目 SKILL.md，使用 scholarly-kg-llm Profile
追踪最近 7 天论文并生成 HTML。”首次运行仍需先安装依赖、创建本地配置。
只下载 SKILL.md，或只复制 `.agents/skills` 子目录到别处，不能独立运行。

加载目录与调用方式见 [官方 Skill 文档](https://learn.chatgpt.com/docs/build-skills)。
此版本是仓库级 Skill，不是已上架插件；`scripts/check_skill.py` 检查入口与链接，
不代替真实客户端中的选择/触发验收。

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
.venv\Scripts\python.exe -X utf8 scripts/frontier_tracker.py --config config.local.json --profile references/profile-scholarly-kg-llm.md --days 7 --output-modes html excel app notes
.venv\Scripts\python.exe -X utf8 scripts/frontier_tracker.py --config config.local.json --profile references/profile-scientometrics-evaluation.md --days 7 --output-modes html excel app notes
.venv\Scripts\python.exe -X utf8 scripts/frontier_tracker.py --config config.local.json --profile references/profile-human-ai-algorithm.md --days 7 --output-modes html excel app notes
```

可选阶段从配置读取；填写 API 后可追加 `--embedding --llm-judge --enrich`。
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
.venv\Scripts\python.exe -X utf8 scripts/frontier_tracker.py --config config.local.json --profile references/profile-scholarly-kg-llm.md --project references/projects/structgraph.md --days 7 --output-modes html app
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

HTML、Excel、App 展示全部已分类候选，方便筛选；阅读容量仅限制 Markdown
笔记与阅读清单/预览。评分和反馈目前用于保存、人工复盘，不会自动训练兴趣模型
或自动改写 Profile。Judge 分析基于题目与摘要，不等于读过全文。

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

GitHub Actions 在 Windows/Linux、Python 3.9/3.12 下执行测试、编译、Skill 入口
检查及发布文件/历史凭据扫描。不会把本地 Key 上传为 CI secrets，也不在 CI 调用付费 API。

## 本地运行与 GitHub 发布隔离

```text
项目根目录/
├── config.local.json       本地真实 Key，忽略、不导出
├── state/                  私人数据库，忽略、不导出
├── outputs/                本地报告与中间结果，忽略、不导出
├── references/projects/    私人项目，只有空模板允许公开
└── release/github/
    ├── v0.1.0-beta/         完整公开源码快照，无私人配置
    ├── v0.1.0-beta.zip      可分享安装包
    └── v0.1.0-beta.manifest.json  commit 与文件 SHA-256
```

发布目录由已提交的源码白名单生成，不参与 Git 跟踪，也不用于日常运行。
在工作目录修改源码、测试并提交后导出；不要手工维护两份源码。

```powershell
python -X utf8 scripts/build_release.py --check-only --history
python -X utf8 scripts/build_release.py --ref HEAD --version v0.1.0-beta
```

已有同名目录时导出器拒绝覆盖。ZIP 的内容与该 commit 一致；公开配置所有
API Key 均为空，填写位置在 README 用 `REPLACE_LOCALLY` 表示，不保留部分真实字符。
工具同时检查已知本地 Key 和常见 token 格式；这不是通用的秘密检测保证。
分享整个项目文件夹前仍需检查，优先只分享导出的 ZIP。

安全注意事项见 [SECURITY.md](SECURITY.md)，版本范围见 [CHANGELOG.md](CHANGELOG.md)。
