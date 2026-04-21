# 决策记录

## Install & Distribution Standardization (v0.5.0)

**Background**: v0.4.x used a clone-to-skills-directory install model with `scripts/run.py` as the primary entry point. This created inconsistent user experiences, made wheel packaging incomplete, and mixed user-facing and agent-facing workflows.

**Decision**:
- Distribution unified via PyPI / wheel
- Two first-time install paths: `uv tool install zotpilot` or `pip install zotpilot`
- Unified user entry: `zotpilot setup` / `zotpilot register` / `zotpilot upgrade`
- `zotpilot upgrade` auto-detects installer (uv/pip/editable) and upgrades accordingly
- `zotpilot upgrade --no-refresh-skills` skips skill refresh but keeps runtime reconcile
- Packaged skills (`src/zotpilot/skills/`) and references (`src/zotpilot/references/`) ship inside the wheel
- Root `SKILL.md` and `scripts/platforms.py` deleted; `scripts/run.py` becomes a tombstone shim
- Legacy clone detection is warn-only (no auto-delete)
- `ztp-setup.md` updated to match new CLI contract (agent skill, not user entry)

**Impact**: Users get a clean PyPI-first experience. Agent skills orchestrate CLI commands rather than replacing them. Wheel is self-contained with skills + references.

---

## Config / Runtime / Registration Unification (v0.6.0)

**Background**: v0.5.x left credentials split across `config.json`, environment variables, and embedded client MCP config. This made `setup / register / update / doctor` hard to reason about, caused client drift, and widened the secret exposure surface.

**Decision**:
- `Config.load()` now reads only shared non-sensitive config from `~/.config/zotpilot/config.json`
- Runtime secret resolution moves to a dedicated `resolve_runtime_settings()` layer
- `zotero_user_id` remains in shared config; true secrets move to ZotPilot-managed secure storage
- macOS uses Keychain first; explicit local-file fallback remains available
- `register` no longer writes embedded secrets into Codex / Claude / OpenCode client config
- Client MCP templates now target `zotpilot mcp serve`
- `config set` becomes the formal path for credential updates; `register --*-key` remains only as a thin compatibility layer
- `config migrate-secrets` is the single migration execution entrypoint; `update --migrate-secrets` only delegates

**Impact**: One stable user model: setup/config for configuration, register for client wiring, update for upgrades, doctor/status for explanation. Multi-client drift is reduced, and client config no longer stores secrets.

---


记录项目关键决策、理由、行动和时间。按时间倒序排列。

---

## 2026-04-18 | Bridge 认证改为 Origin 白名单 + Preflight 按 final_url 归类 publisher

### 背景

内测阶段发现两个真实 bug，同根：

1. **全部 Connector 保存 401**。源于 `f0d8c96`（2026-04-14 security audit）给 bridge 加了
   `X-ZotPilot-Token` header 强制校验。但该方案本身存在根本缺陷：`/status` 端点**不检查**
   auth 且直接返回 token，`Access-Control-Allow-Origin: *` 允许任何 origin 读取 —— 任何
   恶意网页两步 fetch 就能拿到 token 并调 `/enqueue`。既无安全价值，又给扩展 / bridge
   增加了必须同步的契约（扩展必须先 GET /status 拿 token、后续请求带 header）。
2. **Preflight 的 action_required 只报 publisher=`doi.org`**。源于 `_candidates_to_internal`
   为 OA 候选统一用 `https://doi.org/<doi>` 作 landing URL，所有候选 hostname 都是
   `doi.org`。Preflight 重定向后在真实 publisher（sciencedirect / projecteuclid 等）
   触发 anti-bot 时，`extract_publisher_domain` 取的是**原始 URL**，于是 blocked_domains
   只记 `doi.org`；衍生副作用：同批其他 OA 候选 URL 也都 `doi.org`，hostname 恰好匹配
   blocked_domains → 跟着一起被误判 preflight_blocked。

