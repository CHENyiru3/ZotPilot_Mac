# ZotPilot v0.5.0 E2E 测试方案

> 隶属于 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md) Phase 4
> 场景清单权威定义见 [test-spec-ztp-lifecycle-architecture.md](test-spec-ztp-lifecycle-architecture.md)

## 一、测试分层

```
┌─────────────────────────────────────────────┐
│  E2E Tests（18 个场景）                      │
│  模拟 agent 完整工作流调用                   │
├─────────────────────────────────────────────┤
│  Integration Tests                          │
│  setup/update 生命周期 + 工作流能力集成      │
├─────────────────────────────────────────────┤
│  Unit Tests                                 │
│  工作流契约 + Tool Profile policy + 兼容性   │
└─────────────────────────────────────────────┘
```

| 层级 | 框架 | 运行条件 | CI 可运行 |
|---|---|---|---|
| Unit | pytest | 无外部依赖 | 是 |
| Integration | pytest + mock Zotero | mock Zotero API | 是 |
| E2E（自动化） | pytest + mock MCP client | mock Zotero + 真实 ZotPilot 服务器 | 是（mock 模式） |
| E2E（手动 QA） | 真实 Zotero + Claude Code | 真实 Zotero 实例 | 否（手动执行） |

---

## 二、测试执行环境

### 自动化测试（CI 可运行）

**mock Zotero 模式**：

```python
# tests/conftest.py
@pytest.fixture
def mock_zotero_client():
    """返回模拟 Zotero SQLite 客户端，含预置测试数据。"""
    ...

@pytest.fixture
def mock_zotero_writer():
    """返回模拟 Zotero Web API 写入客户端。记录调用，返回成功。"""
    ...

@pytest.fixture
def mock_mcp_client(mock_zotero_client, mock_zotero_writer):
    """启动 ZotPilot MCP 服务器（测试配置），返回 MCP 工具调用客户端。"""
    ...
```

**测试数据准备**：
- `tests/fixtures/sample_library.db`：包含 10 篇测试论文的 SQLite 数据库
- `tests/fixtures/sample_sessions/`：预置 session JSON 文件（各状态）
- `tests/fixtures/openalex_responses/`：mock OpenAlex API 响应

### 手动 QA 环境

- 真实 Zotero 5.x/6.x 实例（含至少 20 篇论文）
- Claude Code 最新版（已注册 ZotPilot v0.5.0 MCP server）
- `ZOTERO_API_KEY` + `ZOTERO_USER_ID` 已配置
- 至少一个嵌入提供商已配置（建议 gemini）

---

## 三、18 个场景测试规格

### E2E-01：规范化研究流程

**类型**：自动化（mock Zotero）+ 手动 QA

**前置条件**：
- 无 active session
- mock OpenAlex 返回 5 篇候选论文
- mock Zotero writer 记录所有写入调用

**步骤**：
```python
def test_e2e_01_canonical_research_flow(mock_mcp_client):
    # 1. 检测无 session
    result = mock_mcp_client.call("research_session", action="get")
    assert result["active_session"] is None

    # 2. 创建 session
    result = mock_mcp_client.call("research_session", action="create", query="attention mechanism")
    session_id = result["session_id"]

    # 3. 外部发现
    candidates = mock_mcp_client.call("search_academic_databases", query="attention mechanism", limit=10)
    assert len(candidates["papers"]) > 0

    # 4. CHECKPOINT 1：审批
    result = mock_mcp_client.call("research_session", action="approve",
                                   checkpoint="candidate-review")
    assert "candidate-review" in result["approved_checkpoints"]

    # 5. ingest
    result = mock_mcp_client.call("ingest_papers", papers=candidates["papers"][:3])
    batch_id = result["batch_id"]

    # 6. 轮询 ingest 状态
    for _ in range(10):
        status = mock_mcp_client.call("get_ingest_status", batch_id=batch_id)
        if status["status"] in ("completed", "failed", "partial_success"):
            break
    assert status["status"] in ("completed", "partial_success")

    # 7. CHECKPOINT 2：审批
    result = mock_mcp_client.call("research_session", action="approve",
                                   checkpoint="post-ingest-review")
    assert "post-ingest-review" in result["approved_checkpoints"]

    # 8. Post-ingest 步骤
    for item_key in [item["item_key"] for item in status["results"] if item["success"]]:
        mock_mcp_client.call("index_library", item_key=item_key)
        mock_mcp_client.call("manage_collections", action="add",
                              item_keys=[item_key], collection_key="test_collection")
        mock_mcp_client.call("create_note", item_key=item_key,
                              content="[ZotPilot] Test note", idempotent=True)
        mock_mcp_client.call("manage_tags", action="add",
                              item_keys=[item_key], tags=["test-tag"])

    # 9. 验证 session 完成
    final = mock_mcp_client.call("research_session", action="get", session_id=session_id)
    assert final["status"] == "completed"
```

