# ZotPilot 工作流架构改造 — 完整实施计划 v2

## 文档定位

本文档是当前版本改造的**唯一实施蓝图**，取代所有先前版本。

规划演进：
1. PRD → 确定了 Option B（四层架构 + 通用工作流引擎）
2. CCG 第一轮审核（2026-04-02）→ 确认 Phase A 技术决策
3. OMC 架构对比 → 发现原计划远重于 OMC 模式
4. **CCG 第二轮审核（2026-04-04）→ 转向 Option C（风险分层混合），本文档即反映此决策**

先前文档状态：

| 文档 | 当前状态 |
|---|---|
| [PRD](prd-ztp-lifecycle-architecture.md) | 历史参考，问题定义仍有效，架构方案已被本文档取代 |
| [Execution Breakdown](execution-breakdown-ztp-lifecycle-architecture.md) | 已废弃 |
| [Final Implementation Doc](final-implementation-doc-ztp-current-version.md) | 已被本文档取代 |
| [Workflow Runtime Contract](workflow-runtime-contract-ztp-current-version.md) | 已被本文档 §六 取代（范围从通用缩减到 research-only） |
| [Test Spec](test-spec-ztp-lifecycle-architecture.md) | 需更新以对齐本文档（测试范围缩减） |

---

## 一、背景与问题

ZotPilot 当前的产品表面是**一个单体 SKILL.md + profile-gated MCP 工具**。四个核心问题：

1. **工作流合同仅存在于 prompt 文本**——不可强制执行，LLM 随时可能偏离
2. **默认 `core` profile 无法完成完整工作流**——`index_library`、`manage_tags` 等不在 core 中，导致 research 流程在 post-ingest 阶段断裂
3. **agent 行为过于随意**——显式调用时 LLM 可能跑去做 generic web search 而不用 ZotPilot 发现工具
4. **生命周期关注点碎片化**——setup 在 README、references、CLI 三个地方各有一部分

---

## 二、架构决策

### 方案演进

| 阶段 | 方案 | 结论 |
|---|---|---|
| PRD | Option A：加固单体 Skill | 否决——无法做到确定性工作流 |
| PRD | Option B：四层架构 + 通用工作流引擎 | 初选——但后续发现过重 |
| PRD | 多 MCP 服务器 | 否决——违反单服务器约束 |
| CCG 第二轮 | **Option C：风险分层混合** | **最终选择** |

### 最终选择：Option C — 风险分层混合

**核心原则**：Prompt-driven UX + 仅在高风险写入路径加代码级保护

- 4 个 Skill 全部为**纯 markdown prompt**（对齐 OMC 模式）
- 只有 `ztp-research` 获得**服务端 guardrail kernel**（因为涉及 Zotero 写操作）
- `ztp-setup`、`ztp-review`、`ztp-profile` 无代码级运行时
- 复用现有 `ZOTPILOT_TOOL_PROFILE`，不建 Capability Pack 体系
- 不建通用工作流引擎

### 决策依据（CCG 第二轮）

**Codex 的 7 个 prompt-only 失败模式**（均来自代码验证）：

| # | 失败模式 | 代码证据 |
|---|---|---|
| 1 | Checkpoint bypass | `SKILL.md` 的 `[USER_REQUIRED]` 是建议文本，非执行屏障 |
| 2 | Resume 丢失 | `BatchStore` 内存 30min TTL + `switch_library` 清空 |
| 3 | Drift 检测不足 | 仅 item 存在性不够，需验证工作流假设 |
| 4 | Wrong-library writes | `switch_library` 重置后恢复的 prompt 可能写到错误库 |
| 5 | Duplicate side effects | `create_note`、tag `set` 不幂等，重试产生重复 |
| 6 | Capability leakage | `core`/`extended`/`all` 不是工作流安全边界 |
| 7 | Portability hole | 安全性应在 ZotPilot 内部，不应依赖 OMC state 工具 |

**Gemini 的关键贡献**：
- 1-2 人项目 markdown-first 是绝对首选
- 复用 `ZOTPILOT_TOOL_PROFILE` 而非重建 capability packs
- 渐进路径：先拆 skill，发现问题再加 guardrails

**综合判断**：Gemini 的"出问题再加"策略对通用开发工作流合理，但 ZotPilot 写的是用户文献库——"出问题"意味着**数据已经损坏**。因此对 research 写入路径预防性加固，其余 prompt-only。