### 方案

**1. 用 Origin 白名单替换 token 方案**（`2bd002f`）

- 删除 `_check_auth` / `auth_token` / `secrets.token_hex` / `/status` 的 auth_token 字段
- 新增 `_check_origin`：
  - 空 Origin → 放行（CLI / MCP / curl 等非浏览器调用者不发 Origin header）
  - `chrome-extension://` / `moz-extension://` / `safari-web-extension://` → 放行
  - 其他任何 http(s) Origin、`null` → 403 `{"error": "forbidden_origin", "origin": ...}`
- `/status` 端点豁免 ACL（健康探测不必带 Origin）
- CORS `Allow-Origin` 改为动态回显被允许的 Origin（不再 `*`），`Allow-Headers` 去掉
  `X-ZotPilot-Token`
- 扩展侧 `agentAPI.js` 删除 `_fetchAuthToken` / header 注入相关代码

**2. Preflight 按 final_url 归类 publisher**（`0a2cc10`）

- `preflight_urls` 的错误路径现在也在 entry 里保留 `final_url` 字段（原本只有 blocked/
  accessible 路径有）
- `run_preflight_check` 构建 `url → final_url` 映射，供：
  - `blocked_domains` 用 final_url 的 hostname 做 key
  - 候选保留过滤通过 `_effective_url(candidate["url"])` 查 final_url 的 hostname
  - `blocked_publishers_details.publisher` 和 `sample_urls` 显示 final_url（用户能直接
    复制到浏览器打开真实页面验证）
- URL-scope blocks（timeout / preflight_failed）仍用原始 URL 做 key 以保持 filter 一致性，
  但对外显示时改用 final_url 的 hostname / URL

### 为什么 Origin ACL 安全模型足够

- 威胁目标：阻止**浏览器里打开的恶意网页**通过 CORS 调 `/enqueue` 让扩展把任意 URL
  存进你的 Zotero
- 浏览器对任何跨域 `fetch()` **强制附上 `Origin` header**，JS 不能伪造
- 非浏览器进程（CLI / MCP）不发 Origin，天然通过 —— 和 localhost 信任边界一致
- 恶意网页的 Origin 必然是 `http(s)://...`，规则直接拒
- 明确**不覆盖**的威胁：同机其他进程伪造 bridge、用户主动装恶意扩展（前者 localhost
  已经是信任边界，后者是用户输入验证问题，都不是 bridge 该防的）

### 为什么按 final_url 归类 publisher 是正确的

- `publisher` 的语义是"触发拦截的真实服务方"，不是"我们最初请求的 URL 的 hostname"
- doi.org 只是 301/302 跳板，几乎从不自己拦人
- 用户在 action_required 里看到 `sciencedirect.com` 才能一眼知道去哪个 Chrome tab 验证；
  看到 `doi.org` 毫无信息量
- 同批候选只要 final_url 不同，就不会因为原始 URL 恰好都是 doi.org 而相互连坐

### 影响

- **安全**：从"摆设"变成"真·防护"。恶意网页无法再调 `/enqueue`
- **用户可见**：`action_required` 的 `publishers` 列表从模糊的 `doi.org` 变为具体出版商
  名；`sample_urls` 可直接打开
- **无共享 secret**：扩展和 bridge 可独立升级，不再有"f0d8c96 改 bridge + 主仓库扩展，
  但 fork 扩展没同步"那种契约断层
- **对 CLI / MCP / curl 使用者透明**：不发 Origin 即放行

### 关联事实：connector/ 仓库结构

`/Users/zxd/zotpilot-connector`（独立 git 仓库，最后 commit 2026-03-28）是当前 `connector/`
子目录的**前身**。目前主仓库 `connector/`（git-tracked，195 文件）才是真相源；fork 仅作
历史归档，不应再在该目录内做开发或构建。任何扩展侧修改都应改主仓库 `connector/src/` 然后
`cd connector && ./build.sh -d` 构建到 `connector/build/manifestv3/`，Chrome 直接从该路径
以 unpacked 加载即可。fork 目录可以安全归档或删除，今后避免误读为"另一份 source"。

