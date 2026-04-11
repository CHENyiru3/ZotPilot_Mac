# ztp-setup 技术实现文档

> 隶属于 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md) Phase 1

## 定位

`ztp-setup` 负责从零开始的安装引导：环境检测 → 选择嵌入提供商 → 写入配置 → 注册 MCP → 重启提示 → 首次索引验证。

**纯 Markdown skill，无服务端 guardrail。**

## Skill 文件格式

```markdown
---
name: ztp-setup
description: ZotPilot installation, configuration, and first-index workflow
triggers:
  - "安装 ZotPilot"
  - "配置 ZotPilot"
  - "setup ZotPilot"
  - "register MCP"
---
```

## 阶段模型

```
detect_environment → choose_provider → write_config
    → register_mcp → [restart-required] → initial_index_ready
```

### 各阶段详解

| 阶段 | 执行方式 | 说明 |
|---|---|---|
| `detect_environment` | CLI 检测 | 检查 Zotero 是否安装、数据库位置、Python 版本、uv/pip 可用性 |
| `choose_provider` | LLM 引导 | 推荐嵌入提供商（gemini/dashscope/local/none），根据用户环境和偏好 |
| `write_config` | CLI 执行 | `zotpilot setup --non-interactive --provider <choice>` |
| `register_mcp` | CLI 执行 | `zotpilot register [--gemini-key KEY]`，写入 agent 配置 |
| `restart-required` | 用户操作 | 提示用户重启 agent（MCP 注册后生效） |
| `initial_index_ready` | MCP 工具 | 重启后调用 `get_index_stats` 检查就绪状态，必要时触发 `index_library` |

## 关键设计边界

### Pre-MCP vs Post-MCP

```
┌─────────────── Pre-MCP Bootstrap ───────────────┐
│  detect_environment                              │
│  choose_provider                                 │
│  write_config        CLI 主导，无 MCP 工具可用   │
│  register_mcp                                    │
├─────────────── restart-required ─────────────────┤
│  initial_index_ready  MCP 工具可用，Skill 可调用  │
└──────────────────────────────────────────────────┘
```

**设计原则**：
- `restart-required` 之前的阶段**不假设 MCP 工具可用**
- Skill prompt 在 pre-MCP 阶段引导用户执行 CLI 命令
- Post-MCP 阶段可通过 `get_index_stats`、`index_library` 等 MCP 工具完成

### CLI 权威不变

Skill 编排和引导用户，**不替代 CLI**：

| 操作 | 执行者 | 说明 |
|---|---|---|
| 环境检测 | CLI `zotpilot doctor` | Skill 解读结果并给出建议 |
| 配置写入 | CLI `zotpilot setup` | Skill 提供参数建议 |
| MCP 注册 | CLI `zotpilot register` | Skill 生成完整命令 |
| API Key 输入 | 用户自行设置环境变量 | Skill 只解释需要哪个 key |
| 首次索引 | MCP `index_library` | Skill 触发并监控进度 |

### 三种安装模式

Skill prompt 需识别并适配：

| 模式 | 检测方式 | 更新命令 |
|---|---|---|
| Editable (`pip install -e .`) | `zotpilot status` 输出含 editable 标识 | `git pull && pip install -e .` |
| uv tool | `which zotpilot` 在 uv tool 路径下 | `uv tool upgrade zotpilot` |
| pip install | 其他情况 | `pip install -U zotpilot` |

**统一更新入口**：`zotpilot update` CLI 子命令会自动检测安装模式并执行对应更新（CLI + Skill 文件）。支持 `--cli-only` / `--skill-only` 标志。上表中的手动命令仅在 `zotpilot update` 不可用时作为 fallback。

### detect_environment 阶段分支

```
detect_environment
  ├─ ZotPilot 未安装
  │   └─ 进入全新安装流程（choose_provider → write_config → register_mcp → ...）
  │   注意：全新安装时 zotpilot doctor 不可用，需先完成安装
  └─ ZotPilot 已安装
      ├─ 检测安装模式（editable / uv tool / pip）
      ├─ 询问用户：升级到新版本 / 重新配置 / 仅检查状态
      └─ 升级子流程：
          - 运行 `zotpilot update`（自动检测安装模式并更新 CLI + Skill 文件）
          - 提示重启 agent
          - 重启后调用 get_index_stats 验证新版本生效
```

### Agent 重启方式

更新 ZotPilot 后需重启 agent 使新版 MCP 工具生效：

| Agent / 工具 | 重启方式 |
|---|---|
| Claude Code | 重启终端，或在 Claude Code 内执行 `/mcp` 重新加载 |
| Cursor | 重启整个编辑器（Cmd+Q 后重新打开） |
| Codex CLI | 终止当前进程，重新运行 `codex` |
| OpenCode | 重启 OpenCode 进程 |
| Windsurf | 重启 Windsurf 编辑器 |
| Gemini CLI | 终止当前进程，重新运行 `gemini` |

## Tool Profile 要求

```
ZOTPILOT_TOOL_PROFILE=extended
```