**预期结果**：
- session JSON 文件存在，含 2 个 approved_checkpoints
- mock writer 记录到 create_note、manage_tags、manage_collections 调用
- final status = "completed"

---

### E2E-02：CHECKPOINT bypass 阻断

**类型**：自动化

```python
def test_e2e_02_gate1_blocks_unapproved_ingest(mock_mcp_client):
    # 创建 session 但不审批 CHECKPOINT 1
    mock_mcp_client.call("research_session", action="create", query="test topic")

    # 直接调用 ingest_papers
    with pytest.raises(ToolError, match="requires user approval"):
        mock_mcp_client.call("ingest_papers", papers=[{"title": "Test Paper", "url": "http://example.com"}])
```

---

### E2E-03：wrong-library 阻断

**类型**：自动化

```python
def test_e2e_03_gate1_blocks_wrong_library(mock_mcp_client):
    # 在 library_A 创建并审批 session
    mock_mcp_client.call("research_session", action="create", query="test")
    mock_mcp_client.call("research_session", action="approve", checkpoint="candidate-review")

    # 切换到 library_B
    mock_mcp_client.call("switch_library", library_id="library_B")

    # 调用 ingest_papers 应被阻断
    with pytest.raises(ToolError, match="Library changed"):
        mock_mcp_client.call("ingest_papers", papers=[...])
```

---

### E2E-04：Post-ingest drift 阻断

**类型**：自动化

```python
def test_e2e_04_gate3_drift_detection(mock_mcp_client, mock_zotero_client):
    # 建立已完成 ingest 的 session（含 fingerprint）
    session = load_fixture_session("post_ingest_session.json")

    # 模拟 Zotero 侧删除一篇论文
    mock_zotero_client.delete_item(session["items"][0]["item_key"])

    # 尝试 resume（load session 时自动触发 drift 检测）
    result = mock_mcp_client.call("research_session", action="validate",
                                   session_id=session["session_id"])
    assert result["status"] == "resume_invalidated"
    assert len(result["drift_details"]) > 0
    assert result["drift_details"][0]["reason"] == "deleted"
```

---

### E2E-05：Partial success 处理

**类型**：自动化

```python
def test_e2e_05_partial_success(mock_mcp_client):
    # mock ingest：3 篇中 1 篇失败
    papers = [paper_1, paper_2, paper_failing]
    result = mock_mcp_client.call("ingest_papers", papers=papers)
    # ... 轮询到终态
    assert status["status"] == "partial_success"
    assert len([r for r in status["results"] if r["success"]]) == 2
    assert len([r for r in status["results"] if not r["success"]]) == 1

    # post-ingest 只处理成功的 2 篇
    # 验证 failed 篇不产生 note/tag
```

---

### E2E-06：幂等性验证

**类型**：自动化

```python
def test_e2e_06_idempotent_post_ingest(mock_mcp_client, mock_zotero_writer):
    item_key = "TESTKEY1"

    # 第一次执行
    mock_mcp_client.call("create_note", item_key=item_key,
                          content="[ZotPilot] Research note", idempotent=True)
    mock_mcp_client.call("manage_tags", action="add", item_keys=[item_key], tags=["tag-a"])

    # 第二次重复执行
    mock_mcp_client.call("create_note", item_key=item_key,
                          content="[ZotPilot] Research note", idempotent=True)
    mock_mcp_client.call("manage_tags", action="add", item_keys=[item_key], tags=["tag-a"])

    # 验证 note 只创建一次
    create_note_calls = mock_zotero_writer.calls_for("create_note")
    assert len(create_note_calls) == 1  # 第二次因 idempotent=True 跳过

    # 验证 tag 没有重复（add 操作天然幂等）
    tags = mock_zotero_writer.get_item_tags(item_key)
    assert tags.count("tag-a") == 1
```

