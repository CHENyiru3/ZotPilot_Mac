# ZotPilot v0.5.0 分发与生命周期管理

> 隶属于 [zotpilot-0.5.0-newarc.md](zotpilot-0.5.0-newarc.md)

## 一、当前分发模型（v0.4.x）的问题

### 双轨道分发

```
用户安装 ZotPilot 实际上需要两步：
1. pip install zotpilot          → CLI + MCP server（Python 包）
2. git clone → skills_dir/zotpilot  → SKILL.md + references/（git 仓库）

更新也是两步：
1. pip install -U zotpilot       → 更新 CLI + MCP server
2. zotpilot update → git pull    → 更新 skill 文件
```

### 问题清单

| # | 问题 | 影响 |
|---|---|---|
| 1 | CLI 和 Skill 版本可能脱节 | CLI v0.5.0 + Skill v0.4.x → 工具名不匹配、功能缺失 |
| 2 | pip/uv 用户没有 git clone | Step 4（skill update）找不到 git repo，跳过 |
| 3 | git pull 有 6+ 种失败模式 | dirty tree、symlink、broken symlink、identity check、git 不在 PATH... |
| 4 | 无版本防护 | 旧 skill 覆盖新 skill、CLI 和 skill 版本不一致无检测 |
| 5 | `scripts/run.py` 同时负责安装和启动 | 职责混乱，首次安装和日常使用的入口相同 |

---

## 二、v0.5.0 分发模型

### 核心变更：Skill 文件打包进 pip 包

```
zotpilot/                    # pip 包
├── src/zotpilot/
│   ├── skills/              ← v0.5.0 目标：新增目录，skill 文件随包分发
│   │   ├── SKILL.md         # 根 skill（兼容路由 shell）
│   │   ├── ztp-research.md
│   │   ├── ztp-setup.md
│   │   ├── ztp-review.md
│   │   └── ztp-profile.md
│   ├── references/          # 现有：参考文档
│   ├── tools/               # 现有：MCP 工具模块
│   └── ...
└── pyproject.toml           # v0.5.0 目标：package-data 将包含 skills/
```

### 安装流程（v0.5.0）

```
pip install zotpilot          # 或 uv tool install zotpilot
    └─ Python 包安装完成（CLI + MCP server + skill 文件均在 site-packages 中）

zotpilot register             # 注册 MCP server + 部署 skill 文件
    ├─ 注册 MCP server 到各 agent 配置（现有逻辑）
    └─ 复制 skill 文件到各平台 skills_dir（新增逻辑）
        ├─ ~/.claude/skills/zotpilot/SKILL.md
        ├─ ~/.claude/skills/zotpilot/ztp-research.md
        ├─ ~/.claude/skills/zotpilot/ztp-setup.md
        ├─ ~/.claude/skills/zotpilot/ztp-review.md
        ├─ ~/.claude/skills/zotpilot/ztp-profile.md
        └─ ~/.claude/skills/zotpilot/.zotpilot-version.json  ← 版本标记
```

### 更新流程（v0.5.0）

```
zotpilot update
    ├─ Step 1: 版本检查（PyPI 最新 vs 当前安装）
    ├─ Step 2: CLI 更新（pip/uv upgrade — 逻辑不变）
    ├─ Step 3: Skill 部署（新逻辑）
    │   ├─ 从 site-packages/zotpilot/skills/ 读取最新 skill 文件
    │   ├─ 遍历各平台 skills_dir（复用 _platforms.PLATFORMS）
    │   ├─ 版本比对：读取目标目录的 .zotpilot-version.json
    │   │   ├─ 目标版本 < 包版本 → 覆盖部署
    │   │   ├─ 目标版本 = 包版本 → 跳过（已是最新）
    │   │   └─ 目标版本 > 包版本 → 警告（目标比包新，可能来自 dev 安装）
    │   └─ 写入新的 .zotpilot-version.json
    ├─ Step 4: git pull fallback（仅 editable install 时）
    │   └─ 检测 editable install → 提示用户 git pull
    └─ Step 5: Post-update summary
```

### 三种安装模式对比

| 模式 | CLI 更新 | Skill 更新 | 说明 |
|---|---|---|---|
| `pip install` | `pip install -U zotpilot` | `zotpilot update` 自动从 site-packages 部署 | 最常见，全自动 |
| `uv tool install` | `uv tool upgrade zotpilot` | `zotpilot update` 自动从 uv tool 路径部署 | 推荐方式 |
| `pip install -e .` | `git pull && pip install -e .` | `zotpilot update` 检测 editable → 提示 git pull | 开发模式 |

**关键改进**：pip/uv 用户不再需要 git clone 仓库。`pip install zotpilot && zotpilot register` 即完成全部安装。

---

## 三、`cmd_register` 改造

### 现有逻辑

```python
def cmd_register(args):
    from ._platforms import register
    results = register(platforms=args.platforms, ...)
    # 仅注册 MCP server 配置
```