---

## 2026-04-15 | Preflight 升级为 mandatory gate + 分级 blocking

**背景**：Science 论文（`10.1126/science.abj8754`）的 anti-bot 在预检阶段未被检测到，
连带同批 CrossViT 被标记为 `batch_halted_by_anti_bot`。根因有二：
(1) `run_preflight_check` 只采样 5 个 URL，Science 没被抽到；
(2) blocking 策略仅覆盖 `anti_bot_detected`，timeout / subscription / 未知失败一律放行。

**方案**：
1. 取消采样：`run_preflight_check` 对全部 URL 执行预检
2. **预检升级为 mandatory gate**：只有 `accessible` 状态的 URL 进入 save 阶段
3. 分级 blocking：
   - 站点级信号（`anti_bot_detected` / `subscription_required`）→ 封整个 publisher 域
   - 页面级信号（`preflight_timeout` / `preflight_failed`）→ 仅封该 URL，同域其他 candidate 放行
4. 任一类阻断都触发 batch halt（`blocking_dict` 非 None），让用户介入
5. `blocked_publishers_details[*]` 新增 `scope: "publisher" | "url"` 字段；`error_code` 从硬编码
   `"anti_bot_detected"` 改为反映真实归类

**为什么 timeout / preflight_failed 不封域**：
IEEE Xplore / Springer 等 SPA 页面 hydration 较慢，单次 timeout 不构成"出版商不可用"
的充分证据。封域会导致同出版商无关条目无法保存。若 timeout 真因 anti-bot，title /
error_message 会被 `_classify_preflight_error_code` 重分类为 `anti_bot_detected`，
照常封域。`preflight_failed` 同理——信号不明，但仍拒绝放行该 URL（preflight 已给出
非 accessible 判决，继续 save 是对失败信号的无视；save 失败的代价更大：占 Connector
tab、可能在 Zotero 留快照/错误条目）。

**影响**：
- `remaining` 的语义变干净：等价于 preflight `accessible` 列表对应的 candidates
- API 响应增加 `scope` 字段，旧消费者需兼容（建议默认值 `"publisher"` 兼容旧行为）
- 大批次预检耗时增加（无采样），但 `preflight_urls` polling 是并发的，影响有限

---

## 2026-04-14 | MCP 开发注册改为 `uv run --directory` 源码模式

**背景**：`zotpilot register` 默认写入 `~/.local/bin/zotpilot`（`uv tool install` 的隔离副本），与源码目录完全无关。开发时修改 `src/` 下的代码对正在运行的 MCP server 没有任何影响，必须重新 `uv tool install` 才能生效，严重拖慢 dev → test 循环。

**方案**：为 `zotpilot register` 新增 `--dev [SOURCE_DIR]` flag，写入 `uv run --directory <repo> zotpilot` 代替二进制路径。`--dev` 无参数时自动探测 repo 根目录。不加 `--dev` 时行为与之前完全一致，不影响普通用户。变更范围：`_platforms.py`（`DesiredRuntime.source_dir`、6 个注册函数、`reconcile_runtime`、`register`）和 `cli.py`（argparse + `cmd_register`）。

**影响**：开发循环简化为"改源码 → `/mcp` 重启 → 立即生效"，无需重新安装。仅本地 dev 环境使用，PyPI 发布包行为不变。同时将 `.claude.json` 中的注册命令从安装二进制修正为 `uv run --directory /Users/zxd/ZotPilot zotpilot`。

---

## 2026-04-08 | Batch-Centric Workflow Redesign：删除 ResearchSession，Phase 状态机替代旁路 Gate

### 背景

