# Changelog

## 如何更新 / How to Update

```bash
zotpilot update              # 自动探测安装方式，更新 CLI + skill 目录
zotpilot update --check      # 只查版本，不安装
zotpilot update --dry-run    # 预览操作，不执行
```

手动更新：`uv tool upgrade zotpilot` 或 `pip install --upgrade zotpilot`

---

## [0.5.0] - 2026-04-11

**架构重构版本 / Architectural refactor** — 不破不立，彻底简化入库路由、工具层和 skill 系统。

### ✨ Highlights
- **入库路由 Plan C**：Connector save → 本地 API 验证 → DOI API fallback，彻底解决 IEEE/Springer translator 失败导致的 webpage snapshot 垃圾 item 问题
- **工具层从 33 → 18 个原子操作**：每个工具对应一个不可再分解的原子操作，从用户场景推导而非拍脑袋删减
- **Skill 系统重写**：4 个声明式 skill (`ztp-research` / `ztp-review` / `ztp-profile` / `ztp-setup`)，删除路由器 Skill，由平台原生机制根据 `description` 自动选择
- **代码量减少 30%**：~31,400 行 → ~22,000 行，测试覆盖率从 15.78% → 46.00%
- **仅支持三大 agent 平台**：Claude Code / Codex CLI / OpenCode（Gemini / Cursor / Windsurf 不再维护适配）

### Added
- **`ingest_by_identifiers`**：同步原子入库工具，内部完成 DOI/arXiv/URL 规范化 → 本地去重 → Connector preflight → 逐条 save + 即时验证 → 失败时 DOI API fallback → PDF 验证，返回每篇论文的最终状态（`saved_with_pdf` / `saved_metadata_only` / `blocked` / `duplicate` / `failed`）
- **`validate_saved_item`**：Connector save 后通过**本地 Zotero API (port 23119)** 即时验证 itemType + title，规避 Web API 同步延迟
- **`zotpilot upgrade` 命令**：一键升级 CLI + skill，`aliases=["update"]` 向后兼容
- **版本漂移检测**：MCP server 启动时检测已部署 skill 版本，不匹配时在 instructions 中提示运行 `zotpilot register`
- **OpenAlex 检索增强**：参数化 `min_citations`、cursor-based pagination，支持 `concepts` / `institutions` / `source` filter
- **arXiv DOI fast-path**：`10.48550/arXiv.xxx` 规范 DOI 自动路由到 arXiv API（CrossRef 不索引 arXiv DOI）

### Changed
- **Ingestion 子系统从 7 文件 3146 行 → 3 文件 ~1200 行**：
  - 新建 `tools/ingestion/connector.py`（~1100 行）— Connector 通信 + 验证 + DOI API fallback
  - 新建 `tools/ingestion/search.py`（~490 行）— OpenAlex 搜索 + query 构建
  - 重写 `tools/ingestion/__init__.py`（~330 行）— 只注册 2 个 MCP 工具
- **18 个 MCP 工具（从 33 精简）**：
  - `search_papers` 吸收 `search_tables` / `search_figures`（新增 `section_type` 参数）
  - `ingest_by_identifiers` 吸收 `save_urls`（URL 自动识别）
  - `manage_collections` 吸收 `create_collection`（`action="create"`）
  - `index_library` 吸收 `reindex_degraded`（`item_keys` 参数）
- **Skill 系统**：4 个 skill 替代原有 5 个，删除 `zotpilot` 路由器 skill（由平台原生机制处理），`ztp-research` 完整覆盖 4-Phase 流程（Discovery → Ingestion → Post-processing → Final Report）
- **平台支持收敛**：从 6 个平台降到 3 个（Claude Code / Codex / OpenCode），移除 Gemini / Cursor / Windsurf 适配代码

### Removed
- **10 个状态机 phase gate 工具**：`confirm_candidates` / `resolve_preflight` / `approve_ingest` / `get_batch_status` / `approve_post_ingest` / `authorize_taxonomy_changes` / `approve_post_process` — 全部删除，Agent 在 Skill 引导下通过 `action_required` 字段自然处理用户介入
- **整个 `tools/research_workflow.py`**（1202 行）— 状态机 MCP 工具层被 Skill 声明式编排替代
- **整个 `workflow/worker.py`**（660 行）— 后台 worker 线程模型被同步执行替代
- **`tools/ingest_state.py`**（427 行）— 旧的 `BatchStore` 系统，与 `workflow/batch.py` 合并为单一来源
- **`tools/ingestion_bridge.py`**（1654 行）— 拆分到 `tools/ingestion/connector.py`
- **`switch_library` MCP 工具**：v0.5.0 仅支持单文献库，多库切换推迟到未来版本
- **旧的 `skills/SKILL.md` 路由器** + **`skills/references/` 目录**：内容内化到工具逻辑和各 skill 硬规则
- **`test_research_workflow_*.py`** / **`test_post_process_gate.py`** 等依赖旧状态机的测试

