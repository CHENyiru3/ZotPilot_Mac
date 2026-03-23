# Changelog

## 如何更新 / How to Update

**推荐：一条命令更新 CLI 和 skill · Recommended: one command**
```bash
zotpilot update
```
自动探测安装方式（uv / pip），同时更新所有平台的 skill 目录。
Detects your installer (uv / pip) and updates all skill directories automatically.

```bash
zotpilot update --check      # 检查是否有新版本，不安装 / check only, no install
zotpilot update --dry-run    # 预览操作，不执行 / preview actions, no changes
zotpilot update --cli-only   # 只更新 CLI / CLI only
zotpilot update --skill-only # 只更新 skill 目录 / skill dirs only
```

**手动更新 · Manual**

```bash
# pip / uv 安装 · pip or uv install
uv tool upgrade zotpilot
# or / 或
pip install --upgrade zotpilot

# git clone 安装（editable / skill 目录）· git clone install
cd ~/.claude/skills/zotpilot   # 替换为你的实际路径 / replace with your path
git pull
```

---

## [0.3.1] - 2026-03-23

### 新功能 / New Features
- **`status --json` 新增 version 字段**：方便脚本和 agent 获取当前版本号
  **`status --json` adds version field**: Makes it easy for scripts and agents to check the installed version
- **`--version` flag**：`zotpilot --version` 输出版本号
  **`--version` flag**: `zotpilot --version` prints the version
- **Cursor / Windsurf 升级为 Tier 1**：支持 Skill 目录安装，与 Claude Code / Codex / Gemini CLI 同级
  **Cursor / Windsurf upgraded to Tier 1**: Skill directory support, on par with Claude Code / Codex / Gemini CLI

### 修复 / Fixes
- **Windows 升级友好提示**：`zotpilot update` 在 Windows 遇到文件锁定（MCP server 运行中）时，输出清晰的提示而非原始错误
  **Windows upgrade friendly error**: `zotpilot update` shows a clear message when the executable is locked by a running MCP server
- **收窄异常类型**：`_detect_cli_installer` 中 `except Exception` 改为 `except (KeyError, TypeError)`
  **Narrower exception handling**: `_detect_cli_installer` catches specific exceptions instead of bare `Exception`
- **路径比较安全性**：改用 `Path.is_relative_to()` 替代字符串前缀匹配，避免误判
  **Safer path comparison**: Uses `Path.is_relative_to()` instead of string prefix matching
- **文件编码显式指定**：所有 `open()` 调用统一加 `encoding="utf-8"`，修复 Windows 非 UTF-8 locale 问题
  **Explicit file encoding**: All `open()` calls now specify `encoding="utf-8"` for Windows compatibility
- **ruff lint 全部修复**，CI green
  **All ruff lint errors fixed**, CI green
- **mypy 类型检查通过**（per-module overrides 抑制历史问题）
  **mypy type checking passes** (per-module overrides suppress legacy issues)

### 文档 / Docs
- **SKILL.md 重构**：精简主文件至 ~120 行，安装配置内容迁移至 `references/setup-guide.md`；新增 ingestion 工具和文献库分类建议 workflow
  **SKILL.md refactor**: Concise main file (~120 lines), setup content moved to `references/setup-guide.md`; added ingestion tools and library classification advisor workflow
- **README 中英文对齐**：统一 Write 工具分组、Admin 工具计数、写操作配置流程、skills 目录表、数据存储路径
  **README zh/en alignment**: Unified write tool grouping, admin tool count, write ops config flow, skills directory table, data storage paths
- **Windows PATH 提示**：Troubleshooting 表格新增 Windows PATH 配置说明
  **Windows PATH hint**: Troubleshooting table adds Windows PATH configuration info

---

## [0.3.0] - 2026-03-23

### 新功能 / New Features
- **一键更新命令**：新增 `zotpilot update` 子命令，自动探测安装方式（uv / pip / editable）并完成 CLI 和所有平台 skill 目录的升级
  **One-command update**: New `zotpilot update` subcommand — auto-detects your installer (uv / pip / editable) and upgrades the CLI and all platform skill directories in one step
- 支持 `--check`（查版本不安装）、`--dry-run`（预览不执行）、`--cli-only`、`--skill-only` 四个标志
  Supports `--check` (version check only), `--dry-run` (preview without changes), `--cli-only`, `--skill-only`