v0.5.0 的 `ResearchSession` + `SessionStore` + Gate 1/2/3 三层 guardrail 在 4 次迭代后仍然无法可靠地保护 research 流程。根因：流程本体活在 SKILL 散文里,Python 只做旁路检查,agent 走神或 SKILL 改错字就串戏。2026-04-08 incident replay 测试表明 agent 可以绕过所有 3 个 gate。

经过 deep-interview（4 轮 Q&A）+ ralplan consensus（2 轮 Planner/Architect/Critic）+ Codex external review（5 轮,共 20 条 finding）的反复打磨,确立了新的 batch-centric 架构。

### 决策

**ADR-2026-04-08：三层 ingest workflow + runtime-asserted phase state machine**

用四层架构替换旧的 Skills/Guardrail/MCP Tools：

1. **SKILL 叙述层**：`ztp-research.md` 只含叙述/prompt 模板,零控制流(P9 drift guard 自动化守护)
2. **MCP 适配层**：`tools/research_workflow.py` 作为薄 adapter,10 个 `@mcp.tool`,每个返回 `next_action`
3. **Workflow Core**：`workflow/batch.py` 拥有不可变 `Batch` + 15-phase `_ALLOWED_TRANSITIONS` 状态机 + 16 条 runtime-asserted properties (P1-P16)
4. **Domain Tools**：搜索/引用/浏览/写操作等领域能力(不变)

### 关键设计决定

| 决定 | 理由 |
|---|---|
| 删除 `ResearchSession` / `SessionStore` / `workflow.py` | 旧 session 机制同时承载"研究意图"和"ingest 事务",职责混淆;Batch 是唯一事务单位 |
| 5 个 checkpoint (CP1a/CP1b/CP2/CP2.5/CP3) | 用户明确拒绝了"减到 1 个 checkpoint"的方案,要求每个边界可预测 |
| Phase 状态机替代旁路 gate | 旧 gate(3-check approve 序列 + `last_get_at` + `checkpoint_reached_at`)是可被 agent 绕过的 runtime 检查;新 `_ALLOWED_TRANSITIONS` + worker 入口 assert 在类型/运行时双重阻断 |
| `next_action` 是输出契约不是服务器闸门 | MCP server 无 session correlation ID,无法强制 agent 按顺序调 tool;真正的强制来自状态机 runtime assert |
| `ingestion.py` → `ingestion/` package | 旧 1302 行单文件违反 coding-style.md 800 LOC 上限;package split + 子模块 LLOC ≤ 800 |
| Taxonomy 新建必须经 CP2.5 授权 | 用户诉求:优先复用已有 tag/collection 体系,新建/重构需显式授权 |
| P6 embedding 距离标定而非硬编码 | Gemini/DashScope 距离分布不同,硬编码 0.3 会在不同 provider 上静默失效 |
| `_POST_INGEST_INSTRUCTION` 删除 | 被 `next_action` 输出契约替代;SKILL 层的文本指令是旧模型的残留 |

### 否决方案

- **Option B 两层塌缩(workflow+MCP 合并)**：最强形态是"薄 phase descriptor + 单一 dispatcher",≤8 phase 时可读。否决:per-phase side effects(标定、replay hook、auth gate)会退化 dispatcher;1302 行纠缠是退化轨迹的证据。
- **Option C SKILL 控制流 + aggressive runtime validation**：否决:SKILL 是概率性产物,任何依赖 prose 保持不变性的方案都不合格。
- **Option D 延后重构只上 runtime guards**：否决:用户显式授权了结构化重构。

### 实现摘要

**删除:** `workflow/research_session.py`, `workflow/session_store.py`, `tools/workflow.py`, `_POST_INGEST_INSTRUCTION`, `_check_pre_ingest_gate`, 4 个旧 gate test 文件

**新增:** `workflow/batch.py`(455L), `workflow/batch_store.py`(75L), `workflow/worker.py`(237L), `tools/research_workflow.py`(564L, 10 tools), `tools/ingestion/` package(4 sub-modules, LLOC<800), 14 个 P1-P16 guardian test 文件, 5 个 spec fixture/corpus 文件

