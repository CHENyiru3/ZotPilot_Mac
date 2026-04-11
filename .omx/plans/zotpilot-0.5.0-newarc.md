# ZotPilot v0.5.0 架构设计

## 文档体系

本文档是 v0.5.0 工作流架构改造的**总设计文档**。

| 文档 | 角色 |
|---|---|
| **本文档** | 总架构、决策记录、MCP 工具规划、实施路线 |
| [ztp-research 技术实现](zotpilot-0.5.0-skill-research.md) | Research skill 阶段模型、guardrail 规格、幂等规则 |
| [ztp-setup 技术实现](zotpilot-0.5.0-skill-setup.md) | Setup skill 阶段模型、CLI 对接、安装模式 |
| [ztp-review 技术实现](zotpilot-0.5.0-skill-review.md) | Review skill 阶段模型、local-first 规则 |
| [ztp-profile 技术实现](zotpilot-0.5.0-skill-profile.md) | Profile skill 阶段模型、批量写操作确认规则 |
| [MCP 工具参考手册](zotpilot-0.5.0-mcp-tool-reference.md) | 全部 25 个活跃工具定义、参数、工作流矩阵、改造清单 |
| [分发与生命周期管理](zotpilot-0.5.0-distribution.md) | 安装/更新/发版流程、Skill 打包分发、版本防护 |
| [Test Spec](test-spec-ztp-lifecycle-architecture.md) | 测试权威（需按本文档更新） |
| [E2E 测试方案](zotpilot-0.5.0-e2e-test-plan.md) | Agent E2E 测试执行方案，18 个场景 |

先前规划文档（PRD、Execution Breakdown、Final Implementation Doc、Workflow Runtime Contract）均已被本文档体系取代，仅作历史参考。

---

## 一、背景与问题

ZotPilot 当前产品表面：**一个单体 SKILL.md + profile-gated MCP 工具（core/extended/all）**。

| 问题 | 说明 |
|---|---|
| 工作流仅存在于 prompt | `[USER_REQUIRED]` 是建议文本，LLM 可跳过 |
| 默认 profile 不完整 | `core` 缺少 `index_library`、`manage_tags` 等，research 流程在 post-ingest 断裂 |
| Agent 行为过于随意 | 显式调用时 LLM 可能用 generic web search 而非 ZotPilot 发现工具 |
| 生命周期碎片化 | setup 分散在 README、references、CLI 三处 |
| BatchStore 内存丢失 | 进程重启后 ingest 状态消失（30min TTL + switch_library 清空） |
| Post-ingest 不幂等 | `create_note` 重复调用产生多条 note，`manage_tags(set)` 清空已有 tags |

---

## 二、架构决策

### 方案演进

| 轮次 | 方案 | 结论 |
|---|---|---|
| PRD 初选 | Option B：四层架构 + 通用 WorkflowRuntime + Capability Packs | 过重 |
| CCG 第一轮 | 确认 Phase A 技术决策（JSON 存储、SQLite anchor） | 部分保留 |
| OMC 对比 | 发现 OMC 用纯 prompt skill + 通用 state 工具，无代码级运行时 | 触发反思 |
| **CCG 第二轮** | **Option C：风险分层混合** | **最终选择** |

### 最终选择：Option C — 风险分层混合

| 原则 | 说明 |
|---|---|
| Prompt-driven UX | 4 个 skill 全部为纯 markdown，对齐 OMC 模式 |
| 代码保护仅限高风险路径 | 只有 `ztp-research` 有 ResearchSession guardrail |
| 复用现有机制 | Tool Profile 控制可见性，不建 Capability Pack 体系 |
| 不建通用引擎 | ResearchSession 是 research-specific，拒绝泛化 |

### 与旧方案对比

| 维度 | Option B（旧） | Option C（新） | 缩减 |
|---|---|---|---|
| 架构层数 | 4 层 | 3 层 | -25% |
| 新 Python 模块 | 5 个 | 2 个 | -60% |
| 有代码级运行时的 Skill | 4 个 | 1 个 | -75% |
| Drift 检测 | 全库 SQLite 快照 | per-item fingerprint | 大幅简化 |
| 能力控制 | 4 个 Capability Pack + 代码级校验 | 复用 ZOTPILOT_TOOL_PROFILE | 删除 |

---

## 三、目标架构

```
┌────────────────────────────────────────────────────────┐
│  Layer 1: Workflow Skills（纯 Markdown prompt）        │
│  ztp-research · ztp-setup · ztp-review · ztp-profile   │
│  + root SKILL.md 兼容路由 shell                        │
├────────────────────────────────────────────────────────┤
│  Layer 2: Research Guardrail（仅 ztp-research）         │
│  ResearchSession · SessionStore · 3 Hard Gates         │
│  Per-item Fingerprint Validation                       │
├────────────────────────────────────────────────────────┤
│  Layer 3: MCP Tools（单服务器，Tool Profile 控制）      │
│  25 个活跃工具（v0.5.0 目标：deprecated 别名全部移除） │
└────────────────────────────────────────────────────────┘
```

