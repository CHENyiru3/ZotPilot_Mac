# ZotPilot Workflow Runtime Contract（当前版本）

## 文档定位

本文档是 Phase A 的交付物，属于实现级合同，不是规划摘要。

权威关系：
- 本文档描述的合同**优先于** `final-implementation-doc-ztp-current-version.md` 中的草案描述
- 测试权威仍为 `test-spec-ztp-lifecycle-architecture.md`
- 代码骨架位于 `src/zotpilot/workflow/state.py`（与本文档同期交付）

Phase A 退出条件：本文档与骨架代码均已交付，且两者之间无矛盾。

---

## 状态存储决策

**主要存储：本地 JSON 文件**

```
~/.local/share/zotpilot/workflows/<workflow_id>.json   # Unix
%LOCALAPPDATA%\zotpilot\workflows\<workflow_id>.json   # Windows
```

规则：
- 进程重启后状态必须可恢复
- 不依赖 `ZOTERO_API_KEY`
- 文件由 `WorkflowStore` 独占写入，其他模块只读

**可选增强：Zotero tracking note**

条件：仅当 `ZOTERO_API_KEY` 已配置时写入。  
格式：Zotero 笔记，标题为 `[ZotPilot Workflow: <workflow_id>]`，附在该批次第一篇论文上。  
作用：让用户在 Zotero 客户端里看到进行中的工作流；不作为恢复的信息来源。

---

## Workflow 状态 Schema

### WorkflowState（顶层对象）

| 字段 | 类型 | 说明 |
|---|---|---|
| `workflow_id` | `str` | `wf_<hex12>`，全局唯一 |
| `workflow_type` | `WorkflowType` | 见下方枚举 |
| `status` | `WorkflowStatus` | 见下方枚举 |
| `stage` | `str` | 当前所在阶段名称（见各 workflow 定义） |
| `active_checkpoint` | `CheckpointId \| None` | 当前等待用户审批的检查点 ID |
| `allowed_capability_pack` | `str` | 当前允许调用的能力包名称 |
| `resume_token` | `str \| None` | 恢复标识，用于绑定 in-flight 的 batch_id 等 |
| `blocker_reason` | `str \| None` | 进入 blocked/restart-required 的原因 |
| `next_resumable_action` | `str \| None` | 恢复后应执行的第一个动作描述 |
| `completed_outputs` | `list[OutputRecord]` | 已完成的产出列表（note key、tag 等） |
| `partial_failures` | `list[FailureRecord]` | 部分失败的条目 |
| `items` | `list[WorkflowItemState]` | 多论文工作流的逐篇状态 |
| `anchor` | `WorkflowAnchor` | 与 Zotero 状态的锚定信息 |
| `created_at` | `str` | ISO 8601 时间戳 |
| `updated_at` | `str` | ISO 8601 时间戳 |

### WorkflowType 枚举

```python
"research" | "setup" | "review" | "profile"
```

### WorkflowStatus 枚举

| 状态 | 含义 |
|---|---|
| `running` | 正在执行，无需用户介入 |
| `awaiting_user` | 在检查点等待用户审批 |
| `partial-success` | 部分条目成功，部分失败，等待决策 |
| `blocked` | 遇到外部阻塞（如 anti-bot），需用户解决 |
| `restart-required` | MCP 重启后才能继续（如注册新配置） |
| `resume-invalidated` | 检测到 Zotero 侧 drift，需用户显式决策 |
| `completed` | 所有阶段成功完成 |
| `cancelled` | 用户主动取消 |
| `failed` | 不可恢复的失败 |

### CheckpointId 枚举

```python
"candidate-review"    # 外部发现后，用户审核候选论文列表
"post-ingest-review"  # ingest 验证后，用户确认执行后续整理步骤
"restart-required"    # 需要重启才能继续
```

---

## WorkflowItemState Schema

每篇论文在多论文工作流中的独立状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| `item_key` | `str \| None` | Zotero item key（ingest 成功后填入） |
| `url` | `str \| None` | 来源 URL |
| `title` | `str \| None` | 论文标题 |
| `status` | `ItemStatus` | 见下方枚举 |
| `stage_completed` | `list[str]` | 已完成的阶段列表 |
| `error` | `str \| None` | 失败原因 |

### ItemStatus 枚举

```python
"pending" | "ingested" | "indexed" | "noted" | "tagged" | "done" | "failed" | "skipped"
```

---

## Native Workflow Anchor

### 目的

在工作流暂停期间检测用户在 Zotero 客户端做的手动修改（drift），防止工作流在错误假设下继续执行。

### 实现方式

Anchor 使用**只读 SQLite 快照**，不依赖 API Key。

**WorkflowAnchor Schema：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `snapshot_at` | `str` | 快照时间（ISO 8601） |
| `item_snapshots` | `list[ItemSnapshot]` | 各论文的状态快照 |
| `zotero_note_key` | `str \| None` | tracking note 的 Zotero key（可选，有 API Key 时填入） |

