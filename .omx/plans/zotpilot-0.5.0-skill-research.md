# ztp-research 技术实现文档

> 隶属于 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md) Phase 1-3

## 定位

`ztp-research` 是 ZotPilot 的**主要证明目标**——唯一拥有服务端 guardrail 的工作流 skill。
负责完整的文献研究闭环：外部发现 → 用户审核 → 入库 → 索引 → 整理。

## Skill 文件格式

```markdown
---
name: ztp-research
description: Literature discovery, ingest, and organization workflow
triggers:
  - "帮我调研"
  - "调研近两年"
  - "find papers about"
  - "survey research on"
  - "收集文献"
  - "做文献综述"
---
```

放置路径：`src/zotpilot/skills/ztp-research.md`（随包分发，`zotpilot register` 自动部署）

## 阶段模型

```
┌─ clarify_query ──→ external_discovery ──→ score_candidates ─┐
│                                                              │
│                    [CHECKPOINT 1: candidate-review]          │
│                    用户审核候选列表，选择/排除/全选           │
│                                                              │
├─ ingest ──→ ingest_verification ─────────────────────────────┤
│                                                              │
│                    [CHECKPOINT 2: post-ingest-review]        │
│                    展示 ingest 结果 + 后续自动化步骤预览     │
│                                                              │
├─ index ──→ classify ──→ note ──→ tag ──→ final_report ──────┘
```

### 各阶段详解

| 阶段 | 使用的 MCP 工具 | 类型 | 说明 |
|---|---|---|---|
| `clarify_query` | 无 | Intelligence | LLM 与用户对话，明确检索意图、范围、年份 |
| `external_discovery` | `search_academic_databases` | Deterministic | 必须使用 ZotPilot 工具，禁止 generic web search |
| `score_candidates` | `advanced_search`（查重） | Intelligence | LLM 评分、排序、去重解释 |
| **CHECKPOINT 1** | — | Gate | 展示候选列表，等待用户选择 |
| `ingest` | `ingest_papers` | Deterministic | 调用前必须通过 Gate 1 |
| `ingest_verification` | `get_ingest_status` | Deterministic | 轮询直到 batch 终态 |
| **CHECKPOINT 2** | — | Gate | 展示结果 + 后续步骤预览列表 |
| `index` | `index_library` | Deterministic | 可重入（幂等） |
| `classify` | `manage_collections` | Intelligence | LLM 选择最深匹配子集合 |
| `note` | `create_note` | Intelligence | LLM 合成笔记（幂等模式） |
| `tag` | `manage_tags` | Intelligence | 从现有词汇选择，默认 `add` 而非 `set` |
| `final_report` | 无 | Intelligence | 逐篇汇总 |

### Intelligence vs Deterministic 分区

**Intelligence zones**（LLM 可自主判断）：
- 候选评分与排序理由
- 集合归属建议
- 笔记内容合成
- 标签选择（从 `list_tags` 返回的现有词汇中选）

**Deterministic zones**（必须严格执行，不可偏离）：
- 使用 `search_academic_databases` 而非 generic web search
- 两个 CHECKPOINT 不可跳过
- CHECKPOINT 2 通过后 downstream 步骤自动连续执行
- Post-ingest 各步骤必须使用幂等模式

## Research Guardrail Kernel

### 为什么只有 research 需要

| 比较 | ztp-research | 其他 3 个 skill |
|---|---|---|
| 写入 Zotero | 是（ingest + tags + collections + notes） | profile 可能写，review/setup 不写或少写 |
| 可逆性 | 半不可逆（ingest 难撤销） | 大部分可逆 |
| 暂停 + 恢复场景 | 常见（用户审核后暂停） | 较少 |
| Drift 风险 | 高（多论文、长时间暂停） | 低 |

### ResearchSession 生命周期

```
创建 ──→ clarify ──→ discovery ──→ scoring ──→ CHECKPOINT 1
  │                                                  │
  │                                    [awaiting_user]
  │                                                  │
  │                                    用户审批 ──→ approve_checkpoint
  │                                                  │
  ├──→ ingest ──→ verification ──→ CHECKPOINT 2 ────┤
  │                                                  │
  │                                    [awaiting_user]
  │                                                  │
  │                                    用户审批 ──→ approve_checkpoint
  │                                                  │
  ├──→ index ──→ classify ──→ note ──→ tag ──→ report
  │                                                  │
  └──────────── [completed] ─────────────────────────┘
```