### 层间职责

| 层 | 职责 | 不做 |
|---|---|---|
| Skill | 阶段顺序、用户交互、intelligence/deterministic 分区 | 状态持久化、gate 强制执行 |
| Guardrail | Session 持久化、gate 检查、drift 检测 | 阶段推进、用户交互 |
| MCP Tools | 领域能力（搜索、入库、写操作） | 工作流编排、策略执行 |

---

## 四、v0.5.0 版本范围

### 纳入

| 交付物 | 类型 | 状态 | Phase |
|---|---|---|---|
| `src/zotpilot/skills/ztp-research.md` | Markdown skill | v0.5.0 目标 | 2 |
| `src/zotpilot/skills/ztp-setup.md` | Markdown skill | v0.5.0 目标 | 2 |
| `src/zotpilot/skills/ztp-review.md` | Markdown skill | v0.5.0 目标 | 2 |
| `src/zotpilot/skills/ztp-profile.md` | Markdown skill | v0.5.0 目标 | 2 |
| `SKILL.md` 精简 | 路由 shell | v0.5.0 目标 | 2 |
| `profiles.py` 新增 `research` profile | Tool Profile | v0.5.0 目标 | 1 |
| `workflow/research_session.py` | Python dataclasses | v0.5.0 目标 | 3 |
| `workflow/session_store.py` | JSON 持久化 | v0.5.0 目标 | 3 |
| Gate 1/2/3 集成 | Python 代码 | v0.5.0 目标 | 3 |
| Post-ingest 幂等改造 | Python 代码 | v0.5.0 目标 | 3 |
| 移除 15 个 deprecated 别名 | Python 代码 | v0.5.0 目标 | 1 |
| 合并 4 个低频工具 | Python 代码 | v0.5.0 目标 | 1 |
| profile tag 提升 | Python 代码 | v0.5.0 目标 | 1 |
| 文档对齐 | Markdown | v0.5.0 目标 | 4 |

### 推迟

- `ztp-guider`（深度阅读）
- 通用工作流引擎
- Capability Pack 体系
- MCP 工具全面重写

---

## 五、MCP 工具现状分析

### 当前工具清单（当前状态 vs v0.5.0 目标）

#### 搜索类（6 个）

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `search_papers` | core | 语义搜索本地库 | 当前 |
| `search_topic` | core | 主题搜索 | 当前 |
| `search_boolean` | extended | 布尔搜索 | 当前 |
| `search_tables` | extended | 搜索表格 | 当前 |
| `search_figures` | extended | 搜索图表 | 当前 |
| `advanced_search` | core | 元数据过滤 | 当前 |

#### 上下文类（2 个）

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `get_passage_context` | core | 扩展搜索结果的上下文 | 当前 |
| `get_paper_details` | core | 论文详情 | 当前 |

#### 库浏览类

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `browse_library` | extended | 统一浏览（集合/标签/概览） | 当前 |
| `get_notes` | extended | 读取笔记 | 当前 |
| `get_feeds` | extended | RSS feeds | v0.5.0 目标：将合并入 `browse_library(view="feeds")` |
| `get_annotations` | extended | PDF 标注 | 当前 |
| `profile_library` | extended | 库画像数据（ztp-profile 依赖） | 当前 |

#### 索引类

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `index_library` | admin（当前）→ extended | 索引/重建，research/setup 依赖 | v0.5.0 目标：将从 admin 提升到 extended |
| `get_index_stats` | admin（当前）→ core | 索引统计；v0.5.0 将合并未索引论文列表、重排配置、视觉费用 | v0.5.0 目标：将从 admin 提升到 core |
| `get_unindexed_papers` | admin | 未索引论文列表（分页） | v0.5.0 目标：将合并入 `get_index_stats` 参数 |
| `get_reranking_config` | admin | 重排权重查看 | v0.5.0 目标：将合并入 `get_index_stats(include_config=True)` |
| `get_vision_costs` | admin | 视觉提取费用 | v0.5.0 目标：将合并入 `get_index_stats(include_vision_costs=True)` |

#### 引用类

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `get_citations` | extended | 引用网络（将合并 find_citing/find_references/get_count） | v0.5.0 目标：deprecated 3 个将移除 |
| `find_citing_papers` | extended | 被引论文 | v0.5.0 目标：将作为 deprecated 别名移除 |
| `find_references` | extended | 引用列表 | v0.5.0 目标：将作为 deprecated 别名移除 |
| `get_citation_count` | extended | 引用数 | v0.5.0 目标：将作为 deprecated 别名移除 |

