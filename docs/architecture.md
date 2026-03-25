# ZotPilot 架构文档

> 最后更新：2026-03-26

---

## 项目定位

ZotPilot 是一个基于 **FastMCP** 的本地 Zotero 文献库 AI 助手，核心目标是：**让 AI agent 通过语义搜索和工具调用直接操作 Zotero 文献库**。

提供 32 个 MCP 工具，涵盖语义搜索、文献摄取、标注管理、集合操作等全流程，同时支持与 Chrome 扩展（zotpilot-connector）协作，实现从网页直接保存论文到 Zotero。

---

## 系统架构

```
AI Agent / Claude
      │
      │ MCP 协议（stdio）
      ▼
┌─────────────────────┐
│   FastMCP Server    │  zotpilot (server.py)
│   32 MCP Tools      │  工具注册 via import side-effects
└──────────┬──────────┘
           │
     ┌─────┼──────────────┐
     ▼     ▼              ▼
┌─────────┐ ┌──────────┐ ┌──────────────┐
│ Zotero  │ │ChromaDB  │ │ Bridge HTTP  │
│ SQLite  │ │ 向量索引 │ │ Server :2619 │
│ (本地)  │ │          │ │ (connector)  │
└─────────┘ └──────────┘ └──────┬───────┘
                                 │ 轮询 /pending
                                 ▼
                         ┌──────────────┐
                         │ ZotPilot     │
                         │ Connector    │
                         │(Chrome 扩展) │
                         └──────┬───────┘
                                │ Zotero API
                                ▼
                         ┌──────────────┐
                         │Zotero Desktop│
                         │:23119        │
                         └──────────────┘
```

---

## 核心组件

### 1. Entry Points
- **`cli.py`** — argparse CLI，子命令：`setup`, `index`, `status`, `doctor`, `config`, `register`；无子命令时启动 MCP server
- **`server.py`** — 薄包装层：`from . import tools` 触发所有工具注册，调用 `mcp.run()`

### 2. MCP State & 懒加载单例（`state.py`）
所有共享对象一次性初始化，受 `threading.Lock` 保护：

| 单例 | 职责 |
|------|------|
| `VectorStore` | ChromaDB 向量数据库封装 |
| `Retriever` | RAG 检索器 |
| `Reranker` | RRF + 权重重排序 |
| `ZoteroClient` | 本地 SQLite 只读访问 |
| `ZoteroWriter` | pyzotero Web API 写操作 |
| `ZoteroApiReader` | Web API 只读（引用数等） |
| `IdentifierResolver` | DOI/arXiv/URL 解析 |

`switch_library` 调用 `_reset_singletons()` 全部重置。后台线程监控父进程 PID，父进程退出时调用 `os._exit(0)` 防止孤儿进程。

### 3. Tool Modules（`tools/`）

| 模块 | 工具 |
|------|------|
| `search.py` | `search_papers`, `search_topic`, `search_boolean`, `search_tables`, `search_figures` |
| `context.py` | `get_passage_context`, `get_paper_details` |
| `library.py` | `get_library_overview`, `advanced_search`, `get_notes`, `list_tags`, `list_collections` 等 |
| `indexing.py` | `index_library`, `get_index_stats` |
| `citations.py` | `find_references`, `find_citing_papers`, `get_citation_count` |
| `write_ops.py` | `create_note`, `add_item_tags`, `set_item_tags`, `create_collection`, `add_to_collection` 等 |
| `admin.py` | `switch_library`, `get_reranking_config`, `get_vision_costs` |
| `ingestion.py` | `search_academic_databases`, `add_paper_by_identifier`, `ingest_papers` |

### 4. RAG Pipeline