---

## 三、目标架构

```
┌────────────────────────────────────────────────────────┐
│  Workflow Skills（纯 markdown prompt）                 │
│  ztp-research · ztp-setup · ztp-review · ztp-profile   │
│  + root SKILL.md 兼容路由 shell                        │
├────────────────────────────────────────────────────────┤
│  Research Guardrail Kernel（仅 ztp-research）           │
│  ResearchSession · 3 hard gates · per-item validation  │
├────────────────────────────────────────────────────────┤
│  MCP Tools（32 个领域工具，单服务器）                   │
│  Tool Profile 控制可见性（复用现有机制）                │
└────────────────────────────────────────────────────────┘
```

**与旧方案对比**：

| 维度 | 旧方案（Option B） | 新方案（Option C） |
|---|---|---|
| 架构层数 | 4 层（Skill → Runtime → Pack → Service） | 3 层（Skill → Guardrail → MCP Tools） |
| 运行时范围 | 通用 WorkflowRuntime（所有 skill） | ResearchSession（仅 research） |
| 状态持久化 | WorkflowStore（通用 JSON） | SessionStore（research 专用） |
| Drift 检测 | AnchorChecker（全库 SQLite 快照） | per-item fingerprint check |
| 能力控制 | Capability Packs（4 个 pack + 代码级校验） | 复用 ZOTPILOT_TOOL_PROFILE |
| 新增 Python 模块 | 5 个 | 2 个 |
| 有运行时集成的 Skill | 4 个 | 1 个 |

---

## 四、当前版本范围

### 纳入

| Surface | 类型 | 说明 |
|---|---|---|
| `ztp-research` | Markdown skill + 服务端 guardrail | 主证明目标：发现 → ingest → 整理 |
| `ztp-setup` | 纯 Markdown skill | 安装/配置/注册/首次索引 |
| `ztp-review` | 纯 Markdown skill | 本地库综述与合成 |
| `ztp-profile` | 纯 Markdown skill | 库分析与画像 |
| 根 `SKILL.md` | 兼容路由 shell | 意图分类 + 路由到 ztp-* |
| `ResearchSession` | Python 代码 | 3 hard gates + per-item validation |
| Post-ingest 幂等改造 | Python 代码 | note 查重、tag add、collection no-op |

### 推迟

- `ztp-guider`（深度阅读指导）
- 通用工作流引擎
- Capability Pack 体系

### 排除

- 多 MCP 服务器
- MCP 工具全面重写

---

## 五、Skill 设计

### 5.1 Skill 格式

遵循 OMC 标准格式，纯 markdown + frontmatter：

```markdown
---
name: ztp-research
description: Literature discovery, ingest, and organization workflow
triggers:
  - "帮我调研"
  - "find papers about"
  - "survey research on"
---

# ztp-research

## Purpose
...

## Workflow
...
```

### 5.2 `ztp-research`

**阶段模型**：

```
clarify_query → external_discovery → score_candidates
    → [CHECKPOINT: candidate-review]
    → ingest → ingest_verification
    → [CHECKPOINT: post-ingest-review]
    → index → classify → note → tag
    → final_report
```

**Intelligence zones**（LLM 自主决策）：
- 候选评分与排序解释
- 集合建议
- 笔记合成
- 从现有词汇中选择标签

**Deterministic zones**（必须严格执行）：
- 使用 ZotPilot 发现工具优先，默认禁止 generic web search
- 两个 mandatory checkpoint 不可跳过
- 批准后 downstream 步骤自动执行
- Post-ingest 步骤必须幂等

**Tool Profile 要求**：skill 首部声明 `ZOTPILOT_TOOL_PROFILE=research`（新增 profile，详见 §七）

**服务端 guardrail 集成**：详见 §六

### 5.3 `ztp-setup`

```
detect_environment → choose_provider → write_config
    → register_mcp → [restart-required] → initial_index_ready
```

- 纯 prompt 工作流，无服务端 guardrail
- CLI 权威不变：`setup --non-interactive` / `register` 等机器操作由 CLI 执行
- 明确区分 pre-MCP bootstrap（CLI 主导）vs post-MCP readiness（MCP 工具验证）
- 三种安装模式均需说明：`editable` / `uv tool` / `pip`