#### 入库类

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `search_academic_databases` | core | 外部学术搜索 | 当前 |
| `ingest_papers` | core | 批量入库（v0.5.0 将集成 Gate 1） | 当前 |
| `get_ingest_status` | core | 入库进度查询 | 当前 |
| `save_urls` | extended | 直接 URL 保存 | 当前 |
| `save_from_url` | extended | 单 URL 保存 | v0.5.0 目标：将作为 deprecated 别名移除 |

#### 写操作类

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `create_collection` | extended | 创建集合 | 当前 |
| `create_note` | extended | 创建笔记（v0.5.0 将增加 idempotent 参数） | 当前 |
| `manage_tags` | extended | 标签 add/set/remove | 当前 |
| `manage_collections` | extended | 集合 add/remove/create | 当前 |
| `set_item_tags` | extended | 已废弃别名 | v0.5.0 目标：将移除 |
| `add_item_tags` | extended | 已废弃别名 | v0.5.0 目标：将移除 |
| `remove_item_tags` | extended | 已废弃别名 | v0.5.0 目标：将移除 |
| `add_to_collection` | extended | 已废弃别名 | v0.5.0 目标：将移除 |
| `remove_from_collection` | extended | 已废弃别名 | v0.5.0 目标：将移除 |
| `batch_tags` | extended | 已废弃别名 | v0.5.0 目标：将移除 |
| `batch_collections` | extended | 已废弃别名 | v0.5.0 目标：将移除 |

#### 管理类

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `switch_library` | admin | 切换库（v0.5.0 将增加 active session 警告） | 当前 |

#### Session 类（新增）

| 工具 | Profile Tag | 说明 | 状态 |
|---|---|---|---|
| `research_session` | core | 统一 session 管理入口（方案 C） | v0.5.0 目标：将新增 |

#### Deprecated 别名（将全部移除）

v0.5.0 目标：移除全部 15 个 deprecated 别名（原计划 v0.6.0 移除，v0.5.0 是架构大版本，提前清理）：

`list_collections`, `get_collection_papers`, `list_tags`, `get_library_overview`,
`find_citing_papers`, `find_references`, `get_citation_count`,
`set_item_tags`, `add_item_tags`, `remove_item_tags`,
`add_to_collection`, `remove_from_collection`,
`batch_tags`, `batch_collections`, `save_from_url`

**v0.4.x 迁移指引见本文档第十四节。**

---

### v0.5.0 精简决策总结

| 类别 | 决策 | 说明 |
|---|---|---|
| **移除 deprecated** | 15 个 deprecated 别名全部移除 | v0.5.0 架构大版本，已确定提前清理 |
| **提升 profile tag** | `index_library` → extended，`get_index_stats` → core | research/setup 流程依赖，不应在 admin 隐藏 |
| **合并低频工具** | 4 个合并：`get_feeds` → `browse_library(view="feeds")`；`get_unindexed_papers` / `get_reranking_config` / `get_vision_costs` → `get_index_stats` 新参数 | 减少工具总数，保留功能 |
| **新增工具** | 1 个：`research_session`（方案 C） | 统一 session 管理入口 |

工具数量演变：**28 活跃 - 4 合并 + 1 新增 = 25 活跃**（deprecated 别名 15 个全部移除）

---

## 六、新增 MCP 工具决策（已确定）

**决策：方案 C — 1 个统一 `research_session` 工具**

方案 A（+4 个工具）增加 LLM 选择负担；方案 B（集成到现有工具）使工具职责混乱；方案 D（不暴露工具）导致 LLM 无法主动查询 session 状态。方案 C 仅增加 1 个工具，与 `manage_tags` / `manage_collections` 的多职责模式一致。

### `research_session` 工具定义

| 功能 | 方式 | 说明 |
|---|---|---|
| Session 管理 | 1 个新工具 `research_session` | 统一入口，`action` 参数区分 create/get/approve/validate |
| Gate 检查 | 内嵌在 `ingest_papers` / `create_note` 等 | 不暴露为独立工具 |

```python
@mcp.tool(tags=tool_tags("core"))
def research_session(
    action: Literal["create", "get", "approve", "validate"],
    session_id: str | None = None,
    query: str | None = None,           # action=create 时
    checkpoint: str | None = None,       # action=approve 时
) -> dict:
    """Manage research workflow sessions."""
```

### 并发 session 处理

同一 library 同一时间只允许 1 个 active session（status 为 `running` 或 `awaiting_user`）。

- `research_session(action="create")` 时，若已有 active session → 返回现有 session 信息，不新建
- Skill prompt 负责展示已有 session 状态，引导用户恢复/放弃/重新开始
- 多 library 场景：每个 library_id 独立维护 session 状态，互不影响