Setup 阶段的 `initial_index_ready` 阶段需要调用 `index_library`（extended profile），因此 profile 应设为 extended。`get_index_stats` v0.5.0 将提升到 core，`index_library` v0.5.0 将提升到 extended，extended profile 同时包含两者。

## 嵌入提供商选择决策树

```
choose_provider 阶段，Skill 引导用户按以下决策树选择：

有 Google Gemini API Key？
  ├─ 是 → 推荐 gemini（精度最高，免费额度充足）
  └─ 否
      ├─ 有 DashScope API Key（阿里云）？
      │   ├─ 是 → 推荐 dashscope（中文文献效果好）
      │   └─ 否
      │       ├─ 机器有 GPU 或愿意接受较慢速度？
      │       │   ├─ 是 → local（all-MiniLM-L6-v2，完全离线）
      │       │   └─ 否 → none（仅元数据搜索，无语义搜索）
      └─ （以上均无）→ none
```

| 提供商 | API Key 环境变量 | 特点 |
|---|---|---|
| `gemini` | `GEMINI_API_KEY` | 精度最高，推荐首选 |
| `dashscope` | `DASHSCOPE_API_KEY` | 中文文献效果好 |
| `local` | 无需 | 完全离线，需安装 sentence-transformers |
| `none` | 无需 | 无向量索引，仅元数据搜索（advanced_search 可用） |

## 配置兼容性

v0.4.x 的配置文件（`~/.config/zotpilot/config.json`）在 v0.5.0 中**完全兼容**：

- 所有现有配置键值继续有效
- v0.5.0 新增配置项（如 session 存储路径）使用内置默认值，无需手动添加
- ChromaDB 索引格式兼容，升级后无需重建索引
- 已入库的论文、标签、集合、笔记完全保留

## Windows 注意事项

| 项目 | Windows 特殊说明 |
|---|---|
| 配置文件路径 | `%APPDATA%\zotpilot\config.json`（而非 `~/.config/zotpilot/`） |
| ChromaDB 数据 | `%LOCALAPPDATA%\zotpilot\chroma\` |
| Session 文件 | `%LOCALAPPDATA%\zotpilot\sessions\` |
| Python 路径 | 优先使用 `uv` 管理，避免系统 Python 路径冲突 |
| Zotero 数据库 | 通常位于 `%APPDATA%\Zotero\Zotero\zotero.sqlite` |
| OCR（Tesseract） | 需手动安装并将 `tesseract.exe` 加入 PATH |

## 回滚说明

若升级到 v0.5.0 出现问题：

```bash
# 回退到上一版本（按安装模式选择对应命令）
pip install zotpilot==0.4.x          # pip 模式
uv tool install zotpilot==0.4.x      # uv tool 模式
git checkout v0.4.x && pip install -e .  # editable 模式
```

回滚后：
- 配置文件无需修改（向后兼容）
- 索引无需重建
- v0.5.0 新增的 session 文件（`sessions/` 目录）无用但无害，可手动删除

## Skill 文件分发

`ztp-setup.md` 等 skill 文件随 ZotPilot 包分发：

| 安装方式 | Skill 文件位置（v0.5.0 目标） |
|---|---|
| `pip install zotpilot` | `<site-packages>/zotpilot/skills/ztp-setup.md` |
| `uv tool install zotpilot` | `~/.local/share/uv/tools/zotpilot/lib/.../zotpilot/skills/` |
| `git clone` + `pip install -e .` | `<repo>/src/zotpilot/skills/ztp-setup.md` |

v0.5.0 目标：`zotpilot register` 将自动把 skill 文件部署到各平台 skill 目录（如 Claude Code 的 `~/.claude/skills/zotpilot/`）。不再需要手动 git clone 仓库到 skills 目录。详见 [分发与生命周期管理](zotpilot-0.5.0-distribution.md)。

## 错误处理

| 错误场景 | Skill 行为 |
|---|---|
| Zotero 未安装 | 提示安装 Zotero，给出下载链接 |
| API Key 缺失 | 解释哪个 key 对应哪个 provider，引导设置环境变量 |
| register 失败 | 展示错误输出，建议手动编辑 agent 配置 |
| 重启后 MCP 不可用 | 引导用户检查 agent 配置、重启 agent |
| 索引失败 | 检查 `doctor --full` 输出，引导解决 |

## 与现有文档的关系

| 现有文档 | 变化 |
|---|---|
| `references/setup-guide.md` | 内容吸收进 skill，原文件保留作为低层参考 |
| `README.md` 安装段落 | 精简为指向 `ztp-setup` 的引导 |
| `SKILL.md` setup 段落 | 替换为路由到 `ztp-setup` |

## 测试要求

对应 Test Spec Gate 3：

| 测试项 | 验证内容 |
|---|---|
| Clean-machine setup | 从无配置到 index-ready 的完整路径 |
| restart-required | 重启边界正确持久化 |
| 三种安装模式 | 各有一个验证路径 |
| MCP 不可用时的行为 | pre-MCP 阶段不调用 MCP 工具 |