### 5.4 `ztp-review`

```
clarify_review_topic → local_library_scope → cluster_topic
    → extract_passages → optional_citation_expansion → outline
    → synthesis → [refinement checkpoint] → final_review
```

- 纯 prompt 工作流
- **规则**：local-library-first——优先使用本地已索引文献

### 5.5 `ztp-profile`

```
scan_library → infer_themes → [dialogue checkpoint]
    → write_profile_artifact → optional_organization_recommendations
```

- 纯 prompt 工作流
- **规则**：广泛写操作（批量 tag/collection 修改）需显式确认

### 5.6 兼容路由 Shell（根 SKILL.md）

- 精简为意图分类器 + 路由
- 不重新实现任何工作流逻辑
- 透明移交：用户说"帮我查论文" → 回复"正在启动 Research 工作流..." → 上下文移交到 `ztp-research`
- 加轻量级 deprecation 提示

---

## 六、Research Guardrail Kernel（技术规格）

这是 Option C 的核心技术交付物。仅服务于 `ztp-research`，不是通用工作流引擎。

### 6.1 ResearchSession Schema

```python
@dataclass
class ResearchSession:
    session_id: str                      # "rs_<hex12>"
    library_id: int                      # 创建时锁定的 Zotero library ID
    stage: str                           # 当前阶段名称
    status: Literal[
        "running",
        "awaiting_user",          # checkpoint 等待审批
        "partial_success",        # 部分条目成功
        "blocked",                # 外部阻塞（anti-bot 等）
        "resume_invalidated",     # drift 检测失败
        "completed",
        "cancelled",
        "failed",
    ]
    selected_papers: list[PaperCandidate]  # 外部发现的候选列表
    batch_id: str | None                   # 关联的 ingest batch
    items: list[SessionItem]               # 逐篇状态
    approved_checkpoints: list[str]        # 已通过的 checkpoint ID
    blocker_reason: str | None
    created_at: str                        # ISO 8601
    updated_at: str                        # ISO 8601


@dataclass
class SessionItem:
    item_key: str | None           # Zotero item key（ingest 后填入）
    doi: str | None
    title: str | None
    status: Literal["pending", "ingested", "indexed", "noted", "tagged", "done", "failed", "skipped"]
    fingerprint: ItemFingerprint | None  # resume 前校验用
    stages_completed: list[str]
    error: str | None


@dataclass(frozen=True)
class ItemFingerprint:
    """Resume 前的 drift 校验指纹。"""
    item_key: str
    date_added: str               # 来自 SQLite items.dateAdded
    title_prefix: str             # 标题前 50 字符
    note_count: int               # 当前 note 数量（防止 note 重复写入）
```

### 6.2 三个 Hard Gates

这是 guardrail 的核心。通过 MCP 工具返回值中嵌入 gate check 来实现，不需要独立的拦截层。

| Gate | 触发时机 | 检查内容 | 失败行为 |
|---|---|---|---|
| **Gate 1: Pre-Ingest** | `ingest_papers` 调用时 | session 存在 + `candidate-review` checkpoint 已通过 + `library_id` 一致 | 返回 ToolError，阻止 ingest |
| **Gate 2: Pre-Post-Ingest** | post-ingest 首个写操作时 | session 存在 + `post-ingest-review` checkpoint 已通过 + ingest 验证成功 | 返回 ToolError，阻止写入 |
| **Gate 3: Pre-Resume** | session 从磁盘恢复时 | `library_id` 一致 + 每个 `SessionItem` 的 fingerprint 校验通过 | 状态置为 `resume_invalidated`，等待用户决策 |

### 6.3 Fingerprint Drift 检测

**校验方式**：通过 `ZoteroClient`（只读 SQLite）查询目标 item 的当前状态，与保存的 fingerprint 比对。

**Drift 触发条件**：
- `item_key` 在 SQLite 中不存在（条目被删除）
- `date_added` 变化（条目被替换）
- `title_prefix` 变化（条目被替换为不同论文）

**不触发 drift**（因为工作流本身会改这些）：
- tags 变化
- collections 变化
- notes 变化

**Gate 3 drift 检测后的用户选项**（可在 Skill prompt 中定义，无需代码枚举）：
- 工具返回 drift 详情 + `resume_invalidated` 状态
- Skill prompt 引导用户选择：继续（跳过消失的条目）/ 重新开始 / 放弃