### 已确定的所有决策

| 决策点 | 结论 |
|---|---|
| 新 MCP 工具 | 方案 C：1 个 `research_session` 工具 |
| Deprecated 移除时机 | v0.5.0 全部移除 15 个别名 |
| Profile tag 提升 | `index_library` → extended，`get_index_stats` → core |
| 低频工具精简 | 合并 4 个：`get_feeds` / `get_unindexed_papers` / `get_reranking_config` / `get_vision_costs` |
| Gate 策略 | 静默放行：无 session 时 gate 不生效（向后兼容，非 skill 调用不受限） |
| 发版范围 | 四个 Phase 全部完成才发 v0.5.0 |

---

## 七、Tool Profile 扩展

在现有 `profiles.py` 基础上新增 `research` profile：

```python
VALID_TOOL_PROFILES = {"core", "extended", "all", "research"}

PROFILE_VISIBLE_TAGS: dict[str, set[str] | None] = {
    "core": {"core"},
    "extended": {"core", "extended", "admin"},
    "all": None,
    "research": {"core", "extended", "write", "admin"},
}
```

**注意**：`index_library`（extended）和 `get_index_stats`（core）将从 admin 提升，`research` profile 包含 extended 标签，两者均可访问。

---

## 八、实施 Phase

### Phase 1：代码清理

**目标**：清理 deprecated 工具、合并低频工具、调整 profile tag、新增 research profile

**具体任务**：
1. 移除 `tools/` 各模块中 15 个 deprecated 别名的注册代码
2. 合并 4 个低频工具：
   - `get_feeds` → `browse_library` 新增 `view="feeds"` 参数
   - `get_unindexed_papers` / `get_reranking_config` / `get_vision_costs` → `get_index_stats` 新增 `limit/offset`、`include_config`、`include_vision_costs` 参数
3. 修改 `profiles.py`：`index_library` tag 改为 extended，`get_index_stats` tag 改为 core
4. 修改 `profiles.py`：新增 `research` profile（包含 core + extended + write + admin）

**退出条件**：`uv run pytest` 通过 + `zotpilot status` 显示正确工具数（25 个活跃）

### Phase 2：Skill 文件 + 分发改造

**目标**：创建 skill 文件目录、实现 deploy_skills 分发、精简 SKILL.md

**具体任务**：
1. 创建 `src/zotpilot/skills/` 目录
2. 写入 5 个 skill markdown 文件：`SKILL.md`、`ztp-research.md`、`ztp-setup.md`、`ztp-review.md`、`ztp-profile.md`
3. 在 `src/zotpilot/_platforms.py` 实现 `deploy_skills()` 函数
4. 更新 `src/zotpilot/cli.py` 的 `cmd_register` 调用 `deploy_skills()`
5. 更新 `src/zotpilot/cli.py` 的 `cmd_update` Step 3 替换为 `deploy_skills()` + editable fallback
6. 更新 `pyproject.toml`：添加 `[tool.setuptools.package-data]` 包含 `skills/*.md` 和 `references/*.md`
7. 精简根目录 `SKILL.md` 为路由 shell

**退出条件**：`pip install . && zotpilot register` 后各平台 skills_dir 有 skill 文件

### Phase 3：Research Guardrail（可选，可推迟到 v0.5.1）

**目标**：实现 session 持久化、3 个 hard gate、drift 检测

**具体任务**：
1. 创建 `src/zotpilot/workflow/` 目录（`__init__.py`）
2. 实现 `src/zotpilot/workflow/research_session.py`（ResearchSession、SessionItem、ItemFingerprint dataclasses）
3. 实现 `src/zotpilot/workflow/session_store.py`（JSON 持久化，`~/.local/share/zotpilot/sessions/`）
4. 在 `tools/ingestion.py` 的 `ingest_papers` 集成 Gate 1（Pre-Ingest check）
5. 在 `tools/write_ops.py` 的 `create_note`/`manage_tags`/`manage_collections` 集成 Gate 2（Pre-Post-Ingest check）
6. 实现 Gate 3（Pre-Resume drift 检测）在 `SessionStore.load()` 中自动触发
7. 在 `tools/write_ops.py` 或新模块实现 `research_session` MCP 工具（action=create/get/approve/validate）
8. `create_note` 新增 `idempotent` 参数（检查已有 `[ZotPilot]` 前缀 note）
9. `manage_tags` research context 默认 `action="add"`

**退出条件**：3 gates 测试通过 + session 持久化验证 + 幂等性验证

### Phase 4：文档 + 测试 + 迁移

**目标**：文档一致、测试覆盖、迁移路径清晰