---

### E2E-07：向后兼容（无 session 直接调用）

**类型**：自动化

```python
def test_e2e_07_backward_compat_no_session(mock_mcp_client):
    # 确保无 active session
    result = mock_mcp_client.call("research_session", action="get")
    assert result["active_session"] is None

    # 直接调用 ingest_papers 应成功（无 gate 阻断）
    result = mock_mcp_client.call("ingest_papers",
                                   papers=[{"title": "Direct Ingest", "url": "http://example.com"}])
    assert "batch_id" in result
```

---

### E2E-08：Gate 2 仅拦截 `running`

**类型**：自动化

```python
def test_e2e_08_gate2_blocks_running_state(mock_mcp_client):
    # 建立 session，完成 CHECKPOINT 1，完成 ingest
    # → session.status = "running"（未经 CHECKPOINT 2 审批，自动推进写操作时）
    session = create_session_in_running_state(mock_mcp_client)

    # 在 running 状态下尝试 create_note（未经 CHECKPOINT 2 审批）
    with pytest.raises(ToolError, match="Post-ingest steps require user approval"):
        mock_mcp_client.call("create_note", item_key="TESTKEY1", content="test")
```

---

### E2E-09：Gate 2 不拦截 `awaiting_user`

**类型**：自动化

```python
def test_e2e_09_gate2_allows_awaiting_user_state(mock_mcp_client):
    # 建立 session，session.status = "awaiting_user"（等待 CHECKPOINT 1）
    mock_mcp_client.call("research_session", action="create", query="test")
    # 此时 status = awaiting_user（等待用户在 CHECKPOINT 1 处决策）

    # 手动调用 create_note 不应被 Gate 2 拦截
    result = mock_mcp_client.call("create_note", item_key="TESTKEY1",
                                   content="Manual note outside session")
    assert result["success"] is True
```

---

### E2E-10：Clean-machine setup

**类型**：手动 QA（无法完全自动化，依赖真实 MCP 注册流程）

**步骤**：
1. 清空 `~/.config/zotpilot/` 配置目录
2. 确保 Zotero 已安装，已打开
3. 运行 `ztp-setup` skill
4. 验证 `detect_environment` 阶段正确识别 Zotero 路径
5. 选择 gemini provider，输入 API Key
6. 执行 `zotpilot setup --non-interactive --provider gemini`
7. 执行 `zotpilot register`
8. 重启 agent（Claude Code）
9. 调用 `get_index_stats` 验证 MCP 可用
10. 调用 `index_library` 完成首次索引

**预期结果**：
- `~/.config/zotpilot/config.json` 存在且含 provider 配置
- `~/.claude/skills/zotpilot/` 下有 5 个 skill 文件
- `get_index_stats` 返回已索引论文数 > 0（或 0 但无报错）

---

### E2E-11：restart-required 边界

**类型**：手动 QA + 部分自动化

```python
def test_e2e_11_pre_mcp_no_tool_calls(mock_mcp_client):
    """验证 restart 前 setup 阶段不调用 MCP 工具。"""
    # 模拟 pre-MCP 阶段：工具不可用
    with mock_mcp_unavailable():
        # detect_environment、choose_provider、write_config、register_mcp
        # 这些阶段应只使用 CLI 命令，不调用 MCP 工具
        result = simulate_pre_mcp_setup_phases()
    assert result["mcp_calls"] == []  # 没有 MCP 工具调用
```

---

### E2E-12：升级路径

**类型**：手动 QA（需要真实安装环境）

**步骤（pip 模式）**：
1. 安装 `pip install zotpilot==0.4.x`
2. 执行 `pip install -U zotpilot` 升级到 v0.5.0
3. 执行 `zotpilot update`
4. 检查 `~/.claude/skills/zotpilot/.zotpilot-version.json` 版本号
5. 验证 skill 文件已更新到 v0.5.0

**步骤（uv 模式）**：
1. `uv tool install zotpilot==0.4.x`
2. `uv tool upgrade zotpilot`
3. `zotpilot update`
4. 验证 skill 文件版本

---

### E2E-13：旧式模糊请求路由

**类型**：手动 QA