### v0.5.0 改造

```python
def cmd_register(args):
    from ._platforms import register, deploy_skills
    # Step 1: 注册 MCP server（现有逻辑不变）
    results = register(platforms=args.platforms, ...)
    # Step 2: 部署 skill 文件（新增）
    deploy_results = deploy_skills(platforms=args.platforms)
```

### `deploy_skills` 逻辑

```python
def deploy_skills(platforms: list[str] | None = None) -> dict[str, bool]:
    """从包内 skills/ 目录复制 skill 文件到各平台 skills_dir。"""
    # 1. 定位包内 skills 目录
    skills_source = Path(__file__).parent / "skills"
    if not skills_source.exists():
        # editable install 时可能在仓库根目录
        skills_source = Path(__file__).parent.parent.parent / "skills"
    
    # 2. 遍历目标平台
    for plat_name, plat_info in PLATFORMS.items():
        skills_dir = plat_info.get("skills_dir")
        if not skills_dir:
            continue  # 该平台无 skills_dir，跳过
        target = Path(skills_dir).expanduser() / "zotpilot"
        
        # 3. 版本检查
        if _should_skip_deploy(target, current_version):
            continue
        
        # 4. 复制文件
        target.mkdir(parents=True, exist_ok=True)
        for skill_file in skills_source.glob("*.md"):
            shutil.copy2(skill_file, target / skill_file.name)
        
        # 5. 写入版本标记
        _write_version_marker(target, current_version)
    
    # 6. 同时复制 references/ 目录（如果存在）
    refs_source = Path(__file__).parent / "references"
    if refs_source.exists():
        for plat_name, plat_info in PLATFORMS.items():
            ...  # 同理复制到 skills_dir/zotpilot/references/
```

---

## 四、`cmd_update` 改造

### Step 3 新逻辑（替换现有 git pull）

```python
# Step 3: Skill 部署（新逻辑）
if not args.cli_only:
    from ._platforms import deploy_skills
    
    # 对于非 editable 安装：从 site-packages 部署
    installer, _ = _detect_cli_installer()
    if installer != "editable":
        deploy_results = deploy_skills()
        for plat, success in deploy_results.items():
            if success:
                print(f"  Skills updated for {plat}")
            else:
                warnings.append(f"Skill deploy failed for {plat}")
    else:
        # Editable 安装：提示 git pull（现有逻辑简化版）
        print("Dev install detected — skill files read from source repo")
        print("Run 'git pull' in the repo to update skills")
        warnings.append("editable install: run git pull manually")
```

### Step 4 保留（仅 editable 兼容）

对 editable install 保留 git pull 逻辑，但大幅简化：
- 不再遍历所有 skill 目录做 git pull
- 仅提示用户在仓库中 `git pull`
- Symlink 场景自然覆盖（editable install 的 skill 目录通常 symlink 到仓库）

---

## 五、版本标记文件

### `.zotpilot-version.json`

```json
{
    "version": "0.5.0",
    "deployed_at": "2026-04-06T12:00:00Z",
    "installer": "pip",
    "skills": [
        "SKILL.md",
        "ztp-research.md",
        "ztp-setup.md",
        "ztp-review.md",
        "ztp-profile.md"
    ]
}
```

放置位置：每个平台的 `skills_dir/zotpilot/.zotpilot-version.json`

### 版本防护规则

| 场景 | 行为 |
|---|---|
| 目标无版本文件 | 首次部署，直接写入 |
| 目标版本 < 包版本 | 正常升级，覆盖部署 |
| 目标版本 = 包版本 | 跳过（已是最新），显示"Already up to date" |
| 目标版本 > 包版本 | 警告"Target has newer version (dev install?)"，不覆盖 |
| 目标目录是 symlink | 警告"Symlink detected — update source repo manually"，不覆盖 |

---

## 六、`pyproject.toml` 变更

```toml
[tool.setuptools.package-data]
zotpilot = [
    "skills/*.md",
    "references/*.md",
    "data/**/*",
]
```

确保 `pip install zotpilot` 后 `site-packages/zotpilot/skills/` 包含所有 skill 文件。

---

## 七、发版流程（v0.5.0 起）

### 版本号规则（不变）

| 级别 | 场景 |
|---|---|
| patch (0.x.**Z**) | bug 修复、skill 文案调整、文档更新 |
| minor (0.**Y**.0) | 新 skill、新 MCP 工具、新功能 |
| major (**X**.0.0) | MCP 工具签名或配置格式的破坏性变更 |

### 发版清单（更新版）

```
- [ ] `pyproject.toml` 版本已更新
- [ ] `src/zotpilot/__init__.py` `__version__` 同步
- [ ] `CHANGELOG.md` 有对应版本条目
- [ ] `README.md` 反映新功能
- [ ] `src/zotpilot/skills/` 下的 skill 文件已更新
- [ ] skill 文件中的工具名、参数与代码一致
- [ ] `uv run pytest -q` 通过（覆盖率 ≥ 29%）
- [ ] `connector/package.json` 版本一致（如有 connector 变更）
- [ ] commit → tag → push
```