**具体任务**：
1. 更新 `README.md`：反映三层架构、新 skill 引导入口
2. 更新 `docs/architecture.md`：三层架构图、workflow/ 目录说明
3. 更新 `CLAUDE.md`：添加 workflow/ 目录说明、tools/__init__.py 工具数更新
4. 编写 v0.4.x → v0.5.0 迁移指南（见本文档第十四节）
5. E2E 测试套件（见 [E2E 测试方案](zotpilot-0.5.0-e2e-test-plan.md)）

**退出条件**：文档无矛盾 + 迁移路径清晰 + E2E 通过

---

## 九、验证门控

| Gate | Phase | 退出条件 |
|---|---|---|
| Gate 1 | 1 | research profile 工具充足 + `zotpilot status` 25 个工具 |
| Gate 2 | 2 | `pip install + register` 后各平台 skill 文件就位 |
| Gate 3 | 3 | 3 hard gates 测试通过 + session 持久化 + drift 检测 |
| Gate 4 | 3 | post-ingest 幂等验证 |
| Gate 5 | 1-4 | 文档对齐 + 迁移路径清晰 + E2E 通过 |

Gate 1 和 Gate 2 可**并行**。

---

## 十、实施文件总览

### 新增

| 路径 | Phase |
|---|---|
| `src/zotpilot/skills/` 目录 | 2 |
| `src/zotpilot/skills/SKILL.md` | 2 |
| `src/zotpilot/skills/ztp-research.md` | 2 |
| `src/zotpilot/skills/ztp-setup.md` | 2 |
| `src/zotpilot/skills/ztp-review.md` | 2 |
| `src/zotpilot/skills/ztp-profile.md` | 2 |
| `src/zotpilot/workflow/__init__.py` | 3 |
| `src/zotpilot/workflow/research_session.py` | 3 |
| `src/zotpilot/workflow/session_store.py` | 3 |

### 修改

| 路径 | Phase | 内容 |
|---|---|---|
| `src/zotpilot/tools/profiles.py` | 1 | 新增 `research` profile；调整 index_library/get_index_stats tag |
| `src/zotpilot/tools/library.py` | 1 | `browse_library` 新增 `view="feeds"`；移除 `get_feeds` 注册 |
| `src/zotpilot/tools/indexing.py` | 1 | `get_index_stats` 新增参数；移除 `get_unindexed_papers`/`get_reranking_config`/`get_vision_costs` 注册 |
| `src/zotpilot/tools/citations.py` | 1 | 移除 deprecated 3 个别名注册 |
| `src/zotpilot/tools/write_ops.py` | 1+3 | 移除 deprecated 7 个别名；Gate 2 + 幂等改造 |
| `src/zotpilot/tools/ingestion.py` | 1+3 | 移除 `save_from_url` 注册；Gate 1 集成 |
| `src/zotpilot/tools/admin.py` | 1 | 移除 `get_reranking_config`/`get_vision_costs`；`switch_library` 增加 session 警告 |
| `src/zotpilot/_platforms.py` | 2 | 新增 `deploy_skills()` |
| `src/zotpilot/cli.py` | 2 | `cmd_register` + `cmd_update` 改造 |
| `pyproject.toml` | 2 | 添加 `package-data` 包含 skills/ 和 references/ |
| `SKILL.md` | 2 | 精简为路由 shell |
| `README.md` | 4 | 架构更新 |
| `docs/architecture.md` | 4 | 三层架构 |
| `CLAUDE.md` | 4 | workflow/ 目录 |

---

## 十一、多客户端支持

### 支持平台（v0.5.0）

v0.5.0 支持 6 个平台，不再支持 Cline 和 Roo Code：

| 平台 | Skill 支持 | MCP 支持 | Skill 目录 | LLM |
|---|---|---|---|---|
| Claude Code | ✅ | ✅ | `~/.claude/skills/` | Claude |
| Codex CLI | ✅ | ✅ | `~/.agents/skills/`（当前标准） | GPT |
| Gemini CLI | ⚠️ 需适配 | ✅ | `~/.gemini/skills/` | Gemini |
| Cursor | ✅ | ✅ | `~/.cursor/skills/` | Claude / GPT / 可配置 |
| OpenCode | ✅ | ✅ | `~/.config/opencode/skills/` | 可配置 |
| Windsurf | ✅ | ✅ | `~/.codeium/windsurf/skills/` | Claude / GPT / 可配置 |

> **Codex skill 路径说明**：Codex 源码（`loader.rs`）扫描两个用户级路径——`~/.codex/skills/`（deprecated）和 `~/.agents/skills/`（当前标准）。`_platforms.py` 的 Codex `skills_dir` 当前值 `~/.agents/skills` **是正确的**。`~/.agents/skills/` 是新兴跨工具 skill 共享标准，未来可能被更多客户端采用。

### MCP 层：全平台统一

