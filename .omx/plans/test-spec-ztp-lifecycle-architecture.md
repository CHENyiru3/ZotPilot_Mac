# Test Spec: ZotPilot v0.5.0 Lifecycle Architecture

## Scope

Validate the v0.5.0 architecture refactor that introduces workflow-first skill surfaces while preserving one MCP server and compatibility for existing users.

Validation rule:
- 本文档是当前版本交付物的验证权威
- 实现变更范围时，必须在工作被认为完成之前更新本文档
- 每个 gate 必须有具体证据（代码引用、测试名、命令输出、运行时日志），不接受仅凭 prose 通过

Primary workflows:
- `ztp-setup`
- `ztp-research`
- `ztp-review`
- `ztp-profile`
- `ztp-guider` 推迟到下个版本，除非后续产品决策重新提升
- 兼容 shell 位于根目录 `SKILL.md`

## Test Goals

1. 确认工作流 skill 是可执行契约，而非仅 prose 说明
2. 确认显式工作流调用不偏离允许路径
3. 确认默认 profile 对各工作流有充足能力（Tool Profile 测试）
4. 确认 clean-machine bootstrap 和 post-registration MCP 阶段均正确建模
5. 确认生命周期文档、CLI、运行时行为对齐
6. 确认迁移保留过渡期内的 legacy 入口行为
7. 确认旧 umbrella 工作流节已映射到专项 skill、吸收到子流程、或明确保留在兼容 shell 中
8. 确认当前 MCP 工具正确分类为：直接复用、提升进 `research` profile、或内部修复

Out of validation scope for this version:
- `ztp-guider` 行为（除证明其已推迟外）
- Capability Pack 体系的兼容性保证（v0.5.0 不建此体系）

## Verification Matrix

| Area | Proof |
| --- | --- |
| Setup lifecycle | 新 setup 工作流从 clean machine 到 ready state |
| Update lifecycle | `zotpilot update` 在三种安装模式下语义正确 |
| Research workflow | 用户审核和 post-ingest checkpoint 被强制执行 |
| Post-ingest continuation | 审批后 downstream 步骤自动运行并报告完成 |
| Negative controls | generic-web drift 和 Gate bypass 被可见阻断 |
| Compatibility shell | 旧式请求路由到专项工作流或明确提示 |
| Legacy mapping | 旧 umbrella 工作流有明确目标，无孤立 surface |
| MCP repair | 当前工具 surface 分类修复，不破坏单服务器契约 |
| Developer lifecycle | 文档、计划产物、代码边界对齐 |

## Evidence Format

每个验证项必须产生以下之一或多项：
- 代码引用（文件:行号）
- 单元/集成/E2E 测试名称
- 命令调用
- 运行时日志或状态产物
- 带结果的手动 QA 记录

最低证据规则：
- 任何 gate 不得仅凭 prose 通过
- 每个通过的 gate 必须引用具体证据产物或测试运行

## Unit Tests

### Workflow Contract

- 每个工作流的阶段转换规则
- checkpoint gating 规则
- allowed intelligence-zone policy
- blocker 和 resume 状态序列化
- 失败状态转换：`failed`、`cancelled`、`partial-success`、`restart-required`、`resume-invalidated`
- native workflow anchor 生命周期和 delta-check 规则
- 每个工作流的能力充足性检查
- setup 的 clean-machine bootstrap 与 post-registration continuation 规则

### Tool Profile Policy

- Tool Profile（`core` / `extended` / `all` / `research`）对应工具集的映射测试
- `research` profile 包含 `index_library`（extended）和 `get_index_stats`（core）的可访问性验证
- 各工作流所需 profile 的能力充足性检查（`ztp-research` 需要 `research` profile，`ztp-setup` 需要 `extended`，其他需要 `core`）
- `awaiting_user` 状态不触发 Gate 2 的验证（手动工具调用不被拦截）
- Gate 2 仅在 `status == "running"` 时触发的验证
- profile 不兼容时的 blocker 行为

### Compatibility

- 根 skill 路由逻辑
- legacy 别名保留行为（v0.5.0 中全部移除，回滚时重现）
- deprecation 警告发出
- legacy 工作流节映射与 PRD 一致

## Integration Tests