### 6.4 SessionStore

```python
class SessionStore:
    """ResearchSession 的 JSON 持久化。"""
    
    def __init__(self, data_dir: Path | None = None):
        # 默认: ~/.local/share/zotpilot/sessions/
        ...
    
    def save(self, session: ResearchSession) -> None:
        """写入 <session_id>.json"""
        ...
    
    def load(self, session_id: str) -> ResearchSession | None:
        """从磁盘加载"""
        ...
    
    def find_active(self, library_id: int) -> ResearchSession | None:
        """查找当前 library 的 active session（status 非终态）"""
        ...
    
    def cleanup_expired(self, max_age_days: int = 30) -> int:
        """清理已完成/过期的 session"""
        ...
```

### 6.5 自动检测 in-flight session

当用户调用 `ztp-research` 时，skill prompt 指示 LLM：
1. 先调用 `get_research_session()` 检查是否有 active session
2. 若有 → 提示用户：检测到未完成的研究流程，是否恢复？
3. 若无 → 创建新 session

这是 prompt-level 逻辑，不需要代码级拦截。

---

## 七、Tool Profile 扩展

在现有 `profiles.py` 基础上新增一个 `research` profile：

```python
VALID_TOOL_PROFILES = {"core", "extended", "all", "research"}

PROFILE_VISIBLE_TAGS: dict[str, set[str] | None] = {
    "core": {"core"},
    "extended": {"core", "extended", "admin"},
    "all": None,
    "research": {"core", "extended", "write", "admin"},  # research 需要全部写操作
}
```

每个 skill 在首部声明所需 profile：
- `ztp-research` → `ZOTPILOT_TOOL_PROFILE=research`
- `ztp-setup` → `ZOTPILOT_TOOL_PROFILE=core`
- `ztp-review` → `ZOTPILOT_TOOL_PROFILE=extended`
- `ztp-profile` → `ZOTPILOT_TOOL_PROFILE=extended`

兼容性：`core`/`extended`/`all` 行为不变。

---

## 八、Post-Ingest 幂等改造

Codex 指出当前 post-ingest 写操作不幂等，重试会产生重复。必须修复：

| 操作 | 当前行为 | 改造后 |
|---|---|---|
| `index_library` | 可重入（安全） | 不变 |
| `create_note` | 无查重，重复调用产生多条 note | **新增**：检查 item 是否已有 ZotPilot 生成的 note（通过标记前缀或 tag） |
| `manage_collections` (`add`) | 已在 collection 中时 API 返回成功（安全） | 不变 |
| `manage_tags` (`set`) | 替换所有 tags（destructive） | **改为默认 `add`**；`set` 仅在 skill prompt 显式要求时使用 |

实现方式：
- `create_note` 新增参数 `idempotent: bool = False`，为 True 时先查该 item 是否已有 `[ZotPilot]` 前缀的 note
- `manage_tags` 在 research session 上下文中默认行为从 `set` 改为 `add`（通过 session 检测，非全局变更）

---

## 九、遗留表面映射

| 现有 SKILL.md 段落 | 目标归属 |
|---|---|
| External Discovery | `ztp-research` 主流程 |
| Direct Ingest | `ztp-research` 快速子流程 |
| Local Search | 共享能力，`ztp-review`/`ztp-profile`/`ztp-research` 验证阶段使用 |
| Organize | 吸收进 `ztp-research` post-ingest + `ztp-profile` 整理建议 |
| Profile | `ztp-profile` |
| Setup guidance | `ztp-setup` |
| Update guidance | 生命周期合同，非独立 skill |
| Deep note / guided read | 推迟到 `ztp-guider` |
| Root intent router | 兼容路由 shell |

---

## 十、实施 Phase

### Phase 1：Skill 拆分 + Tool Profile 扩展

**目标**：4 个 markdown skill 上线，根 SKILL.md 变为路由 shell。

**交付物**：

| 文件 | 说明 |
|---|---|
| `skills/ztp-research.md` | Research skill（含 guardrail 集成指示） |
| `skills/ztp-setup.md` | Setup skill |
| `skills/ztp-review.md` | Review skill |
| `skills/ztp-profile.md` | Profile skill |
| `SKILL.md` 精简 | 路由 shell + 迁移提示 |
| `profiles.py` | 新增 `research` profile |

