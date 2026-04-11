# ZotPilot v0.5.0 MCP 工具参考手册

> 隶属于 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md)

## 概览

v0.5.0 目标工具清单：**25 个活跃工具**。相比 v0.4.x：deprecated 别名将全部移除（原 15 个），低频工具将合并（原 4 个），新增 `research_session`（1 个）。

| 类别 | v0.5.0 活跃工具数 | 变化说明 |
|---|---|---|
| 搜索 | 6 | 无变化 |
| 上下文 | 2 | 无变化 |
| 库浏览 | 4 | `get_feeds` 将合并入 `browse_library(view="feeds")`，deprecated 4 个将移除 |
| 索引 | 2 | `index_library` + `get_index_stats`；`get_unindexed_papers` / `get_reranking_config` / `get_vision_costs` 将合并入 `get_index_stats` 参数 |
| 引用 | 1 | deprecated 3 个将移除 |
| 入库 | 4 | deprecated `save_from_url` 将移除 |
| 写操作 | 4 | deprecated 7 个将移除 |
| 管理 | 1 | `switch_library`；`get_reranking_config` / `get_vision_costs` 将合并入 `get_index_stats` |
| Session | 1 | 将新增 `research_session`（方案 C） |
| **合计** | **25** | 28 - 4 合并 + 1 新增 = 25 |

---

## 一、搜索类（`search.py`）

### `search_papers`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `search.py:39` |
| 说明 | 语义搜索本地库 chunk，按复合分数（相似度 × 章节权重 × 期刊权重）排序 |
| 参数 | `query`, `top_k=10`, `context_chunks=0`, `year_min/max`, `author`, `tag`, `collection`, `chunk_types`, `section_weights`, `journal_weights`, `required_terms`, `verbosity` |
| 返回 | 按分数排序的段落列表，含 doc_id、chunk_index、文本、元数据 |
| 前置 | 需要已索引的库（`index_library` 执行过） |
| 被调用的工作流 | `ztp-review`（extract_passages）、`ztp-research`（验证阶段可选） |

### `search_topic`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `search.py:119` |
| 说明 | 论文级主题发现。每篇论文返回一条记录，按平均复合分数排序。用于"我库里有什么关于 X 的" |
| 参数 | `query`, `num_papers=10`, `year_min/max`, `author`, `tag`, `collection`, `chunk_types`, `section_weights`, `journal_weights`, `verbosity` |
| 返回 | 论文列表（去重，每篇一条），含标题、作者、年份、匹配摘要 |
| 前置 | 需要已索引的库 |
| 被调用的工作流 | `ztp-review`（local_library_scope、cluster_topic）、`ztp-profile`（infer_themes） |

### `search_boolean`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `search.py:262` |
| 说明 | 基于 Zotero 词索引的全文关键词搜索（非语义）。不做词干化或短语匹配。最适合作者名、缩写、精确术语 |
| 参数 | `query`, `operator="AND"`, `year_min/max`, `verbosity` |
| 返回 | 匹配论文列表 |
| 前置 | 需要已索引的库 |
| 被调用的工作流 | `ztp-research`（score_candidates 阶段查重时可选） |

### `search_tables`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `search.py:321` |
| 说明 | 语义搜索表格内容（表头、单元格、标题） |
| 参数 | `query`, `top_k=10`, `year_min/max`, `author`, `tag`, `collection`, `journal_weights`, `verbosity` |
| 返回 | 表格 chunk 列表 |
| 前置 | 需要已索引的库 + 表格已提取 |
| 被调用的工作流 | 无固定工作流（按需使用） |

### `search_figures`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `search.py:410` |
| 说明 | 语义搜索图表标题。返回图片路径 |
| 参数 | `query`, `top_k=10`, `year_min/max`, `author`, `tag`, `collection`, `verbosity` |
| 返回 | 图表 chunk 列表，含图片路径 |
| 前置 | 需要已索引的库 + 图表已提取 |
| 被调用的工作流 | 无固定工作流（按需使用） |