### Setup / Update

- `setup` + `register` + restart-required 路径（clean config 目录）
- `update` 三种安装模式验证：
  - editable install
  - uv install
  - pip install
- skill update dirty-tree 和 symlink 保护完整
- clean-machine setup 不假设 MCP 已可用
- post-restart continuation 可验证 MCP 就绪状态和首次索引
- update 失败恢复路径：locked binary、unknown installer、dirty skill tree

Required evidence:
- `editable`、`uv`、`pip` 三种模式各有一条验证路径
- restart 或 updater guard 行为的一条失败路径证明

### Workflow Capability Integration

- `ztp-research` 可按预期顺序调用 discovery、ingest、verification、indexing、写操作
- 默认 `research` profile 能力充足性测试（25 个活跃工具中 research profile 可见的工具集）
- `ztp-profile` 将库分析与可选写操作集成
- 工作流状态持久化和 resume 在强制 checkpoint 后存活
- partial-success 处理保留已完成的逐篇输出，仅重试失败子集
- blocked generic-web 和 disallowed gate bypass 尝试给出含工作流/阶段上下文的错误
- native workflow anchor 在 resume 前检测 Zotero 侧 drift
- 当前工具正确分桶：
  - 直接复用工具可调用
  - 提升的工具（`index_library`→extended，`get_index_stats`→core）在 `research` profile 下可达
  - 修复的工具边界保持稳定外部契约

Required evidence:
- 一份能力矩阵产物
- 一份运行时策略失败产物
- 一份提升工具在 `research` profile 下可达的证明

## End-to-End Tests

### E2E 场景清单（18 个）

#### 研究工作流（7 个）

| # | 场景名 | 输入 | 预期结果 |
|---|---|---|---|
| E2E-01 | 规范化研究流程 | 用户通过 `ztp-research` 请求某主题最新文献 | 外部发现→候选列表→CHECKPOINT 1 暂停→用户审批→ingest→ingest 验证→CHECKPOINT 2 暂停→用户审批→index/classify/note/tag 自动运行→final report |
| E2E-02 | CHECKPOINT bypass 阻断 | 未经 CHECKPOINT 1 审批直接调用 `ingest_papers`（含 session） | Gate 1 返回 ToolError，提示需先展示候选列表 |
| E2E-03 | wrong-library 阻断 | session 建立后切换库，再调用 `ingest_papers` | Gate 1 检测 library_id 不一致，返回 ToolError |
| E2E-04 | Post-ingest drift 阻断 | CHECKPOINT 2 前手动删除已入库论文，再尝试继续 | Gate 3 检测 drift，状态置为 `resume_invalidated`，提示用户决策 |
| E2E-05 | Partial success 处理 | 3 篇中 1 篇 ingest 失败 | 保留 2 篇的 post-ingest 产出；失败篇记录在 final report 阻塞器节 |
| E2E-06 | 幂等性验证 | 对同一 session 重复执行 post-ingest（note + tag） | 不产生 duplicate note；tag 追加而非覆盖 |
| E2E-07 | 向后兼容（无 session 直接调用） | 无 session 上下文下直接调用 `ingest_papers` | Gate 1 不生效，正常执行 |

#### Gate 2 语义验证（2 个）

| # | 场景名 | 输入 | 预期结果 |
|---|---|---|---|
| E2E-08 | Gate 2 仅拦截 `running` | session 处于 `running`，未经 CHECKPOINT 2 审批调用 `create_note` | Gate 2 返回 ToolError |
| E2E-09 | Gate 2 不拦截 `awaiting_user` | session 处于 `awaiting_user`（等待 CHECKPOINT 1 决策），手动调用 `create_note` | Gate 2 不生效，`create_note` 正常执行 |

#### Setup 工作流（3 个）

| # | 场景名 | 输入 | 预期结果 |
|---|---|---|---|
| E2E-10 | Clean-machine setup | 无配置环境，Zotero 已安装 | `ztp-setup` 执行 detect→provider 选择→config 写入→register→restart 提示→重启后 index-ready 验证 |
| E2E-11 | restart-required 边界 | pre-MCP 阶段不调用 MCP 工具 | restart 前各阶段仅 CLI 命令；重启后才调用 `get_index_stats` |
| E2E-12 | 升级路径 | 已安装 v0.4.x，请求升级 | `zotpilot update` 正确检测安装模式，更新 CLI + 部署新 skill 文件 |

