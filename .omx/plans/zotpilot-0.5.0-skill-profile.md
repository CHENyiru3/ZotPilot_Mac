# ztp-profile 技术实现文档

> 隶属于 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md) Phase 1

## 定位

`ztp-profile` 负责分析用户的 Zotero 库结构、推断研究主题、生成研究者画像，并可选地提供整理建议。

**纯 Markdown skill，无服务端 guardrail。**

## Skill 文件格式

```markdown
---
name: ztp-profile
description: Library analysis, researcher profiling, and organization recommendations
triggers:
  - "分析我的库"
  - "研究画像"
  - "profile my library"
  - "what's in my library"
  - "organize my papers"
  - "整理建议"
---
```

## 阶段模型

```
scan_library → infer_themes → [dialogue checkpoint]
    → write_profile_artifact → optional_organization_recommendations
```

### 各阶段详解

| 阶段 | 使用的 MCP 工具 | 类型 | 说明 |
|---|---|---|---|
| `scan_library` | `browse_library(view="overview")`, `browse_library(view="collections")`, `profile_library` | Deterministic | 获取库统计、集合结构、标签分布（`get_library_overview` 已合并入 `browse_library`，v0.5.0 起使用 `browse_library(view="overview")`） |
| `infer_themes` | `search_topic`, `advanced_search` | Intelligence | 推断研究主题、时间趋势、核心作者 |
| **dialogue checkpoint** | — | Soft Gate | 向用户展示推断结果，询问是否准确 |
| `write_profile_artifact` | 可选 `create_note` | Intelligence | 生成研究者画像文档 |
| `optional_organization_recommendations` | `manage_tags`, `manage_collections` | Intelligence | 建议标签清理、集合重组等 |

## 核心规则：广泛写操作需显式确认

**这是 ztp-profile 的安全原则**：

批量修改 tags/collections 前**必须**获得用户逐项或批量确认：

```
推荐整理操作：
1. 将 15 篇未分类论文归入 /ML/NLP（展示列表）
2. 清理 12 个出版商自动标签（展示列表）
3. 合并 "deep learning" 和 "Deep Learning" 标签

执行全部 / 选择性执行 / 跳过？
```

**不允许**：
- 静默执行批量 tag/collection 修改
- 在用户未确认前调用 `manage_tags(action="set", ...)`
- 删除用户手动创建的集合或标签

## Tool Profile 要求

```
ZOTPILOT_TOOL_PROFILE=extended
```

Profile 需要 `browse_library`、`profile_library`、`get_notes`、`get_annotations`（extended）+ 可选写操作。

## 输出格式

### 研究者画像

```
## 研究者画像

### 基本统计
- 论文总数: 342
- 时间跨度: 2018-2026
- 主要语言: 英文 (89%), 中文 (11%)

### 研究主题
1. **自然语言处理** (45%) — Transformer, 预训练模型, 文本生成
2. **计算机视觉** (30%) — 目标检测, 图像分割
3. **强化学习** (15%) — 多智能体, 模型预测控制
4. **其他** (10%)

### 核心引用作者
- Vaswani et al. (被引 12 次)
- ...

### 集合结构建议
- 当前: 5 个顶层集合，平均深度 1.2
- 建议: 按研究主题重组为 3 层结构
```

### 整理建议报告

单独章节，列出具体可执行的建议：
- 标签清理（合并重复、删除 publisher 标签）
- 集合重组（移动/新建/合并）
- 未分类论文归档

## 与 ztp-research 的边界

| 行为 | ztp-profile | ztp-research |
|---|---|---|
| 分析范围 | 全库 | 特定检索结果 |
| 写入类型 | 标签清理、集合重组（批量） | 单论文的 note/tag/collection |
| 发现新论文 | 不做 | 核心职责 |
| Guardrail | 无（prompt 确认规则） | ResearchSession + 3 gates |

## 与 profile_library 工具的关系

现有 `profile_library` MCP 工具提供原始数据（标签频率、集合结构、年份分布）。
`ztp-profile` skill 在此基础上做**智能分析**——推断主题、发现模式、生成建议。

关系：`profile_library` 是数据源，`ztp-profile` 是分析者。

## 测试要求

对应 Test Spec Gate 4：

| 测试项 | 验证内容 |
|---|---|
| 完整流程 | 从扫描到画像输出 |
| 写操作确认 | 批量修改前必须获得用户确认 |
| 不触发外部搜索 | 不调用 `search_academic_databases` |