### Fixed
- **40% Connector 垃圾率根治**：之前 Connector `success=True` 信号不可信，IEEE 等翻车 publisher 的 translator 会保存成 webpage snapshot；现在通过 `validate_saved_item` 检查 itemType + title，失败自动 delete 并走 DOI API fallback
- **item_key Web API 同步延迟竞态**：`validate_saved_item` 和 `_fetch_item_via_local_api` 使用本地 Zotero HTTP API (port 23119)，无需等待 Zotero Desktop → api.zotero.org 同步
- **`delete_item_safe` 加入重试退避**：Web API delete 针对刚 save 的 item 加入 0/5/10/15s 退避重试，处理 Zotero 同步延迟
- **arXiv DOI fallback 路由修复**：`identifier_resolver._resolve_doi` 识别 `10.48550/arXiv.xxx` 并路由到 arXiv API，避免 CrossRef 404

### Docs
- `docs/prd-v0.5.0.md` — 产品需求文档（重构动机、产品定位、工具表、任务分解）
- `docs/tech-design-v0.5.0.md` — 技术实施规格（入库路由决策、Task 级别的实施指令）
- `scripts/ingest_routing_test.py` — 入库路由基准测试脚本（可复用）

### Migration Notes
v0.5.0 从未发布到 PyPI，现有用户直接升级即可。使用新命令 `zotpilot upgrade` 一键同步 CLI + skill。Agent 在新版本中不再需要调用 `confirm_candidates` / `approve_ingest` 等 phase gate 工具——直接调用 `ingest_by_identifiers`，响应中 `action_required` 非空时停下等用户。

---

## [0.4.0] - 2026-03-24

### Added
- `bridge` CLI 子命令：`zotpilot bridge [--port N]` 手动启动 HTTP bridge 服务（为后续浏览器扩展集成做基础设施准备）

### Fixed
- pyzotero `url_params` 泄漏
- Zotero API `qmode` 参数修复

---

## [0.3.1] - 2026-03-23

### Added
- `status --json` 新增 version 字段
- `--version` flag
- Cursor / Windsurf 升级为 Tier 1

### Fixed
- Windows `zotpilot update` 文件锁定时输出友好提示
- 收窄异常类型、路径比较安全性、文件编码显式指定
- ruff lint / mypy 全部通过

---

## [0.3.0] - 2026-03-23

### Added
- `zotpilot update` 一键更新命令，自动探测安装方式（uv / pip / editable），同时更新 CLI 和所有平台 skill 目录
- `--check` / `--dry-run` / `--cli-only` / `--skill-only` 标志
- Skill 目录升级安全检查：跳过符号链接、脏工作树、非 ZotPilot 仓库

---

## [0.2.1] - 2026-03-23

### Added
- 论文摄取：`search_academic_databases`、`add_paper_by_identifier`、`ingest_papers`（Semantic Scholar 搜索 + Zotero 导入）
- `config` CLI 子命令：`set` / `get` / `list` / `unset` / `path`
- Semantic Scholar API key 支持（`S2_API_KEY`）
- `switch_library` 工具：切换用户/群组文献库
- `get_annotations` 工具：读取高亮和评论

### Fixed
- API key 优先级：环境变量现在优先于配置文件

---

## [0.2.0] - 2026-03-19

### Added
- No-RAG 模式：`embedding_provider: "none"` 可在不配置 embedding 的情况下使用元数据搜索、笔记、标签等基础功能

---

## [0.1.5] - 2026-03-19

### Added
- `get_feeds` 工具：列出 RSS 订阅或获取订阅条目

---

## [0.1.4] - 2026-03-19

### Added
- `get_notes` / `create_note` 笔记工具
- `advanced_search` 高级元数据搜索（年份/作者/标签/集合等，无需索引）

---

## [0.1.3] - 2026-03-19

### Changed
- 批量工具合并：`batch_tags(action="add|set|remove")`、`batch_collections(action="add|remove")`，工具数 29 → 26
- 所有工具 docstring 精简

---

## [0.1.2] - 2026-03-19

### Added
- 查询缓存：相同查询不再重复调用 embedding API
- 批量写操作工具（最多 100 条）

### Removed
- 内置中英翻译（改由 Agent 负责）

---

## [0.1.1] - 2026-03-19

### Fixed
- 线程安全：所有单例初始化使用双重检查锁
- ReDoS 漏洞修复
- API key 不再打印到终端
- Collection 缓存在写操作后正确失效

---

## [0.1.0] - 2026-03-16

### Added
- 初始版本：26 个 MCP 工具
- Gemini / Local 嵌入提供方
- 章节感知重排序 + 期刊质量加权
- PDF 提取（文本 + 表格 + 图表 + OCR）