#### Compatibility Shell（2 个）

| # | 场景名 | 输入 | 预期结果 |
|---|---|---|---|
| E2E-13 | 旧式模糊请求路由 | 通过根 `SKILL.md` 发出旧式模糊请求（如"帮我整理文献"） | 路由到对应专项 skill（`ztp-profile` 或 `ztp-research`），不在 shell 内静默重实现工作流 |
| E2E-14 | Legacy 别名移除后提示 | v0.5.0 中调用已移除的 deprecated 别名（如 `list_collections`） | 返回明确错误或提示，说明替代工具（`browse_library(view="collections")`） |

#### Review/Profile 工作流（2 个）

| # | 场景名 | 输入 | 预期结果 |
|---|---|---|---|
| E2E-15 | Review 工作流（local-first） | 主题综述请求通过 `ztp-review` | 先搜索本地库；本地结果充足时不触发外部搜索；产出综述 |
| E2E-16 | Profile 工作流（批量写确认） | 库画像 + 标签整理请求通过 `ztp-profile` | `profile_library` 分析→建议→用户确认→批量写操作（`manage_tags`/`manage_collections`） |

#### 无 RAG 模式（1 个）

| # | 场景名 | 输入 | 预期结果 |
|---|---|---|---|
| E2E-17 | 无 RAG 模式降级 | `embedding_provider=none` 下运行 `ztp-research` | `index_library` 返回 skipped；语义搜索跳过；`classify`/`note`/`tag` 正常执行；向用户说明降级情况 |

#### Session Resume（1 个）

| # | 场景名 | 输入 | 预期结果 |
|---|---|---|---|
| E2E-18 | Session resume 验证 | 中断的 `ztp-research` 在 CHECKPOINT 1 或 partial ingest 后重启 | resume 从持久化状态加载；drift 检测通过→继续；或 `resume_invalidated`→用户决策 |

---

### E2E 场景详细步骤（关键场景）

#### E2E-01：规范化研究流程（详细步骤）

1. 触发 `ztp-research`，输入研究主题
2. `research_session(action="get")` → 无 active session
3. `research_session(action="create", query=<主题>)` → 创建 session
4. `search_academic_databases(query=<主题>, limit=20)` → 候选列表
5. `advanced_search(...)` → 查重，评分候选
6. 展示候选列表，**CHECKPOINT 1 暂停**，等待用户选择
7. 用户选择后 → `research_session(action="approve", checkpoint="candidate-review")`
8. `ingest_papers(papers=[...])` → 返回 `batch_id`
9. 轮询 `get_ingest_status(batch_id=...)` 直到终态
10. 展示 ingest 结果，**CHECKPOINT 2 暂停**，展示后续步骤预览
11. 用户确认 → `research_session(action="approve", checkpoint="post-ingest-review")`
12. `index_library(item_key=...)` × N（逐篇）
13. `manage_collections(action="add", ...)` × N
14. `create_note(item_key=..., idempotent=True, ...)` × N
15. `manage_tags(action="add", ...)` × N
16. 输出 final report（汇总表 + 阻塞器）

预期证据：session JSON 文件存在于 `~/.local/share/zotpilot/sessions/`；两个 approved_checkpoints 均记录；final report 包含所有篇目状态。

#### E2E-08/09：Gate 2 语义验证（详细步骤）

**E2E-08**（Gate 2 拦截 running）：
1. 创建 research session，完成 CHECKPOINT 1 审批
2. `ingest_papers` 成功，session 状态变为 `running`
3. 不执行 CHECKPOINT 2 审批，直接调用 `create_note(item_key=..., content="test")`
4. 预期：Gate 2 触发，返回 ToolError（`"Post-ingest steps require user approval..."`）

**E2E-09**（Gate 2 不拦截 awaiting_user）：
1. 创建 research session，session 状态为 `awaiting_user`（等待 CHECKPOINT 1）
2. 在另一上下文中直接调用 `create_note(item_key=..., content="manual note")`
3. 预期：Gate 2 不触发，`create_note` 正常执行，返回成功