**异常路径**：
- `ingest` 部分成功 → `partial_success`，保留成功条目，报告失败条目
- CHECKPOINT 2 后任意步骤失败 → 记录 `error`，跳到 `final_report`
- Resume 时 drift 检测失败 → `resume_invalidated`，等待用户决策
- 用户取消 → `cancelled`，保留已有产出

### 三个 Hard Gates

**Gate 1: Pre-Ingest**

```python
# 嵌入 ingest_papers() 内部
def _check_pre_ingest_gate(session: ResearchSession) -> None:
    if "candidate-review" not in session.approved_checkpoints:
        raise ToolError("Research session requires user approval before ingest. "
                        "Present candidates to user first.")
    if session.library_id != _get_current_library_id():
        raise ToolError("Library changed since session started. Cannot continue.")
```

触发时机：`ingest_papers()` 被调用时，检查是否存在 active session 且已通过 CHECKPOINT 1。
无 session 时：不阻断（向后兼容，非 skill 调用时不受限）。

**Gate 2: Pre-Post-Ingest**

```python
# 嵌入 write_ops 中首个写操作（create_note / manage_tags / manage_collections）
def _check_post_ingest_gate(session: ResearchSession) -> None:
    if "post-ingest-review" not in session.approved_checkpoints:
        raise ToolError("Post-ingest steps require user approval after ingest verification.")
```

触发时机：在 research session 上下文中调用 `create_note` / `manage_tags` / `manage_collections` 时。

判断"research session 上下文"：检查当前 library 是否有 **`status == "running"`** 的 active session。

> **设计说明（为何选择 `running` 而非 `running | awaiting_user`）**：
> Gate 2 的目的是防止用户手动操作（如直接调用 `create_note`）在未通过 CHECKPOINT 2 审批时写入 Zotero。
> `awaiting_user` 表示 session 正在等待用户在 CHECKPOINT 处决策，此时用户有可能在另一个对话中手动操作——
> 这种手动操作**不应被拦截**，因为用户本来就有权直接操作工具。
> 只有 `running` 状态（skill 正在自动推进 downstream 步骤时）才需要 Gate 2 保护，
> 确保自动化写操作必须以用户的显式 CHECKPOINT 2 审批为前提。

**Gate 3: Pre-Resume**

```python
def validate_session_items(session: ResearchSession) -> list[DriftDetail]:
    """校验所有 session items 的 fingerprint。"""
    zotero = _get_zotero()
    drifted = []
    for item in session.items:
        if item.fingerprint is None:
            continue
        current = zotero.get_item(item.item_key)
        if current is None:
            drifted.append(DriftDetail(item_key=item.item_key, reason="deleted"))
        elif current.date_added != item.fingerprint.date_added:
            drifted.append(DriftDetail(item_key=item.item_key, reason="replaced"))
        elif not current.title.startswith(item.fingerprint.title_prefix):
            drifted.append(DriftDetail(item_key=item.item_key, reason="title_changed"))
    return drifted
```

触发时机：session 从磁盘恢复时（`SessionStore.load()` → 自动 validate）。
失败行为：状态置为 `resume_invalidated`，返回 drift 详情，由 Skill prompt 引导用户决策。

### Fingerprint 采集时机

- **ingest 成功后**：为每个成功的 `SessionItem` 创建 `ItemFingerprint`
- **每个 post-ingest 步骤完成后**：更新 `note_count`（防止 note 重复检测失误）

### Tool Profile 要求

Skill prompt 首部声明：

```
本工作流需要 ZOTPILOT_TOOL_PROFILE=research
该 profile 暴露以下工具：search_academic_databases, advanced_search,
get_paper_details, ingest_papers, get_ingest_status, index_library,
browse_library, manage_tags, manage_collections, create_note, ...
```

## Post-Ingest 幂等规则

| 操作 | 幂等策略 |
|---|---|
| `index_library(item_key=X)` | 天然幂等（重复 index 同一 item 安全） |
| `create_note(item_key=X, ...)` | 检查该 item 是否已有 `[ZotPilot]` 前缀 note；有则跳过 |
| `manage_collections(action="add", ...)` | 天然幂等（已在 collection 中时 API 返回成功） |
| `manage_tags(action="add", ...)` | 默认 `add`（追加），不用 `set`（替换） |
| `manage_tags(action="set", ...)` | 仅在 Skill prompt 显式要求"清理 publisher auto-tags"时使用 |

## 自动检测 In-Flight Session

Skill prompt 指示 LLM 在工作流开始时：