### `advanced_search`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `search.py:466` |
| 说明 | 多条件元数据搜索。**无需索引**即可使用（直接查 SQLite） |
| 参数 | `conditions`（`[{field, op, value}]`）, `match="all"`, `sort_by`, `sort_dir`, `limit` |
| 字段 | title, author, year, tag, collection, publication, doi |
| 操作符 | contains, is, isNot, beginsWith, gt, lt |
| 返回 | 匹配论文列表 |
| 被调用的工作流 | `ztp-research`（score_candidates 查重）、`ztp-review`（local_library_scope）、`ztp-profile`（scan_library） |

---

## 二、上下文类（`context.py` + `library.py`）

### `get_passage_context`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `context.py:12` |
| 说明 | 扩展搜索结果段落的上下文。传入 doc_id + chunk_index，返回前后窗口 |
| 参数 | `doc_id`, `chunk_index`, `window=2`, `include_merged=True`, `table_page`, `table_index` |
| 返回 | 扩展后的段落文本 + 前后 chunk |
| 前置 | 需要已索引的库 |
| 被调用的工作流 | `ztp-review`（extract_passages） |

### `get_paper_details`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `library.py:114` |
| 说明 | 获取论文完整元数据：摘要、标签、集合、PDF 路径、索引状态 |
| 参数 | `doc_id`（Zotero item key） |
| 返回 | 完整论文元数据 dict |
| 被调用的工作流 | `ztp-research`（final_report）、`ztp-review`（synthesis）、所有 skill 按需使用 |

---

## 三、库浏览类（`library.py`）

### `browse_library`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `library.py:31` |
| 说明 | 统一的库浏览入口。通过 `view` 参数选择视图（集合/标签/概览/集合内论文/feeds） |
| 参数 | `view`（collections/tags/overview/papers/feeds）, `collection_key`, `library_id`（feeds 视图时指定 feed 库），`limit`, `offset`, `verbosity` |
| 返回 | 视图对应的数据 |
| 被调用的工作流 | `ztp-profile`（scan_library）、`ztp-research`（classify 阶段查看集合结构） |
| **v0.5.0 目标** | 将合并 `get_feeds` 工具：使用 `browse_library(view="feeds")` 列出 RSS feeds，`browse_library(view="feeds", library_id=<id>)` 获取指定 feed 条目 |

### `get_notes`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `library.py:216` |
| 说明 | 获取或搜索笔记。可按父条目过滤或全文搜索 |
| 参数 | `item_key`（可选）, `limit`, `query`, `verbosity` |
| 返回 | 笔记列表 |
| 被调用的工作流 | `ztp-review`（可选引用笔记内容）、`ztp-profile`（可选分析笔记） |

### `get_annotations`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `library.py:294` |
| 说明 | 获取 PDF 高亮和批注。需要 ZOTERO_API_KEY |
| 参数 | `item_key`（可选）, `limit`, `verbosity` |
| 返回 | 标注列表 |
| 被调用的工作流 | `ztp-review`（可选引用标注）、`ztp-profile`（可选分析标注密度） |

### `profile_library`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `library.py:317` |
| 说明 | 分析 Zotero 库生成用户画像（标签频率、集合结构、年份分布、核心作者） |
| 参数 | `include_profile=False` |
| 返回 | 库分析数据 dict |
| 被调用的工作流 | `ztp-profile`（scan_library — 核心数据源） |

---

## 四、索引类（`indexing.py`）

### `index_library`

| 属性 | 值 |
|---|---|
| Profile | admin（当前）→ `extended`（v0.5.0 目标：将从 admin 提升） |
| 位置 | `indexing.py:40` |
| 说明 | 将 Zotero PDF 索引到向量库。默认增量；按 batch_size 处理，需重复调用直到 `has_more=false` |
| 参数 | `force_reindex=False`, `limit`, `item_key`, `title_pattern`, `no_vision=False`, `batch_size`, `max_pages`, `include_summary=False` |
| 返回 | 索引结果 + `has_more` 标志 |
| 被调用的工作流 | `ztp-research`（index 阶段）、`ztp-setup`（initial_index_ready） |