**验证:** 922 passed / ruff clean / mypy 0 errors / coverage 51% / architect APPROVED

**参考：** `.omc/specs/ingest-redesign-technical-doc.md`(1369 行完整设计 spec,含 ADR §16 + Pre-mortem §15 + Migration §18)

---

## 2026-04-08 | 搜索策略：agent 主导的 WebFetch + 精准查询

### 背景

单次关键词搜索在题名词汇与查询偏差较大时会遗漏经典文献。典型案例：查"AI flow field reconstruction"在 OpenAlex 找不到 Raissi 2020 *Hidden fluid mechanics*，因为论文题名和用户查询词汇完全不重叠。

### 决策

服务端 `search_academic_databases` 保持**极简**；检索智能移至 agent 侧（`SKILL ztp-research §4`）：

- **服务端**：顶层 `search=` 参数（从废弃 `title_and_abstract.search` filter 迁移）；`_split_author_query` 解析 `author:Name | topic` 语法；`fetch_openalex_by_doi` 含搜索 fallback（处理 DOI 重映射：arXiv 预印本 → 会议正式版）；裸自然语言查询时返回 `_warnings: [{"code": "missing_priming"}]`
- **Agent（SKILL §4）**：WebFetch 预热（Wikipedia / survey）→ 提取锚点作者 + DOIs → 3–5 条精准 OpenAlex 查询（DOI 直查、作者锚定、短语布尔）→ 客户端合并

### 否决方案

- **服务端语义 fan-out**：OpenAlex embedding search 处于 beta，不稳定
- **Topic autocomplete**：OpenAlex 无 topic autocomplete 接口（Codex 实测确认）
- **服务端 LLM 改写查询**：增加外部依赖，对已有 SKILL 层的 agent 无额外收益

### 实现摘要

迁移 `search=` 参数；新增 `missing_priming` warning 不变量；`fetch_openalex_by_doi` 增加搜索 fallback；SKILL §4 增加 WebFetch 预热强制步骤。

### 验证

`tests/test_search_benchmark.py`：12/12 case 通过（需 `--benchmark` 标志）。

**参考**：commit `6780e46`，`.omc/plans/research-search-quality-v3.md`

---

## 2026-04-07 | v0.5.0 架构落地：三层工作流架构、打包 skills、research guardrail

### 背景

三类问题：(1) 工作流层缺位，`SKILL.md` 承担过多职责；(2) CLI 和 skill 目录通过不同机制更新，pip/uv 用户容易版本脱节；(3) research 写入路径缺少服务端保护。

### 决策

采用 **Option C：风险分层混合架构**：

- Layer 1：`ztp-research` / `ztp-setup` / `ztp-review` / `ztp-profile` + 根 `SKILL.md` 路由
- Layer 2：`research_session` + `SessionStore` + Gate 1/2/3（仅 research）
- Layer 3：MCP tools 作为能力层，工具面收敛到 25 个（移除 15 个 deprecated 别名，合并 4 个低频工具）
- Skills 打包进 Python 包：`zotpilot register/update` 从包内部署

### 否决方案

通用 WorkflowRuntime / Capability Pack（实现重）；所有 skill 都做服务端 guardrail（setup/review/profile 风险不足以支撑）；继续独立 skill repo + git pull（对 pip/uv 用户不可靠）。

### 结果

三层架构正式化；25 工具面；Gate 1/2/3；packaged skills；`research_session` 进入 core。

---

## 2026-04-01 | SKILL+MCP 架构改造：工具精简 39→24，三层职责分离

### 背景

39 个 MCP 工具导致 context ~16,650 tokens（Cursor/Windsurf 截断）、三处文档重复维护、无场景裁剪机制。

### 决策