**退出条件**：
- [ ] 4 个 skill 可被 agent 调用
- [ ] 根 SKILL.md 不再包含完整工作流逻辑
- [ ] `ZOTPILOT_TOOL_PROFILE=research` 暴露 research 所需的全部工具

### Phase 2：Research Guardrail Kernel

**目标**：`ztp-research` 的服务端保护上线。

**交付物**：

| 文件 | 说明 |
|---|---|
| `src/zotpilot/workflow/research_session.py` | `ResearchSession` + `SessionItem` + `ItemFingerprint` dataclasses |
| `src/zotpilot/workflow/session_store.py` | `SessionStore`（JSON 持久化） |
| `src/zotpilot/workflow/__init__.py` | 包初始化 |
| `src/zotpilot/tools/ingestion.py` 修改 | Gate 1 集成（Pre-Ingest check） |
| `src/zotpilot/tools/write_ops.py` 修改 | Gate 2 集成（Pre-Post-Ingest check） |
| `src/zotpilot/tools/ingest_state.py` 修改 | `BatchState` 关联 `session_id` |
| `src/zotpilot/zotero_client.py` 修改 | 新增 batch item fingerprint 查询 |

**新增 MCP 工具**（暴露给 Skill prompt 使用）：

```python
@mcp.tool(tags=tool_tags("core"))
def create_research_session(query: str) -> dict:
    """创建新的 research session，返回 session_id。"""

@mcp.tool(tags=tool_tags("core"))
def get_research_session(session_id: str | None = None) -> dict:
    """获取当前 session 状态。无参数时返回当前 library 的 active session。"""

@mcp.tool(tags=tool_tags("core"))
def approve_checkpoint(session_id: str, checkpoint: str) -> dict:
    """记录用户审批通过的 checkpoint。"""

@mcp.tool(tags=tool_tags("core"))
def validate_session_items(session_id: str) -> dict:
    """Gate 3：校验所有 session items 的 fingerprint，返回 drift 详情。"""
```

**退出条件**：
- [ ] 3 个 hard gates 均可阻止未授权写入
- [ ] Session 状态跨进程重启存活
- [ ] Fingerprint drift 检测可发现 item 删除/替换
- [ ] `get_research_session()` 可发现 in-flight session

### Phase 3：Post-Ingest 幂等改造

**目标**：消除重试/resume 时的 duplicate side effects。

**交付物**：

| 文件 | 修改 |
|---|---|
| `src/zotpilot/tools/write_ops.py` | `create_note` 新增幂等模式（查重） |
| `src/zotpilot/tools/write_ops.py` | `manage_tags` research context 默认 `add` |
| `src/zotpilot/tools/ingest_state.py` | `_POST_INGEST_INSTRUCTION` 更新（`add` 替代 `set`） |

**退出条件**：
- [ ] 对同一 item 重复执行 post-ingest 全流程不产生重复 note
- [ ] 对同一 item 重复执行 tag 操作不清空已有 tags

### Phase 4：文档与兼容性

**目标**：文档反映新架构，迁移路径清晰。

**交付物**：

| 文档 | 更新内容 |
|---|---|
| `README.md` | "以前 vs 现在"指令对照表 + 架构段落更新 |
| `docs/architecture.md` | 三层架构图 + Research Guardrail 说明 |
| `CLAUDE.md` | 架构段落 + 工具模块表 + 新增 workflow/ 目录说明 |
| `SKILL.md` | 确认路由 shell 最终形态 + sunset 提示 |

**退出条件**：
- [ ] 文档与实现无矛盾
- [ ] 新用户能从 README 理解如何使用 `ztp-research`
- [ ] 旧用户能从 SKILL.md 迁移提示理解变化

---

## 十一、验证门控

| Gate | 前置 | 退出条件 |
|---|---|---|
| **Gate 1** | — | 4 个 skill 可调用 + `research` profile 工具充足 |
| **Gate 2** | Gate 1 | 3 hard gates 测试通过 + session 持久化验证 + fingerprint drift 检测验证 |
| **Gate 3** | Gate 2 | post-ingest 幂等测试通过（重复执行无 duplicate） |
| **Gate 4** | Gate 1-3 | 文档对齐 + 兼容路由验证 |

Gate 1 和 Gate 2 可部分**并行**（skill 文件编写与 Python 模块开发互不阻塞）。