```
1. 调用 research_session(action="get") 检查是否有 active session
   （active = status 为 running 或 awaiting_user）
2. 若有未完成的 session：
   - 展示 session 状态（阶段、已处理条目数）
   - 询问用户：恢复 / 放弃 / 重新开始
3. 若无：调用 research_session(action="create", query=<用户意图>) 创建新 session
```

这是 prompt-level 逻辑。`research_session` 是一个 MCP 工具调用，不是代码级拦截。

> **`active session` 定义**：在 UX 上下文（自动检测 in-flight session）中，"active"包含
> `status == "running"` 和 `status == "awaiting_user"` 两种状态，用于向用户展示未完成的工作。
> Gate 2 的代码判断仅用 `running`（见上方 Gate 2 设计说明）。

### 各阶段 research_session 调用

| 时机 | 调用方式 | 说明 |
|---|---|---|
| 工作流开始 | `research_session(action="get")` | 检测 in-flight session（含 running + awaiting_user） |
| 无 session 时 | `research_session(action="create", query=...)` | 创建新 session |
| CHECKPOINT 1 用户审批后 | `research_session(action="approve", checkpoint="candidate-review")` | 解锁 Gate 1 |
| CHECKPOINT 2 用户审批后 | `research_session(action="approve", checkpoint="post-ingest-review")` | 解锁 Gate 2 |
| Resume 时验证 | `research_session(action="validate", session_id=...)` | 触发 drift 检测 |

## 无 RAG 模式说明

当 `embedding_provider=none` 时（无向量索引），`index` 阶段处理方式：

- `index_library` 调用会返回 `{"skipped": true, "reason": "embedding_provider=none"}`，不报错
- `search_papers` / `search_topic` 等语义搜索工具不可用，Skill prompt 应跳过 `cluster_topic` 阶段
- `advanced_search` 仍可用（直接查 SQLite 元数据），`classify` / `note` / `tag` 阶段不受影响
- 向用户说明：本次研究流程跳过语义索引，仅元数据层写操作正常执行

## 向后兼容说明

**无 session 时 gate 静默放行**：

- 非 `ztp-research` skill 调用 `ingest_papers`（如用户直接在 Claude Code 中调用）→ Gate 1 不生效，正常执行
- 非 research session 上下文中调用 `create_note` / `manage_tags` / `manage_collections` → Gate 2 不生效
- 判断"是否在 session 上下文"：检查当前 library 是否有 **`status == "running"`** 的 session

> **`awaiting_user` 不拦截手动操作**：当 session 处于 `awaiting_user`（等待用户在 CHECKPOINT 处决策）时，
> 用户可能在另一个对话中手动调用 `create_note` 等工具。Gate 2 **不拦截**此类手动操作——
> 只有 skill 在 `running` 状态下自动推进写操作时才触发 Gate 2。
> 这确保了 v0.4.x 的调用模式在 v0.5.0 中继续工作，不需要任何迁移操作。

## Final Report 格式

```
## 研究报告

### 汇总
- 总计: 8 篇 | 成功: 6 | 失败: 1 | 跳过: 1

### 逐篇状态

| # | 标题 | 状态 | 集合 | 标签 | 笔记 |
|---|---|---|---|---|---|
| 1 | Paper A | done | /ML/Transformers | NLP, Attention | ✓ |
| 2 | Paper B | done | /ML/Transformers | NLP | ✓ |
| 3 | Paper C | failed | — | — | — |
| ... | ... | ... | ... | ... | ... |

### 阻塞器
- Paper C: ingest 超时（connector 无响应）
```

## 测试要求

对应 Test Spec 的 Gate 2：

| 测试项 | 验证内容 |
|---|---|
| E2E 1: 规范化研究流程 | 两个 checkpoint 强制执行，downstream 自动运行 |
| 负面控制: checkpoint bypass | 未 approve 时调用 ingest_papers 返回 ToolError |
| 负面控制: wrong-library | session 的 library_id 与当前不一致时阻断 |
| Drift 检测 | 删除 item 后 resume → `resume_invalidated` |
| Partial success | 3 篇中 1 篇失败 → 保留 2 篇的 post-ingest 产出 |
| 幂等性 | 重复执行 post-ingest 不产生 duplicate note/tag |
| 向后兼容 | 非 session 上下文中 ingest_papers 正常工作（无 gate 阻断） |
| Gate 2 不拦截 awaiting_user | session 处于 awaiting_user 时手动调用 create_note 正常执行 |