通过 CCG 三方审核确立合并原则：同一动词不同模式、同一对象不同视角可合并；返回结构不兼容、性能量级差异大不合并。

新增合并工具：`browse_library`、`get_citations`、`manage_tags`、`manage_collections`。降级为内部函数：`get_reranking_config`、`get_vision_costs`、`get_feeds`、`save_from_url`。15 个旧工具名保留 deprecated alias 到 v0.6.0。

三层架构：SKILL.md（意图路由）→ references/（SOP）→ MCP Tools（执行，倒金字塔 description）。

**效果**：工具 39→24（-38%），SKILL.md 252→152 行，context tokens ~16,650→~6,900（-58%）。

---

## 2026-04-01 | Ingest 真实性保障：三层防御机制

bridge 返回 `success: True` 但 Zotero 实际未创建条目（静默失败）。

**三层防御**：(1) post-save 即时验证，无 `item_key` 时调 `_discover_via_local_api`；(2) preflight 阻断 early-return，blocked/errored 且无 API candidates 时立即返回 `is_final: True`；(3) SKILL 层 `[VERIFY]`，`advanced_search` 批量 DOI 验证。

---

## 2026-04-01 | PDF 状态：付费墙场景元数据入库是正常行为

`pdf: "none"` + 非 OA → 正常；`pdf: "none"` + OA → 异常，重试 `doi.org/{doi}` 或手动下载。

---

## 2026-03-30 | ingestion 工作流修复：duplicate routing、tags 移除、post-ingest 引导

三个问题：(1) duplicate 论文跳过 collection routing；(2) `ingest_papers` 的 `tags` 参数导致 agent 擅自打标；(3) 入库后无 post-ingest 引导。另有 `update_item` 列表位置索引 IndexError。

**决策**：移除 `ingest_papers` 的 `tags` 参数（breaking，minor bump）；duplicate 后先 `add_to_collection`；`is_final=true && saved>0` 时返回 `_instruction`；`update_item` 改线性查找。

---

## 2026-03-30 | ingest_papers 异步化：解决 MCP 客户端超时

OpenCode 等客户端调用 `ingest_papers` 触发 `-32001` 超时（最坏 670s）。

`ingest_papers` 同步完成校验/去重/preflight 后提交 `ThreadPoolExecutor` 后台线程，立即返回 `batch_id`。新增 `get_ingest_status(batch_id)`、`ingest_state.py`（`BatchState` / `BatchStore` 内存 TTL 30min）。旧字段全部保留；全同步解决时 `is_final=true`，行为与旧版一致。

---

## 2026-03-30 | E2E 验证修复：dedup DOI、bridge 快速失败、collection/tag 本地路由

**5 个 bug**：(1) DOI 去重改大小写不敏感（SQLite BINARY collation）；(2) dedup 同时查原始 + arxiv canonical DOI；(3) collection/tag 路由改 Zotero 本地 API（`:23119`），弃用 pyzotero Web API 路由；(4) bridge 快速失败（`extension_connected == false` 立即返回）；(5) `config set preflight_enabled` 存字符串 bug 修复。Commit `769f91a`。

---

## 2026-03-30 | Ingestion 模块重构：3 工具 + 单路径去重 + 删除 S2

`ingest_papers` 从 460 行怪兽函数精简，4 条去重路径 → 1，最坏延迟 ~25min → ~3min。

删除 Semantic Scholar（OpenAlex 覆盖率足够）；删除 doi.org URL 路由（translator 匹配错误风险）；简化去重为单一 SQLite DOI 查询；工具精简 4→3（`save_from_url` 降为别名）；删除 PDF 轮询（180s 延迟）；preflight config 化。`ingestion.py` 963→419 行。Commit `210afff`。

---

## 2026-03-29 | Vision 默认预算收缩 + ingestion 内部分层

Vision 默认改用 compact prompt，输出上限 1536 tokens，保留 `prompt_mode="full"` 调试路径。