MCP 工具在所有 6 个平台上行为一致：
- 25 个 MCP 工具通过标准 MCP 协议暴露
- `research_session` 工具、Gate 1/2/3 检查、Session 持久化均在 MCP server 内部实现
- 不依赖特定客户端或 LLM

### Skill 层：需要平台适配

Skill 文件（markdown prompt）的加载方式因平台而异：

| 适配项 | 说明 | Phase |
|---|---|---|
| **Gemini CLI 适配** | Gemini CLI 不直接读 skill markdown，需要通过 `GEMINI.md` 引导。`register` 命令应为 Gemini 生成引导文件 | 2 |
| **Skill frontmatter 兼容** | 各平台对 skill frontmatter 的解析可能不同。v0.5.0 使用最小化 frontmatter（仅 `name` + `description`），避免平台特定字段 | 2 |
| **MCP server instruction 增强** | 对于 skill 加载不可靠的平台，MCP server 的 description/instruction 字段应包含核心工作流提示 | 2 |

### 跨客户端 Session 恢复

ResearchSession 存储在本地 JSON 文件中（`~/.local/share/zotpilot/sessions/`），不绑定特定客户端。跨客户端恢复场景：

```
用户在 Claude Code 开始 research session → 关闭 → 在 Cursor 打开同一项目
  → Cursor 的 LLM 调用 research_session(action="get") → 发现 in-flight session
  → 提示用户恢复
```

前提：目标客户端已加载 `ztp-research` skill（否则 LLM 不知道要做这个检查）。

### 不同 LLM 的行为差异

| 层 | LLM 依赖性 | 说明 |
|---|---|---|
| Gate 1/2/3 | 无 | 代码级检查，任何 LLM 均可靠 |
| `research_session` 工具 | 无 | MCP 工具，任何 LLM 均可调用 |
| Skill prompt 指令遵循 | **有** | prompt-only skill（setup/review/profile）的检查点执行依赖 LLM 遵守指令 |
| 意图分类路由 | **有** | 兼容 shell 的路由质量取决于 LLM 理解能力 |

**缓解措施**：
- `ztp-research` 有代码级 Gate 保护，不受 LLM 差异影响
- 其他 3 个 skill 的检查点是 soft gate（建议性），LLM 跳过不会导致数据损坏
- MCP server instruction 提供基础引导，作为 skill prompt 的兜底

---

## 十二、风险预防

| 风险 | 缓解 |
|---|---|
| Prompt 不够约束 LLM | Gate 1/2 代码层兜底 |
| ResearchSession 泛化为通用引擎 | 严格限制：仅 research，拒绝泛化抽象 |
| Post-ingest 幂等不彻底 | Gate 2 保证只有 approved session 能触发写操作 |
| 兼容 shell 不缩减 | sunset 提示 + 下一版本进一步收缩 |
| 其他 skill prompt-only 不够 | 渐进路径：观察失败模式再决定是否加 guardrail |

---

## 十二、回滚方案

若 v0.5.0 升级出现严重问题，可按以下步骤回退到 v0.4.x：

### 回滚步骤

| 步骤 | 操作 | 说明 |
|---|---|---|
| 1 | 降级包 | `pip install zotpilot==0.4.x` 或 `uv tool install zotpilot==0.4.x` |
| 2 | 重启 agent | MCP 服务器需重启以加载旧版本 |
| 3 | 检查配置 | v0.4.x 的 `~/.config/zotpilot/config.json` 在 v0.5.0 中完全兼容，无需修改 |
| 4 | 检查索引 | ChromaDB 索引格式兼容，无需重建 |

### 不可逆操作

回滚前注意：
- v0.5.0 中通过 `research_session` 创建的 session 文件（`~/.local/share/zotpilot/sessions/`）在 v0.4.x 中不存在，回滚后这些文件无用但无害
- v0.5.0 中已删除的 15 个 deprecated 别名工具，回滚后重新可用
- 已入库的论文、标签、集合、笔记不受影响（写入 Zotero 的数据不依赖版本）

### 紧急联系

如遇 v0.5.0 升级问题，优先检查：
1. `zotpilot doctor --full` 输出
2. MCP 服务器日志（agent 配置中可查看）
3. `~/.local/share/zotpilot/` 目录下的 session 文件状态

---

## 十三、CCG 审核纪要

### 第一轮（2026-04-02）：Option B 技术审核

- Codex 发现：无 API Key 写入路径不存在、BatchStore 纯内存、profile 执行一次性
- Gemini 建议：checkpoint 预览列表、in-flight 检测、resume-invalidated 四选项
- 决策：JSON 主存储、SQLite anchor、Phase A 含代码骨架

### 第二轮（2026-04-04）：架构选型

- Codex 列出 7 个 prompt-only 失败模式 → prompt-only 对 research 不够
- Gemini 建议 markdown-first + 渐进加固
- **决策：转向 Option C**，仅 research 有 guardrail，其余 prompt-only