---

## 十二、实施文件总览

### 新增文件

| 路径 | Phase | 说明 |
|---|---|---|
| `src/zotpilot/workflow/__init__.py` | 2 | 包初始化 |
| `src/zotpilot/workflow/research_session.py` | 2 | ResearchSession + SessionItem + ItemFingerprint |
| `src/zotpilot/workflow/session_store.py` | 2 | SessionStore（JSON 持久化） |
| `skills/ztp-research.md` | 1 | Research workflow skill |
| `skills/ztp-setup.md` | 1 | Setup workflow skill |
| `skills/ztp-review.md` | 1 | Review workflow skill |
| `skills/ztp-profile.md` | 1 | Profile workflow skill |

### 修改文件

| 路径 | Phase | 修改内容 |
|---|---|---|
| `src/zotpilot/tools/profiles.py` | 1 | 新增 `research` profile |
| `src/zotpilot/tools/ingestion.py` | 2 | Gate 1（Pre-Ingest session check） |
| `src/zotpilot/tools/write_ops.py` | 2+3 | Gate 2 + note 幂等 + tag add 默认 |
| `src/zotpilot/tools/ingest_state.py` | 2+3 | `session_id` 关联 + instruction 更新 |
| `src/zotpilot/zotero_client.py` | 2 | batch fingerprint 查询 |
| `SKILL.md` | 1 | 精简为路由 shell |
| `README.md` | 4 | 指令对照表 + 架构更新 |
| `docs/architecture.md` | 4 | 三层架构图 + guardrail 说明 |
| `CLAUDE.md` | 4 | 架构段落 + workflow/ 目录 |

---

## 十三、风险预防

| 风险 | 缓解措施 |
|---|---|
| Skill prompt 不够约束 LLM | Gate 1/2 在代码层兜底，即使 LLM bypass prompt checkpoint 也无法执行写操作 |
| ResearchSession 变成通用引擎 | 严格限制：仅 research 使用，拒绝不直接服务 research 流程的抽象 |
| `research` profile 暴露过多工具 | 可后续收紧，当前优先保证 research 流程可完成 |
| Post-ingest 幂等改造不彻底 | Gate 2 保证只有经过 checkpoint 的 session 才能触发写操作 |
| 兼容 shell 永远不缩减 | Phase 4 定义 sunset 提示；下一版本进一步收缩 |
| 其他 3 个 skill prompt-only 不够用 | Gemini 建议的渐进路径：观察失败模式，再决定是否加 guardrail |

---

## 十四、与 OMC 架构的对齐关系

| OMC 概念 | ZotPilot 对应 |
|---|---|
| Skills（markdown + frontmatter） | `skills/ztp-*.md`（相同格式） |
| Agents（role definitions） | 不适用（ZotPilot 不需要 agent 角色） |
| MCP Tools（generic: LSP, state, memory） | MCP Tools（domain-specific: search, ingest, write） |
| `OMC_DISABLE_TOOLS`（category 开关） | `ZOTPILOT_TOOL_PROFILE`（profile 选择） |
| `state_read/state_write`（generic state） | `create/get_research_session`（domain-specific state） |
| 无 workflow runtime | ResearchSession guardrail kernel（仅 research） |

**关键差异**：OMC 的工具是通用基础设施（LSP、AST），ZotPilot 的工具是领域特定的（search_papers、ingest_papers）。OMC 不需要 guardrail 因为它不写用户的高价值数据。ZotPilot 在 research 路径上需要因为 Zotero 写操作半不可逆。

---

## 附录：CCG 审核纪要

### 第一轮（2026-04-02）

主题：审核 Option B 四层架构计划的不确定点

关键决策：
1. 状态存储选本地 JSON
2. Anchor 用 SQLite 只读快照
3. Phase A 包含代码骨架
4. resume-invalidated 选项推迟到实现时再定

### 第二轮（2026-04-04）

主题：OMC 轻量架构 vs 当前重型计划

关键决策：
1. **转向 Option C**：风险分层混合
2. 只有 `ztp-research` 有服务端 guardrail
3. 其他 3 个 skill 纯 prompt
4. 复用 `ZOTPILOT_TOOL_PROFILE`，不建 Capability Pack
5. Post-ingest 必须幂等改造
6. 从 5 个新模块缩减到 2 个