Ingestion 拆出 `ingestion_search.py`（OpenAlex adapter、DOI normalization）和 `ingestion_bridge.py`（preflight、bridge enqueue/poll、post-save routing），保住现有测试的 monkeypatch 入口。

---

## 2026-03-29 | Connector 心跳三项修复 + build 流程明确

三个并发问题：(1) preflight 竞态——`auto_start` 后立即 enqueue，heartbeat 未就绪；修复：新增 `_wait_for_extension(timeout=35)`；(2) `keep-mv3-alive.js` LET_DIE_AFTER 10min→60min（与注释一致）；(3) monorepo 合并后 build 产物缺失，从独立仓库复制重新生成。

Connector 分发：GitHub Release 附件 zip，不走 Chrome Web Store。

---

## 2026-03-29 | Monorepo 合并：connector 并入主仓库

将 `zotpilot-connector` 用 `git subtree add --squash` 并入 `connector/` 子目录，统一版本号（`pyproject.toml` 为 source of truth），两个组件同一 git tag 发版。

---

## 2026-03-28 | Connector preflight 三项修复

(1) preflight hard timeout 15s < TRANSLATOR_WAIT_MS 20s → 改 30s；(2) anti-bot 检测时最多重试 2×2s 重读 title；(3) PDF 直链触发下载时 tab 关闭 → `browser.tabs.get` 加 try/catch；(4) anti-bot 后 `finally` 关闭 tab → 加 `tabId = null`。

---

## 2026-03-28 | DOI de-dup 修复 + arXiv canonical DOI cache

de-dup 先查本地 SQLite，再 fallback Web API；arXiv 入库后缓存 canonical DOI（`10.48550/arxiv.{id}`）防重复入库。

---

## 2026-03-27 | 文献笔记系统 + get_paper_details 加 date_added

两级笔记工作流：Workflow A（精简自动，每篇必做）和 Workflow B（完整按需，用户触发）。`get_paper_details` 加 `date_added` 字段。preflight 失败提示改为等待用户决策（防 agent 自动重试循环）。

---

## 2026-03-26 | Token Slimming v3 — 统一 verbosity 体系

三级 verbosity（minimal/standard/full）统一贯穿所有工具，默认 minimal；`doc_id` 成为统一标识符；`search_topic` 移除 `best_passage_context`；`get_passage_context` `include_merged` 默认改 False；`get_index_stats` 改为 sample_unindexed + 新增 `get_unindexed_papers` 分页工具。513 tests passed，coverage 44%。

---

## 2026-03-26 | Connector 事件驱动握手 + 闭环 itemType 验证

(1) 替换 `_pollForTranslators` 为事件驱动（monkey-patch `onTranslators`，20s 超时 fallback）；(2) 新增 `_waitForItemInZotero`（save 后本地 API diff，最多 15 次 1s 间隔）；(3) 闭环 itemType 验证：拿到 `item_key` 后检查类型，非学术条目调 `delete_item`；(4) 移除 API 元数据 fallback 路径。

---

## 2026-03-26 | ingest_papers 批量并发 + 反爬三层修复

(1) `ingest_papers` 改批量 `save_urls`（解决串行心跳超时）；(2) 反爬检测移至 `_handleSave` 前（防止垃圾条目入库）；(3) `STABILITY_WINDOW_REDIRECT_MS` 2000→4000ms；(4) PDF 下载失败时监听 `cross.png` 事件立即 resolve。

---

## 2026-03-26 | item_key 发现链三项修复

(1) `find_items_by_url_and_title` 空 url 不再作为排除条件；(2) `_ITEM_DISCOVERY_WINDOW_S` 实际传入 discovery 函数；(3) `write_ops` 所有 list 参数加 `_coerce_list()` 解析 JSON string。

---

## 2026-03-25 | v0.4.1 Research Chain 九项修复