---

## 十四、v0.4.x → v0.5.0 迁移指南

### 概述

v0.5.0 是破坏性架构版本，主要变更：移除 15 个 deprecated 别名工具、合并 4 个低频工具、调整 2 个工具的 profile tag。已有的**数据（论文、标签、集合、笔记、索引）完全兼容，无需迁移**。

### 移除的 15 个 deprecated 别名及替代工具

| 移除的工具 | v0.5.0 替代工具 | 调用方式变化 |
|---|---|---|
| `list_collections` | `browse_library` | `browse_library(view="collections")` |
| `get_collection_papers` | `browse_library` | `browse_library(view="papers", collection_key=<key>)` |
| `list_tags` | `browse_library` | `browse_library(view="tags")` |
| `get_library_overview` | `browse_library` | `browse_library(view="overview")` |
| `find_citing_papers` | `get_citations` | `get_citations(doc_id=<id>, direction="citing")` |
| `find_references` | `get_citations` | `get_citations(doc_id=<id>, direction="cited")` |
| `get_citation_count` | `get_citations` | `get_citations(doc_id=<id>, direction="both")` 取 count 字段 |
| `set_item_tags` | `manage_tags` | `manage_tags(action="set", item_keys=[<key>], tags=[...])` |
| `add_item_tags` | `manage_tags` | `manage_tags(action="add", item_keys=[<key>], tags=[...])` |
| `remove_item_tags` | `manage_tags` | `manage_tags(action="remove", item_keys=[<key>], tags=[...])` |
| `add_to_collection` | `manage_collections` | `manage_collections(action="add", item_keys=[<key>], collection_key=<key>)` |
| `remove_from_collection` | `manage_collections` | `manage_collections(action="remove", item_keys=[<key>], collection_key=<key>)` |
| `batch_tags` | `manage_tags` | `manage_tags(action=<add/set/remove>, item_keys=[...], tags=[...])` |
| `batch_collections` | `manage_collections` | `manage_collections(action=<add/remove>, item_keys=[...], collection_key=<key>)` |
| `save_from_url` | `save_urls` | `save_urls(urls=[<url>])` |

### 合并的 4 个低频工具

| 移除的工具 | 合并目标 | 新调用方式 |
|---|---|---|
| `get_feeds` | `browse_library` | `browse_library(view="feeds")` |
| `get_unindexed_papers` | `get_index_stats` | `get_index_stats(limit=50, offset=0)` |
| `get_reranking_config` | `get_index_stats` | `get_index_stats(include_config=True)` |
| `get_vision_costs` | `get_index_stats` | `get_index_stats(include_vision_costs=True)` |

### Profile Tag 变更

| 工具 | v0.4.x profile | v0.5.0 profile | 影响 |
|---|---|---|---|
| `index_library` | admin | extended | 原 extended/all profile 均可访问；admin-only 配置中需升级为 extended |
| `get_index_stats` | admin | core | 所有 profile 均可访问，无需调整 |

### SKILL.md 变更

v0.5.0 的 `SKILL.md` 精简为路由 shell，原有的详细工作流说明移至各专项 skill 文件（`ztp-research.md`、`ztp-setup.md` 等）。`zotpilot register` 会自动将这些文件部署到各平台的 skills 目录。

### 配置文件和数据兼容性

- `~/.config/zotpilot/config.json`：**完全兼容**，无需修改
- ChromaDB 索引：**格式兼容**，无需重建
- 已入库数据：**完全保留**，不受影响
- v0.5.0 新增：`~/.local/share/zotpilot/sessions/` 目录（session 文件，首次使用 ztp-research 时自动创建）

---

## 十五、实施 Checklist

按 Phase 顺序排列，每个任务含文件路径，可直接作为实施者（人或 agent）的执行清单。

### Phase 1：代码清理