**步骤**：
1. 通过根 `SKILL.md` 发出请求："帮我整理一下我的文献库的标签"
2. 验证 agent 路由到 `ztp-profile`，而非在根 skill 内重实现整个工作流
3. 发出请求："帮我收集最近的机器学习论文"
4. 验证 agent 路由到 `ztp-research`

**预期结果**：
- 路由到专项 skill，不静默重实现
- 如无法路由，应明确提示用户使用对应 skill

---

### E2E-14：Legacy 别名移除后提示

**类型**：自动化

```python
@pytest.mark.parametrize("removed_tool,replacement", [
    ("list_collections", "browse_library(view='collections')"),
    ("get_library_overview", "browse_library(view='overview')"),
    ("find_citing_papers", "get_citations(direction='citing')"),
    ("set_item_tags", "manage_tags(action='set')"),
    ("save_from_url", "save_urls([url])"),
])
def test_e2e_14_deprecated_alias_removed(mock_mcp_client, removed_tool, replacement):
    with pytest.raises((ToolNotFoundError, ToolError)):
        mock_mcp_client.call(removed_tool)
```

---

### E2E-15：Review 工作流（local-first）

**类型**：手动 QA + 部分自动化

```python
def test_e2e_15_review_local_first(mock_mcp_client):
    # 本地库有充足相关论文时，不触发外部搜索
    # 模拟本地库有 10 篇相关论文
    result = mock_mcp_client.call("search_topic", query="attention mechanism", num_papers=5)
    assert len(result["papers"]) >= 5
    # review 工作流应以本地结果为基础，不调用 search_academic_databases
```

---

### E2E-16：Profile 工作流（批量写确认）

**类型**：手动 QA

**步骤**：
1. 触发 `ztp-profile`，请求"分析我的库并清理标签"
2. `profile_library` 分析 → 展示标签建议
3. 用户确认批量操作
4. `manage_tags(action="set", ...)` 执行清理
5. 验证操作在用户确认后才执行（不自动执行）

---

### E2E-17：无 RAG 模式降级

**类型**：自动化

```python
def test_e2e_17_no_rag_degradation(mock_mcp_client):
    # 配置 embedding_provider=none
    with mock_config(embedding_provider="none"):
        result = mock_mcp_client.call("index_library")
        assert result["skipped"] is True
        assert result["reason"] == "embedding_provider=none"

        # advanced_search 仍可用
        result = mock_mcp_client.call("advanced_search",
                                       conditions=[{"field": "title", "op": "contains", "value": "test"}])
        assert "papers" in result
```

---

### E2E-18：Session resume 验证

**类型**：自动化

```python
def test_e2e_18_session_resume(mock_mcp_client, tmp_path):
    # 模拟中断：在 CHECKPOINT 1 后进程重启
    session_data = create_fixture_session(
        status="awaiting_user",
        approved_checkpoints=["candidate-review"],
        items=[{"item_key": "KEY1", "fingerprint": {"title_prefix": "Test Paper"}}]
    )
    save_session(tmp_path / "sessions" / "session.json", session_data)

    # 重新加载（模拟重启）
    result = mock_mcp_client.call("research_session", action="get")
    assert result["active_session"] is not None
    assert result["active_session"]["status"] == "awaiting_user"

    # 验证 fingerprint 无 drift → 可继续
    result = mock_mcp_client.call("research_session", action="validate",
                                   session_id=session_data["session_id"])
    assert result["status"] != "resume_invalidated"
    assert len(result.get("drift_details", [])) == 0
```

---

## 四、Tool Profile 能力矩阵测试