`_enrich_oa_url` 加 `is_oa` 门控；`search_academic_databases` 结果加 `publisher`/`journal` 字段；anti-bot + translator 降级检测；条目发现指数退避 `[2,4,8]`；SKILL.md 六项 agent 指令补全（订阅询问、确认门、路由表、批次上限、并行索引、pdf 状态区分）。

---

## 2026-03-24 | v0.4.1 前置修复

`pyzotero url_params` 二次泄漏修复；CrossRef 缺失时从 OpenAlex 补全 `oa_url`；SKILL.md Step 3 去重检查 + Step 4 工作流扩展；`profile_library` 新增 `top_journals` 字段；自适应对话式 profiling 工作流；SQLite `?mode=ro` URI 修复。

---

## 2026-03-24 | v0.4.0 误发事故记录

用户问命名问题，Claude 误读为发版指令，执行了完整 release flow，CI 自动发布 v0.4.0 到 PyPI（无法撤回）。

**结论**：`发版` / `release` 必须是用户的**显式指令**，不能由 Claude 从上下文推断，发版前必须等待用户确认。

---

## 2026-03-24 | 分支策略 + docs/ 文档体系建立

建立 `dev` 开发分支（禁止直接 push main）；新建 `docs/` 存放内部架构文档和决策记录。

---

## 2026-03-23 | v0.3.1 关键决策

SKILL.md 重构（setup 内容迁 `references/setup-guide.md`）；Windows 升级错误改 `CalledProcessError` + stderr 关键词检测；Cursor/Windsurf 升级为 Tier 1；写操作配置统一用 `config set` 持久化。

---

## 2026-03-23 | v0.3.0（已发布）

`zotpilot update` CLI 子命令（uv/pip 自适应，skill 目录 git pull）；CI 全面修复（ruff 114 errors、mypy 136 errors）；`main` 分支保护（禁止 force push/删除）。

---

## 2026-03-22 | v0.2.1（已发布）

新增 ingestion 工具组（`search_academic_databases`、`add_paper_by_identifier`、`ingest_papers`）；`zotpilot config` CLI 子命令；API key 优先级规则（环境变量 > config，`Config.save()` 不持久化 API key）。

---

## 早期架构决策（摘要）

| 决策 | 说明 |
|---|---|
| Bridge + Connector（HTTP 轮询） | MV3 Service Worker 不支持持久 WebSocket；HTTP 轮询天然兼容；`ThreadingHTTPServer` 防死锁 |
| FastMCP 框架 | `@mcp.tool` 装饰器 + import side-effects 注册，极大简化工具模块维护 |
| 懒加载单例（`state.py`） | 启动时不知道用户是否需要 RAG；`switch_library` 全部重置；父进程监控防孤儿进程 |
| No-RAG 降级模式 | `embedding_provider="none"` 跳过向量索引，基础功能不依赖 API |
| 嵌入提供方抽象 | `embeddings/base.py` 定义 `Embedder` 接口，`create_embedder(config)` 工厂函数，对工具层透明 |
| `switch_library` 工具禁用 | cross-library RAG leaks 风险，功能未完成前不暴露 |

---

## 版本管理约定

- **Claude 负责版本管理**（见 CLAUDE.md `## Version Management`）
- **patch** (0.x.Z)：bug fixes, doc updates, test additions
- **minor** (0.Y.0)：new user-facing features (new CLI subcommand, new MCP tool)
- **major** (X.0.0)：breaking changes to MCP tool signatures or config format
- **CHANGELOG**：双语格式（中文 / English），CI 用 awk 提取 release notes
- **发版流程**：`dev` → PR → `main` → commit → tag vX.Y.Z → push + push tags → CI 自动发 PyPI + GitHub Release

---

<!-- 新决策追加在上方，格式：
## YYYY-MM-DD
### 标题
- **决策**：
- **理由**：
- **行动**：
- **状态**：🔄 进行中 / ✅ 完成 / ❌ 撤销
-->