- [ ] `src/zotpilot/tools/library.py`：`browse_library` 新增 `view="feeds"` 参数；移除 `get_feeds` 的 `@mcp.tool` 注册
- [ ] `src/zotpilot/tools/indexing.py`：`get_index_stats` 新增 `limit/offset`、`include_config`、`include_vision_costs` 参数；移除 `get_unindexed_papers` 的 `@mcp.tool` 注册
- [ ] `src/zotpilot/tools/admin.py`：移除 `get_reranking_config` 和 `get_vision_costs` 的 `@mcp.tool` 注册
- [ ] `src/zotpilot/tools/citations.py`：移除 `find_citing_papers`、`find_references`、`get_citation_count` 的 `@mcp.tool` 注册
- [ ] `src/zotpilot/tools/ingestion.py`：移除 `save_from_url` 的 `@mcp.tool` 注册
- [ ] `src/zotpilot/tools/write_ops.py`：移除 `set_item_tags`、`add_item_tags`、`remove_item_tags`、`add_to_collection`、`remove_from_collection`、`batch_tags`、`batch_collections` 的 `@mcp.tool` 注册
- [ ] `src/zotpilot/tools/library.py`：移除 `list_collections`、`get_collection_papers`、`list_tags`、`get_library_overview` 的 `@mcp.tool` 注册
- [ ] `src/zotpilot/tools/profiles.py`：`index_library` tag 改为 `"extended"`；`get_index_stats` tag 改为 `"core"`
- [ ] `src/zotpilot/tools/profiles.py`：新增 `"research"` profile（`VALID_TOOL_PROFILES` + `PROFILE_VISIBLE_TAGS`）
- [ ] 验证：`uv run pytest` 通过；`uv run zotpilot status` 显示 25 个活跃工具

### Phase 2：Skill 文件 + 分发改造

- [ ] 创建目录 `src/zotpilot/skills/`
- [ ] 创建 `src/zotpilot/skills/SKILL.md`（路由 shell，内容参考各 skill 文档）
- [ ] 创建 `src/zotpilot/skills/ztp-research.md`（内容参考 [ztp-research 技术实现](zotpilot-0.5.0-skill-research.md)）
- [ ] 创建 `src/zotpilot/skills/ztp-setup.md`（内容参考 [ztp-setup 技术实现](zotpilot-0.5.0-skill-setup.md)）
- [ ] 创建 `src/zotpilot/skills/ztp-review.md`（内容参考 [ztp-review 技术实现](zotpilot-0.5.0-skill-review.md)）
- [ ] 创建 `src/zotpilot/skills/ztp-profile.md`（内容参考 [ztp-profile 技术实现](zotpilot-0.5.0-skill-profile.md)）
- [ ] `src/zotpilot/_platforms.py`：实现 `deploy_skills()` 函数（逻辑见 [分发与生命周期管理](zotpilot-0.5.0-distribution.md) §三）
- [ ] `src/zotpilot/cli.py`：`cmd_register` 调用 `deploy_skills()`
- [ ] `src/zotpilot/cli.py`：`cmd_update` Step 3 替换为 `deploy_skills()` + editable fallback
- [ ] `pyproject.toml`：添加 `[tool.setuptools.package-data]` 包含 `"skills/*.md"` 和 `"references/*.md"`
- [ ] 根目录 `SKILL.md`：精简为路由 shell（保留兼容性入口，指向各 skill 文件）
- [ ] 验证：`pip install -e . && zotpilot register`；检查 `~/.claude/skills/zotpilot/` 下有 5 个 skill 文件

### Phase 3：Research Guardrail（可选）

- [ ] 创建目录 `src/zotpilot/workflow/` 及 `__init__.py`
- [ ] 创建 `src/zotpilot/workflow/research_session.py`：`ResearchSession`、`SessionItem`、`ItemFingerprint` dataclasses
- [ ] 创建 `src/zotpilot/workflow/session_store.py`：JSON 持久化（`~/.local/share/zotpilot/sessions/`）
- [ ] `src/zotpilot/tools/ingestion.py`：`ingest_papers` 集成 Gate 1（`_check_pre_ingest_gate`）
- [ ] `src/zotpilot/tools/write_ops.py`：`create_note`/`manage_tags`/`manage_collections` 集成 Gate 2（`_check_post_ingest_gate`）；Gate 2 仅在 `status == "running"` 时触发（**不**拦截 `awaiting_user`）
- [ ] `src/zotpilot/workflow/session_store.py`：`load()` 时自动触发 Gate 3 drift 检测（`validate_session_items`）
- [ ] 实现 `research_session` MCP 工具（可放在 `tools/workflow.py` 或 `workflow/research_session.py`）
- [ ] `src/zotpilot/tools/write_ops.py`：`create_note` 新增 `idempotent` 参数
- [ ] `src/zotpilot/tools/write_ops.py`：`manage_tags` research context 下默认 `action="add"`
- [ ] 验证：Gate 1/2/3 单元测试通过；session 持久化测试通过；幂等性测试通过

### Phase 4：文档 + 测试 + 迁移

- [ ] `README.md`：更新为三层架构说明，setup 入口指向 `ztp-setup`
- [ ] `docs/architecture.md`：更新三层架构图、`workflow/` 目录说明
- [ ] `CLAUDE.md`：添加 `workflow/` 模块说明；更新工具数（25）
- [ ] 编写 E2E 测试套件（见 [E2E 测试方案](zotpilot-0.5.0-e2e-test-plan.md)）
- [ ] 验证：文档无矛盾；`uv run pytest -q` 通过（覆盖率 ≥ 29%）；E2E checklist 通过