```python
# tests/unit/test_tool_profiles.py

PROFILE_TOOL_MATRIX = {
    "core": ["search_papers", "search_topic", "advanced_search", "get_passage_context",
             "get_paper_details", "search_academic_databases", "ingest_papers",
             "get_ingest_status", "get_index_stats", "research_session"],
    "extended": ["search_boolean", "search_tables", "search_figures",
                 "browse_library", "get_notes", "get_annotations", "profile_library",
                 "index_library", "get_citations", "save_urls",
                 "create_collection", "create_note", "manage_tags", "manage_collections"],
    "research": [
        # research = core + extended + write + admin
        "search_papers", "search_topic", "advanced_search",  # core
        "index_library", "browse_library",  # extended（已提升）
        "create_note", "manage_tags", "manage_collections",  # write
        "switch_library",  # admin
        "research_session",  # core
    ],
}

@pytest.mark.parametrize("profile,expected_tools", PROFILE_TOOL_MATRIX.items())
def test_profile_includes_expected_tools(profile, expected_tools):
    visible = get_visible_tools_for_profile(profile)
    for tool in expected_tools:
        assert tool in visible, f"Profile '{profile}' missing tool '{tool}'"

def test_research_profile_has_index_library():
    """index_library 提升到 extended 后，research profile 必须可见。"""
    visible = get_visible_tools_for_profile("research")
    assert "index_library" in visible

def test_research_profile_has_get_index_stats():
    """get_index_stats 提升到 core 后，所有 profile 必须可见。"""
    for profile in ["core", "extended", "all", "research"]:
        visible = get_visible_tools_for_profile(profile)
        assert "get_index_stats" in visible
```

---

## 五、CI 集成方案

### pytest 配置

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: 单元测试，无外部依赖",
    "integration: 集成测试，mock Zotero",
    "e2e: E2E 测试，mock MCP client",
    "manual: 需要真实 Zotero，仅手动运行",
]
```

### CI 运行命令

```bash
# CI 中运行（排除手动 QA）
uv run pytest -m "not manual" --cov=src/zotpilot --cov-report=term-missing -q

# 仅单元测试（最快）
uv run pytest -m unit -q

# E2E 自动化部分
uv run pytest -m e2e -q

# 手动 QA（本地运行）
uv run pytest -m manual -v
```

### GitHub Actions 配置（片段）

```yaml
# .github/workflows/test.yml
- name: Run automated tests
  run: |
    uv run pytest -m "not manual" \
      --cov=src/zotpilot \
      --cov-fail-under=29 \
      -q
```

---

## 六、手动 QA Checklist

在发版前，执行以下手动 QA 场景（对应 E2E-10/12/13/15/16）：

- [ ] **E2E-10**：Clean-machine setup 完整路径（detect → provider → config → register → restart → index-ready）
- [ ] **E2E-12**：`pip install -U` + `zotpilot update` 升级路径，验证 skill 文件版本
- [ ] **E2E-13**：根 SKILL.md 路由验证（模糊请求 → 专项 skill）
- [ ] **E2E-15**：Review 工作流 local-first 行为（本地有充足论文时不触发外部搜索）
- [ ] **E2E-16**：Profile 工作流批量写确认（操作在用户确认后才执行）
- [ ] **E2E-01（手动版）**：真实 Zotero 环境下的完整 research 流程，两个 checkpoint 均触发
- [ ] **迁移验证**：15 个 deprecated 别名在 v0.5.0 中均不可调用，且给出明确替代说明
- [ ] **Skill 部署验证**：`zotpilot register` 后各平台 `skills_dir/zotpilot/` 下有 5 个 skill 文件 + `.zotpilot-version.json`

---

## 七、测试文件组织

```
tests/
├── conftest.py                      # 共享 fixtures（mock_zotero_client 等）
├── fixtures/
│   ├── sample_library.db            # 测试 Zotero SQLite 数据库
│   ├── openalex_responses/          # mock OpenAlex API 响应
│   └── sessions/
│       ├── post_ingest_session.json # 用于 drift 检测测试
│       └── awaiting_user_session.json
├── unit/
│   ├── test_tool_profiles.py        # Tool Profile 能力矩阵测试
│   ├── test_research_session.py     # ResearchSession dataclass + 状态转换
│   ├── test_session_store.py        # JSON 持久化测试
│   └── test_gate_logic.py           # Gate 1/2/3 逻辑单元测试
├── integration/
│   ├── test_setup_lifecycle.py      # setup/update 生命周期
│   └── test_workflow_capability.py  # 工作流能力集成测试
└── e2e/
    ├── test_research_flow.py        # E2E-01~09（研究流程 + Gate 语义）
    ├── test_setup_flow.py           # E2E-10~12（setup/upgrade）
    ├── test_compatibility.py        # E2E-13~14（兼容 shell + 别名）
    ├── test_review_profile.py       # E2E-15~16（review/profile 工作流）
    └── test_edge_cases.py           # E2E-17~18（无 RAG + resume）
```