### `get_index_stats`

| 属性 | 值 |
|---|---|
| Profile | admin（当前）→ `core`（v0.5.0 目标：将从 admin 提升） |
| 位置 | `indexing.py:125` |
| 说明 | 获取索引统计。v0.5.0 后将同时支持未索引论文列表、重排配置和视觉费用摘要查询。通常首先调用以检查就绪状态 |
| 参数（当前） | 无分页参数 |
| 参数（v0.5.0 目标） | `limit=50`, `offset=0`（未索引论文分页），`include_config=False`（返回重排配置），`include_vision_costs=False`（返回视觉费用摘要，`last_n=10`） |
| 返回 | 索引统计（已索引/未索引数量、最后更新时间）；v0.5.0 后可选：未索引论文列表、重排配置、视觉费用 |
| 被调用的工作流 | `ztp-setup`（initial_index_ready 检查）、所有 skill 启动前可调用 |
| **v0.5.0 目标** | 将合并 `get_unindexed_papers`（分页列表）、`get_reranking_config`（重排配置）、`get_vision_costs`（费用摘要）的功能 |

---

## 五、引用类（`citations.py`）

### `get_citations`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `citations.py:41` |
| 说明 | 获取论文引用图谱数据（被引/引用列表）。通过 OpenAlex/Semantic Scholar 查询 |
| 参数 | `doc_id`, `direction`（citing/cited/both）, `limit` |
| 返回 | 引用关系列表 |
| 前置 | 论文需要有 DOI |
| 被调用的工作流 | `ztp-review`（optional_citation_expansion） |

---

## 六、入库类（`ingestion.py`）

### `search_academic_databases`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `ingestion.py:297` |
| 说明 | 搜索外部学术数据库（OpenAlex 为主）。文献发现的第一步 |
| 参数 | `query`, `limit`, `year_min/max`, `sort_by` |
| 返回 | 外部论文列表（标题、作者、年份、DOI、摘要、引用数） |
| 被调用的工作流 | `ztp-research`（external_discovery — **核心入口**） |

### `ingest_papers`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `ingestion.py:662` |
| 说明 | 异步批量入库论文到 Zotero（通过 Connector 或 API fallback） |
| 参数 | `papers`（含 URL 的论文列表）, `collection_key`（可选目标集合） |
| 返回 | `batch_id` + 初始状态 |
| 前置 | Connector 扩展运行中或 Zotero 客户端打开 |
| 被调用的工作流 | `ztp-research`（ingest 阶段 — **写操作核心，受 Gate 1 保护**） |

### `get_ingest_status`

| 属性 | 值 |
|---|---|
| Profile | `core` |
| 位置 | `ingestion.py:993` |
| 说明 | 查询异步入库批次的进度 |
| 参数 | `batch_id` |
| 返回 | BatchState 完整状态（含逐条结果） |
| 被调用的工作流 | `ztp-research`（ingest_verification — 轮询直到终态） |

### `save_urls`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `ingestion.py:1029` |
| 说明 | 批量保存 URL 到 Zotero（通过 Connector）。最多 10 条 |
| 参数 | `urls`, `collection_key`, `tags` |
| 返回 | 保存结果 |
| 被调用的工作流 | `ztp-research`（direct ingest 快速子流程） |

### `save_from_url`（v0.5.0 目标：将移除）

`save_from_url` 是 deprecated 别名，v0.5.0 将移除。请使用 `save_urls([url])` 替代。

---

## 七、写操作类（`write_ops.py`）

### `create_collection`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `write_ops.py:210` |
| 说明 | 创建新的 Zotero 集合（文件夹） |
| 参数 | `name`, `parent_key`（可选父集合） |
| 前置 | ZOTERO_API_KEY + ZOTERO_USER_ID |
| 被调用的工作流 | `ztp-research`（classify — 需要新子集合时）、`ztp-profile`（organization_recommendations） |