**ItemSnapshot Schema：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `item_key` | `str` | Zotero item key |
| `date_added` | `str` | 来自 SQLite `items.dateAdded` |
| `title_prefix` | `str` | 标题前 50 个字符，用于变更检测 |

### Drift 定义

以下任一情况判定为 drift：

1. workflow 记录的 `item_key` 在 SQLite `items` 表中不再存在（条目被删除）
2. `date_added` 发生变化（条目被替换）
3. `title_prefix` 发生变化（条目被替换为不同论文）

**不触发 drift 的变化**（因为工作流本身会修改这些）：
- tags 变化
- collections 变化
- 笔记内容变化

### Delta Check 触发点

以下阶段开始前**必须**执行 delta check：

1. `index` 阶段开始前
2. `classify` 阶段开始前
3. `note` 阶段开始前
4. `tag` 阶段开始前
5. 从 `restart-required` 恢复时

**Delta check 失败处理**：
- 将状态置为 `resume-invalidated`
- 记录 `blocker_reason`（哪些 item_key 消失或变化）
- 等待用户显式决策后方可继续

---

## Capability Pack 策略

### 当前版本的包定义

| 包名 | 工作流 | 包含工具类别 |
|---|---|---|
| `research` | `ztp-research` | 发现、ingest、索引、写操作 |
| `setup` | `ztp-setup` | 配置、诊断、注册 |
| `profile` | `ztp-profile` | 库浏览、分析、只读 |
| `review` | `ztp-review` | 搜索、段落提取、可选引用扩展 |

兼容别名（不作为主要合同）：`core`、`extended`、`all`

### 策略执行层次

1. **主要机制**：skill 文件 prompt 约束（防止 LLM 调用范围外工具）
2. **加固机制**：`WorkflowRuntime.check_capability(tool_name)` 在工具调用前校验（Phase B 实现）

Phase C（ztp-research 证明）不依赖代码级 capability 拦截，prompt 层约束即可。

---

## 策略所有权映射

| 关注点 | 所有者 |
|---|---|
| 阶段顺序 | Workflow skill（prompt） |
| 检查点门控 | `WorkflowRuntime`（代码） |
| Capability 允许/拒绝 | `WorkflowRuntime`（Phase B 加固） |
| 状态持久化 | `WorkflowStore`（代码） |
| Partial-success 推进 | `WorkflowRuntime`（代码） |
| Delta check 执行 | `WorkflowRuntime` 调用 `AnchorChecker`（代码） |
| 恢复有效性校验 | `WorkflowRuntime`（代码） |
| Generic web drift 阻断 | Skill prompt（主要）+ capability check（加固） |

---

## resume-invalidated 处理

当 `AnchorChecker.check()` 发现 drift 时：

1. 将 `WorkflowState.status` 置为 `resume-invalidated`
2. 在 `blocker_reason` 中记录具体 drift 信息
3. 在 `next_resumable_action` 中说明用户需要做的决策
4. **等待用户显式决策**，工作流不得自动继续

用户选项的具体定义推迟到 Phase C（实现 `ztp-research` 时）。
当前版本 contract 仅要求：用户决策必须是**显式的**，系统不得静默降级或自动跳过。

---

## 多客户端 resume 规则

- CLI（setup/update）可在 MCP 不可用时创建和推进 workflow state
- 后续 MCP/skill 会话必须能发现可恢复的 workflow 并从上次检查点继续
- OMX state 可为 Codex 会话镜像进度，但不是跨客户端的信息来源
- **跨客户端信息来源**：`~/.local/share/zotpilot/workflows/<workflow_id>.json`

---

## 代码骨架交付说明

与本文档同期交付：

```
src/zotpilot/workflow/__init__.py
src/zotpilot/workflow/state.py      # dataclasses（WorkflowState、WorkflowAnchor 等）
src/zotpilot/workflow/store.py      # WorkflowStore（JSON 读写）
src/zotpilot/workflow/runtime.py    # WorkflowRuntime（存根，无逻辑）
src/zotpilot/workflow/anchor.py     # AnchorChecker（存根，无逻辑）
```

骨架规则：
- 所有 dataclass 字段与本文档 schema 一致
- 方法签名存在但实现为 `raise NotImplementedError`
- `WorkflowStore.load` / `WorkflowStore.save` 完整实现（Phase C 需要用）

---

## Phase A 退出条件

- [ ] 本文档已完成，无未解决的歧义
- [ ] `src/zotpilot/workflow/` 骨架已创建，dataclass 字段与本文档一致
- [ ] `WorkflowStore.load` / `WorkflowStore.save` 可用
- [ ] `test-spec` 的 Gate 1 中"workflow contract unit coverage target defined"可以开始制定
