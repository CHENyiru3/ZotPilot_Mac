# Post-Ingest Guide — Step 4 of Agent Research Discovery

## PDF Status Check (mandatory before proceeding)

After `ingest_papers` / `save_urls` completes, check PDF status for every ingested item:

- Call `get_paper_details(item_key)` **in parallel** for all items that had `pdf: "none"` or `warning` in the ingest result.
- If `pdf_available: true` for all → proceed to the user prompt below.
- If any still `pdf_available: false` → inform user which titles are still missing PDF (likely subscription-gated), then proceed to the user prompt for the rest.

**User prompt (always required — do NOT skip):**

After confirming PDF status, ask the user:

> "PDF 已全部就位（或说明哪几篇缺 PDF）。是否需要对这批文章执行以下操作？（可多选）
> 1. **构建索引** — 向量化全文，支持后续语义搜索
> 2. **生成笔记** — 为核心文章提炼方法和结论
> 3. **归类到 Collection** — 按主题整理
> 4. **细化 tag** — 打更精准的标签"

Wait for user's explicit selection before executing any of the above.

---

## Execution (after user confirms)

For each successfully saved item with an `item_key`:

1. `index_library(item_key=...)` — call for ALL successfully ingested item_keys **in parallel** (up to 5 concurrent calls). Do NOT call them one by one sequentially. Each call is independent and indexes a single paper.
2. `get_paper_details(item_key)` — read abstract, methods, key findings
3. Based on the content and ZOTPILOT.md context, make judgments:
   - Which collection(s) does this paper belong to? (check existing collections via `list_collections`)
   - If no existing collection clearly matches: tell the user "这篇论文不属于现有任何分类（当前有: X, Y, Z）。建议：[新建分类 'Topic A'] 或 [将现有分类 'Y' 重命名/合并为 'Y+Topic A']。" — wait for user confirmation before executing.
   - If the paper is in INBOX, move it to the appropriate collection with `add_to_collection` and optionally `remove_from_collection` for INBOX.
   - What tags best describe it? (use existing tag vocabulary from `list_tags` where possible)
   - Is there anything worth noting — a key method, finding, or connection to the user's work?
4. `add_to_collection(item_key, collection_key)` + `add_item_tags(item_key, tags)` — classify
5. **生成精简笔记（每篇必做）** — 按 `references/note-analysis-prompt.md` Workflow A 执行：
   - 去重检查 → 元数据召回 → 向量召回（post-retrieval doc_id 验证）→ 填写精简模板 → `create_note` → `add_item_tags(["note-done"])`
   - 详细规则见 `note-analysis-prompt.md`；模板见 `note-template-brief.md`

If `item_key` missing from result: `advanced_search(title=...)` to locate the item first.

## Agent research ingest (single paper, deep read)

Prerequisites: Chrome open, ZotPilot Connector installed, `ZOTERO_API_KEY` configured

1. `save_from_url(url)` → get `item_key` from result
2. `index_library(item_key=...)` → incremental index
3. `get_paper_details(item_key)` → read abstract, methods, conclusions
4. Judge: relevant collection, appropriate tags
5. `add_to_collection` + `add_item_tags` → classify
6. **生成精简笔记** — 按 `note-analysis-prompt.md` Workflow A 执行
7. **用户可随时要求深读** — 说"帮我深读这篇"即触发 Workflow B（完整笔记），见 `note-analysis-prompt.md`

If `item_key` missing: use `advanced_search(title=result["title"])` to locate first.

---

## 质检清单（每批 post-ingest 完成后）

- [ ] 所有成功入库的论文均已生成精简笔记（`note-done` tag 标记）
- [ ] 笔记标题均以 `[ZotPilot]` 开头，无残留 `{{}}` 占位符
- [ ] TL;DR 含具体数值或明确判断
- [ ] Collection 归类已完成（无论文停留在 INBOX 未分类）
- [ ] 缺 PDF 的论文已告知用户
