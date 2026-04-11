# ztp-review 技术实现文档

> 隶属于 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md) Phase 1

## 定位

`ztp-review` 负责基于本地 Zotero 库的文献综述与合成：聚焦用户已有的论文，提取段落、聚类主题、生成综述。

**纯 Markdown skill，无服务端 guardrail。**

## Skill 文件格式

```markdown
---
name: ztp-review
description: Local library review and literature synthesis
triggers:
  - "文献综述"
  - "综述"
  - "review my papers on"
  - "summarize research on"
  - "what does my library say about"
---
```

## 阶段模型

```
clarify_review_topic → local_library_scope → cluster_topic
    → extract_passages → optional_citation_expansion
    → outline → synthesis → [refinement checkpoint] → final_review
```

### 各阶段详解

| 阶段 | 使用的 MCP 工具 | 类型 | 说明 |
|---|---|---|---|
| `clarify_review_topic` | 无 | Intelligence | 与用户确认综述主题、范围、深度 |
| `local_library_scope` | `search_topic`, `advanced_search` | Deterministic | 在本地库中界定范围，筛选相关论文 |
| `cluster_topic` | `search_papers` | Intelligence | 按子主题聚类，识别主要研究方向 |
| `extract_passages` | `search_papers`, `get_passage_context` | Deterministic | 提取关键段落，包含引用信息 |
| `optional_citation_expansion` | `get_citations` | Intelligence | 如用户需要，查询引用网络扩展视野 |
| `outline` | 无 | Intelligence | 生成综述大纲，呈现给用户 |
| `synthesis` | `get_paper_details` | Intelligence | 撰写综述文本，引用具体段落 |
| **refinement checkpoint** | — | Soft Gate | 用户反馈，可选修改方向 |
| `final_review` | 可选 `create_note` | Intelligence | 最终输出，可选写入 Zotero note |

## 核心规则：Local-Library-First

**这是 ztp-review 的基本原则**：

1. 所有搜索首先在本地已索引库中执行
2. 不主动调用 `search_academic_databases`（那是 `ztp-research` 的职责）
3. 仅在用户**明确请求**扩展时使用 `get_citations` 查看引用网络
4. 如果本地库内容不足以完成综述，告知用户并建议使用 `ztp-research` 补充文献

```
LOCAL-FIRST 决策树：
  用户请求综述 → 搜索本地库
    ├─ 找到足够论文 → 继续
    └─ 论文不足
        ├─ 用户说"帮我补充" → 引导到 ztp-research
        └─ 用户说"就用现有的" → 继续，在综述中标注覆盖范围
```

## Tool Profile 要求

```
ZOTPILOT_TOOL_PROFILE=extended
```

Review 需要 `search_papers`、`search_topic`（core）+ `get_passage_context`、`get_citations`、`get_annotations`（extended）。

## 输出格式

综述输出应包含：

1. **主题概览**：研究领域、覆盖年份范围、论文数量
2. **主要发现**：按子主题组织，每个发现引用具体论文+段落
3. **研究差距**：本地库中缺少的方向（基于引用分析，如可用）
4. **参考文献**：所有引用的论文列表（item_key + 标准引用格式）

可选写回 Zotero：
- 用户确认后，通过 `create_note` 将综述写入一个 standalone note
- 使用 `[ZotPilot Review]` 前缀标识

## 与 ztp-research 的边界

| 行为 | ztp-review | ztp-research |
|---|---|---|
| 搜索范围 | 本地库优先 | 外部学术数据库 |
| 写入 Zotero | 可选（写 note） | 必须（ingest + tags + collections + notes） |
| Guardrail | 无 | ResearchSession + 3 gates |
| 典型用例 | "我库里关于 X 的研究怎么说" | "帮我查最新的 X 研究" |

## 测试要求

对应 Test Spec Gate 4：

| 测试项 | 验证内容 |
|---|---|
| Local-library-first | 不调用 `search_academic_databases` |
| 完整流程 | 从话题到综述输出 |
| 库内容不足时的行为 | 正确提示用户，不自行补充 |