### `create_note`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `write_ops.py:221` |
| 说明 | 在 Zotero 条目上创建子笔记 |
| 参数 | `item_key`, `content`, `title`（可选）, `tags`（可选） |
| 前置 | ZOTERO_API_KEY + ZOTERO_USER_ID |
| 被调用的工作流 | `ztp-research`（note 阶段 — **v0.5.0 目标：受 Gate 2 保护，需幂等改造**）、`ztp-review`（可选写回综述） |
| **v0.5.0 目标** | 将新增 `idempotent` 参数：为 True 时检查是否已有 `[ZotPilot]` 前缀 note；将集成 Gate 2 |

### `manage_tags`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `write_ops.py:319` |
| 说明 | 管理一个或多个条目的标签。支持 add/set/remove 操作 |
| 参数 | `action`（add/set/remove）, `item_keys`, `tags`, `allow_new=False` |
| 前置 | ZOTERO_API_KEY + ZOTERO_USER_ID |
| 被调用的工作流 | `ztp-research`（tag 阶段 — **v0.5.0 目标：受 Gate 2 保护，需默认 add 改造**）、`ztp-profile`（标签清理） |
| **v0.5.0 目标** | Research session 上下文中将默认 `action="add"`，`set` 需 skill prompt 显式要求；将集成 Gate 2 |

### `manage_collections`

| 属性 | 值 |
|---|---|
| Profile | `extended` |
| 位置 | `write_ops.py:388` |
| 说明 | 管理条目的集合归属。支持 add/remove/create 操作 |
| 参数 | `action`（add/remove/create）, `item_keys`, `collection_key`, `auto_cleanup_inbox=True` |
| 前置 | ZOTERO_API_KEY + ZOTERO_USER_ID |
| 被调用的工作流 | `ztp-research`（classify 阶段 — 受 Gate 2 保护）、`ztp-profile`（集合重组） |

---

## 八、管理类（`admin.py`）

v0.5.0 后管理类仅保留 1 个活跃工具（`switch_library`）。`get_reranking_config` 和 `get_vision_costs` 将合并入 `get_index_stats` 参数后移除。

### `get_reranking_config`（v0.5.0 目标：将合并移除）

v0.5.0 目标：功能将合并入 `get_index_stats(include_config=True)`，原工具将移除。

### `get_vision_costs`（v0.5.0 目标：将合并移除）

v0.5.0 目标：功能将合并入 `get_index_stats(include_vision_costs=True, last_n=10)`，原工具将移除。

### `switch_library`

| 属性 | 值 |
|---|---|
| Profile | `admin` |
| 位置 | `admin.py:141` |
| 说明 | 列出可用库或切换活跃库上下文。切换后重置所有单例 |
| 参数 | `library_id`（None 列出可用库）, `library_type` |
| 返回 | 可用库列表或切换确认 |
| 被调用的工作流 | 多库用户按需使用 |
| **v0.5.0 目标** | 切换库时将检查是否有 active ResearchSession 并警告 |

---

## 九、Session 类（`workflow/research_session.py`）

### `research_session`（v0.5.0 目标：将新增）

| 属性 | 值 |
|---|---|
| Profile | `core`（v0.5.0 目标） |
| 位置 | `workflow/research_session.py`（v0.5.0 目标：将新增） |
| 说明 | 统一的 Research Session 管理入口。通过 `action` 参数区分 create/get/approve/validate 操作 |
| 参数 | `action`（create/get/approve/validate），`session_id`（可选，get/approve/validate 时使用），`query`（action=create 时提供检索意图），`checkpoint`（action=approve 时提供 checkpoint 名称：`candidate-review` 或 `post-ingest-review`） |
| 返回 | Session 状态 dict（含 session_id、status、阶段、items 数量、approved_checkpoints） |
| 被调用的工作流 | `ztp-research`（全流程） |

#### action 详解

| action | 说明 | 必填参数 |
|---|---|---|
| `create` | 创建新 session。若已有 active session 则返回现有 session，不新建 | `query` |
| `get` | 获取当前 library 的 active session 状态 | 无（或 `session_id` 指定特定 session） |
| `approve` | 标记 checkpoint 已通过用户审批，解锁对应 gate | `checkpoint`（candidate-review 或 post-ingest-review） |
| `validate` | 触发 drift 检测：校验所有 session items 的 fingerprint | `session_id`（可选） |