---

## Observability / Diagnostics

添加以下可观测性证据点：

- workflow id、阶段、status 转换
- checkpoint 进入 / checkpoint 审批
- disallowed capability 尝试
- workflow resume 事件
- 失败状态转换和恢复尝试
- final workflow 摘要
- 能力充足性失败
- bootstrap 阶段 vs MCP 阶段转换

最低预期：
- 失败可归因到具体阶段和策略，而非仅原始工具错误

Required observable checkpoints:
- 用户审核 gate 之前
- ingest 验证之后
- post-ingest continuation 之前
- delta check 之后 resumed downstream 阶段之前

## Regression Targets

- 当前 ingestion 验证行为
- 当前 update 保护措施
- 当前 no-RAG fallback 行为
- 当前 connector 可用性检查
- 当前 compatibility 别名（v0.5.0 移除前的迁移期行为）
- 当前 release/version coupling 假设

## Manual QA Checklist

1. 在 clean 环境 profile 上运行 setup 流程
2. 运行 research 流程处理一个主题，验证两个强制 checkpoint
3. 确认未显式允许时不使用 generic web 路径
4. 审批 continuation，确认 post-ingest 自动完成
5. 验证 notes/tags/collections 与 final report 一致
6. 通过 `zotpilot update` 升级，验证 skill/version 消息
7. 确认 README 和 architecture 文档描述相同的工作流 surface
8. 确认 release 文档仍说明版本同步、分支流程、connector 打包边界
9. 确认 blocked generic-web 和 disallowed gate bypass 产生可见策略失败
10. 确认 `restart-required`、partial-success、`resume-invalidated` 流程可观测且可恢复
11. 确认旧 `Direct Ingest`、`Local Search`、`Organize` 路径作为子流程或吸收流程反映，而非孤立 surface
12. 确认 `research` profile 包含 index/classify/note/tag 完成所需的提升工具（`index_library`、`get_index_stats`）
13. 确认 workflow anchor 在 resumed run 继续前检测到 Zotero 侧手动编辑
14. 确认 Gate 2 在 `awaiting_user` 状态时不拦截手动工具调用（E2E-09）
15. 确认 15 个 deprecated 别名已移除，调用时返回明确错误及替代工具说明

## Exit Criteria

- 所有工作流契约有单元测试覆盖
- 所有生命周期流程至少有一条集成测试路径
- 规范化研究流程有 E2E 覆盖（E2E-01）
- 兼容 shell 行为已验证（E2E-13/14）
- Update 证明覆盖 `editable`、`uv`、`pip` 三种模式 + dirty-tree/symlink 保护 + post-restart 验证
- 开发/release 证明覆盖版本同步、tag/push/release gating、不可逆边界停止
- Legacy umbrella 工作流节有明确映射目标，无未解决的孤立行为
- MCP repair 范围已证明：直接复用工具可用，提升工具完成默认 research 循环，修复工具边界不引入错误层次
- 文档和运行时命名对齐，无未解决矛盾
- Tool Profile 测试覆盖 core/extended/all/research 四个 profile 的工具可见性
- Gate 2 语义（仅拦截 `running`，不拦截 `awaiting_user`）有专项测试（E2E-08/09）

## Gate Mapping

### Gate 1: Contract Ready

Requires:
- 工作流契约单元测试覆盖目标已定义
- 能力矩阵存在
- Tool Profile policy 可测试

### Gate 2: `ztp-research` Proof Ready

Requires:
- E2E-01 通过
- E2E-02/03/04 负面控制产生可见失败
- E2E-08/09 Gate 2 语义验证通过
- anchor/delta-check 行为已证明（E2E-04/18）

### Gate 3: `ztp-setup` Ready

Requires:
- E2E-10 通过
- E2E-11 restart-required 行为已证明
- E2E-12 update/install 模式证据存在

### Gate 4: Secondary Skills Ready

Requires:
- E2E-15/16 通过
- local-library-first 行为已证明（E2E-15）

### Gate 5: Migration Ready

Requires:
- E2E-13/14 通过
- legacy mapping 检查通过
- 文档和兼容性注释对齐
- 15 个 deprecated 别名移除验证通过