```
PDF 文件
  └─ pdf/extractor.py          PyMuPDF 文本提取，OCR 兜底
  └─ feature_extraction/       Vision API 提取图表，PaddleOCR 可选
  └─ pdf/chunker.py            文本 → chunk，含 section 分类
  └─ pdf/section_classifier.py 标注 chunk：Abstract/Methods/Results 等
  └─ embeddings/               base.py 接口；gemini.py / dashscope.py / local.py 实现
  └─ vector_store.py           ChromaDB 封装，存储 chunk + metadata

查询路径：
  retriever.py → vector_store.py → reranker.py（RRF + section/journal 权重）
```

### 5. No-RAG 模式
`embedding_provider = "none"` 禁用向量索引。`_get_store_optional()` 返回 `None`，工具退化为 SQLite 元数据搜索。`advanced_search`、notes、tags、collections 无需索引即可使用。

---

## 目录结构

```
ZotPilot/
├── src/zotpilot/
│   ├── cli.py               ← CLI 入口
│   ├── server.py            ← MCP server 入口
│   ├── state.py             ← 单例 + 懒加载
│   ├── tools/               ← 8 个工具模块
│   ├── pdf/                 ← PDF 提取 + chunking
│   ├── embeddings/          ← 嵌入提供方抽象
│   ├── feature_extraction/  ← 图表 / OCR
│   ├── vector_store.py      ← ChromaDB 封装
│   ├── retriever.py         ← 检索器
│   ├── reranker.py          ← 重排序
│   └── bridge.py            ← HTTP Bridge Server（供 connector 使用）
├── tests/
├── docs/                    ← 内部文档（本目录）
├── CLAUDE.md                ← AI 助手指引
├── CHANGELOG.md
└── pyproject.toml
```

---

## 关键设计模式

| 模式 | 说明 |
|------|------|
| 单例 + 双重检查锁 | 所有昂贵对象一次初始化，`switch_library` 时全部重置 |
| No-RAG 降级 | `embedding_provider="none"` 让元数据工具在无向量索引时正常工作 |
| 嵌入提供方抽象 | `embeddings/base.py` 定义接口，`create_embedder(config)` 返回具体实现 |
| import side-effects 注册 | `server.py` 的 `from . import tools` 触发所有 `@mcp.tool` 装饰器 |
| 后向兼容 re-export | `filters.py`, `result_utils.py` 从 `state.py` re-export，保持向后兼容 |

---

## 配置

- 配置文件：`~/.config/zotpilot/config.json`（Unix）/ `%APPDATA%\zotpilot\config.json`（Windows）
- ChromaDB 数据：`~/.local/share/zotpilot/chroma/`
- API key 优先从环境变量读取，`Config.save()` 不持久化 key 到磁盘

| 环境变量 | 用途 |
|---------|------|
| `GEMINI_API_KEY` | 嵌入（gemini provider） |
| `DASHSCOPE_API_KEY` | 嵌入（dashscope provider） |
| `ANTHROPIC_API_KEY` | 图表视觉提取 |
| `ZOTERO_API_KEY` | 写操作 |
| `ZOTERO_USER_ID` | Zotero 用户 ID（数字） |
| `S2_API_KEY` | Semantic Scholar（可选，提升限速） |

---

## 已知局限与风险

| 风险 | 说明 | 缓解方案 |
|------|------|---------|
| 索引延迟 | 新加入的文献需手动 `zotpilot index` | 未来可考虑 watch 模式 |
| ChromaDB 单进程 | 多 MCP 实例同时写入可能冲突 | 单 server 进程使用，`os._exit` 防孤儿 |
| 嵌入 API 依赖 | Gemini/DashScope 不可用时无法索引 | No-RAG 模式降级 |
| `item_key` 返回率 | 标准 translator 路径 `itemProgress.key` 通常为空；Connector 侧已通过保存前快照 + 本地 API diff 实现回填（2026-03-26 修复），单项保存已可靠返回 key；多项并发写入时仍可能为 null | 多项保存场景保守返回 null，不误绑错误条目 |
| FastMCP list 参数 | Claude Code MCP 客户端有时将 `list[str]` 参数序列化为 JSON string 传入 | 所有接收 list 的工具调用 `_coerce_list()` 统一解析 |