### CI/CD 流程

```
dev 分支开发完成
  → PR: dev → main
  → 合并后在 main 打 tag vX.Y.Z
  → GitHub Actions release.yml 自动：
      1. 构建 wheel（含 skills/ 目录）
      2. 发布到 PyPI
      3. 从 CHANGELOG 创建 GitHub Release
```

### 用户升级路径

```
用户看到新版本发布（PyPI / GitHub Release）
  → zotpilot update                    # 自动升级 CLI + 部署 skill
  → 重启 agent                         # MCP 工具重新加载
  → 完成                               # 新 skill 文件已在各平台 skills_dir
```

**零 git 操作**：pip/uv 用户从安装到更新全程不需要 git。

---

## 八、向后兼容

### 现有 git clone 用户

| 场景 | 行为 |
|---|---|
| 用户已有 git clone 的 skill 目录 | `zotpilot update` 检测到 symlink → 警告，不覆盖，提示 git pull |
| 用户想迁移到 pip 分发 | 删除 symlink → 下次 `zotpilot update` 自动部署 |
| 用户想保持 git clone | 不影响，editable install 路径不变 |

### 现有 `scripts/run.py` 用户

`scripts/run.py` 是首次安装脚本（自动 pip install + register）。v0.5.0 保留此脚本但更新逻辑：
- `pip install zotpilot` 后调用 `zotpilot register`（已含 skill 部署）
- 不再需要用户手动 clone 仓库到 skills 目录

### editable install 用户（开发者）

```
git clone https://github.com/xunhe730/ZotPilot.git
cd ZotPilot
pip install -e ".[dev]"
zotpilot register              # 注册 MCP + 部署 skill（从仓库目录读取）
```

editable install 时 `deploy_skills` 检测到 skill 源是仓库目录，创建 symlink 而非复制：
```
~/.claude/skills/zotpilot → /path/to/ZotPilot/src/zotpilot/skills/
```

这样开发者修改 skill 文件后立即生效，无需重新部署。

---

## 九、Skill 文件目录结构

### 包内结构（source of truth）

v0.5.0 目标结构（Phase 2 实施后）：

```
src/zotpilot/skills/         ← 新建目录
├── SKILL.md                 # 根 skill（兼容路由 shell）
├── ztp-research.md          # Research 工作流
├── ztp-setup.md             # Setup 工作流
├── ztp-review.md            # Review 工作流
└── ztp-profile.md           # Profile 工作流
```

### 部署后各平台结构

```
~/.claude/skills/zotpilot/           # Claude Code
~/.agents/skills/zotpilot/           # Codex CLI（当前标准，~/.codex/skills/ 已 deprecated）
~/.config/opencode/skills/zotpilot/  # OpenCode
~/.gemini/skills/zotpilot/           # Gemini CLI
~/.cursor/skills/zotpilot/           # Cursor
~/.codeium/windsurf/skills/zotpilot/ # Windsurf

每个目录内容相同：
├── SKILL.md
├── ztp-research.md
├── ztp-setup.md
├── ztp-review.md
├── ztp-profile.md
├── references/              # 参考文档
│   ├── setup-guide.md
│   ├── post-ingest-guide.md
│   └── ...
└── .zotpilot-version.json   # 版本标记
```

### `references/` 目录是否随包分发？

**是**。references 是 skill prompt 引用的支撑文档（如 post-ingest-guide.md），必须与 skill 文件版本匹配。随包分发消除了版本脱节风险。

---

## 十、实施清单

### 代码变更

| 文件 | 变更 | Phase |
|---|---|---|
| `pyproject.toml` | 添加 `[tool.setuptools.package-data]` 包含 skills/ 和 references/ | 1 |
| `src/zotpilot/skills/` | 新建目录，放入 5 个 skill 文件 | 1 |
| `src/zotpilot/_platforms.py` | 新增 `deploy_skills()` 函数 | 1 |
| `src/zotpilot/cli.py` `cmd_register` | 调用 `deploy_skills()` | 1 |
| `src/zotpilot/cli.py` `cmd_update` | Step 3 替换为 `deploy_skills()` + editable fallback | 1 |
| `scripts/run.py` | 更新安装逻辑（不再要求 git clone） | 1 |

### 验收条件

- [ ] `pip install zotpilot && zotpilot register` 后各平台 skills_dir 有 skill 文件
- [ ] `zotpilot update` 后 skill 文件版本与 CLI 版本一致
- [ ] editable install 时 skill 目录为 symlink
- [ ] 版本防护：旧包不覆盖新部署
- [ ] 现有 git clone 用户的 symlink 不被覆盖
- [ ] `pip install zotpilot && zotpilot register --help` 显示 skill 部署信息