---

## 十、工具 × 工作流矩阵

| 工具 | research | setup | review | profile | 独立使用 |
|---|---|---|---|---|---|
| `search_papers` | ○ | | ● | | ● |
| `search_topic` | | | ● | ● | ● |
| `search_boolean` | ○ | | | | ● |
| `search_tables` | | | | | ● |
| `search_figures` | | | | | ● |
| `advanced_search` | ● | | ● | ● | ● |
| `get_passage_context` | | | ● | | ● |
| `get_paper_details` | ● | | ● | | ● |
| `browse_library` | ○ | | | ● | ● |
| `get_notes` | | | ○ | ○ | ● |
| `get_annotations` | | | ○ | ○ | ● |
| `profile_library` | | | | ● | ● |
| `index_library` | ● | ● | | | ● |
| `get_index_stats` | | ● | | | ● |
| `get_citations` | | | ○ | | ● |
| `search_academic_databases` | ● | | | | ● |
| `ingest_papers` | ● | | | | ● |
| `get_ingest_status` | ● | | | | ● |
| `save_urls` | ○ | | | | ● |
| `create_collection` | ○ | | | ○ | ● |
| `create_note` | ● | | ○ | | ● |
| `manage_tags` | ● | | | ● | ● |
| `manage_collections` | ● | | | ● | ● |
| `switch_library` | | | | | ● |
| `research_session` | ● | | | | |

图例：● = 核心依赖　○ = 可选使用　空 = 不使用

---

## 十一、v0.5.0 改造清单（决策已确定，尚未实施）

### 必须改造（v0.5.0 目标）

| 工具 | 改造内容 | 原因 |
|---|---|---|
| `ingest_papers` | 集成 Gate 1（Pre-Ingest session check） | Research guardrail |
| `create_note` | 新增 `idempotent` 参数 + Gate 2 集成 | 幂等 + guardrail |
| `manage_tags` | Research context 默认 `add` + Gate 2 集成 | 幂等 + guardrail |
| `manage_collections` | Gate 2 集成 | Research guardrail |
| `switch_library` | Active session 警告 | 防止 wrong-library writes |
| `browse_library` | 新增 `view="feeds"` 支持（合并 `get_feeds` 功能） | 低频工具合并 |
| `get_index_stats` | 新增 `limit/offset`（分页）、`include_config`、`include_vision_costs` 参数 | 合并 3 个低频工具功能 |

### Profile Tag 调整（已确定）

| 工具 | v0.4.x | v0.5.0 | 原因 |
|---|---|---|---|
| `index_library` | admin | extended | research/setup 流程依赖，不应在 admin 隐藏 |
| `get_index_stats` | admin | core | setup 就绪检查基础，所有 skill 启动前调用 |

### 低频工具合并（已确定）

| 原工具 | 合并目标 | 调用方式 |
|---|---|---|
| `get_feeds` | `browse_library` | `browse_library(view="feeds")` |
| `get_unindexed_papers` | `get_index_stats` | `get_index_stats(limit=50, offset=0)` |
| `get_reranking_config` | `get_index_stats` | `get_index_stats(include_config=True)` |
| `get_vision_costs` | `get_index_stats` | `get_index_stats(include_vision_costs=True)` |

### Deprecated 别名移除（已确定）

v0.5.0 全部移除 15 个 deprecated 别名（原计划 v0.6.0，提前清理）：

`list_collections`, `get_collection_papers`, `list_tags`, `get_library_overview`,
`find_citing_papers`, `find_references`, `get_citation_count`,
`set_item_tags`, `add_item_tags`, `remove_item_tags`,
`add_to_collection`, `remove_from_collection`,
`batch_tags`, `batch_collections`, `save_from_url`

### 新增工具（已确定）

1 个新工具 `research_session`（方案 C）——详见 §九及 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md) §六