- Skill 目录升级前自动检查：跳过符号链接、脏工作树、非 ZotPilot 仓库，不会误操作非相关目录
  Skill dir upgrade safety: automatically skips symlinks, dirty trees, and non-ZotPilot repos before running `git pull`

---

## [0.2.1] - 2026-03-23

### 新功能 / New Features
- **论文摄取**：新增从 Semantic Scholar 搜索并一键导入 Zotero 的工具，自动获取元数据和开放获取 PDF
  **Paper Ingestion**: New tools to search Semantic Scholar and import papers directly into Zotero with metadata and open-access PDFs (`search_academic_databases`, `add_paper_by_identifier`, `ingest_papers`)
- **配置管理命令**：新增 `zotpilot config set/get/list/unset/path` 子命令，无需手动编辑 JSON 文件
  **Config CLI**: New `zotpilot config set/get/list/unset/path` subcommands — no more manual JSON editing
- **Semantic Scholar API key 支持**：设置 `S2_API_KEY` 环境变量可提升请求频率限制
  **Semantic Scholar API key**: Set `S2_API_KEY` env var for higher rate limits

### 修复 / Fixes
- **API key 优先级修正**：环境变量现在优先于配置文件（更安全，推荐通过环境变量传递 key）
  **API key priority fix**: Environment variables now take precedence over config file (more secure)

---

## [0.2.1] - 2026-03-19 (pre-release)

### Added
- `switch_library` tool — list available libraries (user + groups) or switch active library context
- `get_annotations` tool — read highlights and comments via Zotero Web API (requires ZOTERO_API_KEY)
- `_get_api_reader()` singleton in state.py for annotation reads
- Tool count: 30 → 32

---

## [0.2.0] - 2026-03-19

### 新功能 / New Features
- **No-RAG 模式**：将 `embedding_provider` 设为 `"none"` 可在不配置 embedding 的情况下使用元数据搜索、笔记、标签等基础功能
  **No-RAG mode**: Set `embedding_provider: "none"` to use metadata search, notes, and tags without configuring an embedding provider

### Added (technical)
- `_get_store_optional()` pattern in state.py for graceful degradation
- Citation tools fall back to SQLite for DOI lookup when vector store unavailable

---

## [0.1.5] - 2026-03-19

### Added
- `get_feeds` tool — list RSS feeds or get feed items (SQLite, no API key needed)
- Tool count: 29 → 30

---

## [0.1.4] - 2026-03-19

### 新功能 / New Features
- **笔记工具**：新增读取笔记（`get_notes`）和创建笔记（`create_note`，需要 ZOTERO_API_KEY）
  **Notes tools**: Added `get_notes` (read) and `create_note` (write, requires ZOTERO_API_KEY)
- **高级元数据搜索**：新增 `advanced_search`，支持按年份、作者、标签、集合等多条件筛选，无需建索引
  **Advanced search**: New `advanced_search` tool — filter by year, author, tag, collection, DOI, etc. Works without indexing

### Added (technical)
- Tool count: 26 → 29

---

## [0.1.3] - 2026-03-19

### Changed
- Batch tools consolidated: `batch_tags(action="add|set|remove")` and `batch_collections(action="add|remove")` — tool count 29 → 26
- All tool docstrings slimmed significantly for faster LLM context usage

---

## [0.1.2] - 2026-03-19

### 新功能 / New Features
- **查询缓存**：相同查询不再重复调用 embedding API，搜索更快
  **Query cache**: Identical queries no longer call the embedding API twice — faster search
- **批量操作工具**：支持批量打标签、批量加入/移出集合（最多 100 条）
  **Batch write tools**: Bulk tag and collection operations (up to 100 items)

### Removed
- Built-in Chinese→English query translation removed — bilingual search is now the Agent's responsibility

---

## [0.1.1] - 2026-03-19

### 修复 / Fixes
- Thread safety: all singleton initializers use double-checked locking
- ReDoS vulnerability in title_pattern regex fixed
- API key no longer printed to terminal during setup
- Collection cache now invalidated after write operations

---

## [0.1.0] - 2026-03-16

### 新功能 / New Features
- **初始版本**：ZotPilot 首次发布，提供 26 个 MCP 工具，支持语义搜索、索引、引用图谱和文献库管理
  **Initial release**: 26 MCP tools for semantic search, indexing, citations, and library management
- Gemini and local embedding providers
- Section-aware reranking with journal quality weighting
- PDF extraction with table, figure, and OCR support
