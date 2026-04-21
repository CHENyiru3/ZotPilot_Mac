# ZotPilot 配置/注册/更新收口设计（v0.6）

## 1. 问题陈述

现有模型把配置与凭证拆散在多个地方：

- `config.json`
- 环境变量
- Codex / Claude / OpenCode 客户端 MCP 配置
- 旧 `deep-zotero` 配置

这导致三个问题：

1. `setup / register / config / update` 职责混乱
2. 客户端配置中嵌入 secret，泄漏面和 drift 面都过大
3. `Config.load()` 同时承担 shared config 与 runtime resolution，边界不清晰

## 2. 目标用户流程

### 新用户

1. 运行 `zotpilot setup`
2. 在 wizard 中完成：
   - Zotero 路径
   - provider
   - embedding key
   - Zotero 写操作凭证
   - `openalex_email`
   - 客户端注册
3. 重启对应客户端
4. 运行 `zotpilot doctor` / `zotpilot status` 验证

### 已有用户

- 修改配置：`zotpilot config set ...`
- 重新挂载客户端：`zotpilot register`
- 迁移旧 secret：`zotpilot config migrate-secrets`
- 升级：`zotpilot update [--migrate-secrets] [--re-register]`

## 3. 配置与凭证存储模型

### Shared config

位置：`~/.config/zotpilot/config.json`

保存：

- `zotero_data_dir`
- `embedding_provider`
- `openalex_email`
- `zotero_user_id`
- 其余非敏感索引/检索/视觉配置

### Secure credentials

默认 backend：

- macOS：Keychain

显式 fallback：

- 本地 secrets 文件（`~/.config/zotpilot/secrets.json`）
- 仅在用户明确启用或环境中指定 backend 时使用

保存：

- `gemini_api_key`
- `dashscope_api_key`
- `anthropic_api_key`
- `zotero_api_key`
- `semantic_scholar_api_key`

### Override

环境变量保留为 override 层：

- `GEMINI_API_KEY`
- `DASHSCOPE_API_KEY`
- `ANTHROPIC_API_KEY`
- `ZOTERO_API_KEY`
- `ZOTERO_USER_ID`
- `OPENALEX_EMAIL`
- `S2_API_KEY`

`doctor/status` 必须把这类来源标成 `env-override`。

## 4. 运行时解析模型

### `Config.load()`

职责：

- 只读 `config.json`
- 不读取 env
- 不读取 secure store
- 不再把 secret 视为 shared config 的一部分

### `resolve_runtime_settings()`

职责：

- 合成最终运行时配置
- 返回：
  - `config`：可供运行时直接使用的配置对象
  - `sources`：每个字段的生效来源
  - `secret_backend`
  - `legacy_sources`

优先级：

1. CLI 显式输入
2. env override
3. secure store
4. `config.json`
5. legacy sources 仅用于迁移探测，不作为正式运行时来源

## 5. CLI 职责

### `setup`

- 完整 onboarding
- 将普通配置写入 `config.json`
- 将 secret 写入 secure store
- 默认注册所有已检测客户端

### `config`

- 唯一配置修改入口
- 普通字段写 `config.json`
- secret 字段写 secure store
- `migrate-secrets` 是唯一正式迁移执行面

### `register`

- 只负责客户端接线
- 不向客户端配置写 secret
- `--*-key` 仅保留薄兼容层：
  - 先导入 secure store
  - 再执行注册
  - 打印 deprecated 提示

### `update`

- 升级 CLI / skills
- 检查 drift / legacy embedded secrets
- `--migrate-secrets` 仅转调 `config migrate-secrets`
- `--re-register` 只做无 secret 模板重注册

### `doctor / status`

- `doctor` 面向排障
- `status` 面向摘要
- 都必须展示：
  - write ops 是否就绪
  - secret backend
  - credentials source
  - 是否需重注册/重启
  - 是否发现 legacy embedded secrets

## 6. MCP 客户端注册模板

统一目标：

- Codex / Claude / OpenCode 只保存 `zotpilot mcp serve`
- 不再在客户端配置中写 `env` / `environment`

drift 判定：

- MCP 条目是否存在
- 命令是否为 `zotpilot mcp serve`
- 是否残留 embedded secret

## 7. 迁移与回滚

迁移入口：`zotpilot config migrate-secrets`

来源：

- 当前 `config.json` 里的 legacy secret
- 旧 `deep-zotero` 配置
- `.codex/config.toml`
- `.claude.json`
- `~/.config/opencode/opencode.json`

优先级：

1. CLI
2. env
3. secure-store 现有值
4. 客户端 embedded secret
5. 旧 config 值

回滚要求：

- 重写客户端配置前创建备份
- 若中途失败，输出备份路径并停止

## 8. 工具与工作流影响

### 继续可用

- 搜索
- 引用
- 状态/浏览/profile/review

### 必须失败并给出统一修复提示

- 入库
- tags
- collections
- notes
- annotation API reader

错误文案统一指向：

- `zotpilot setup`
- `zotpilot config set ...`
- `zotpilot config migrate-secrets`

## 9. 验收标准

- `setup` 完整 onboarding
- `config set zotero_api_key` 写 secure store，不写 `config.json`
- `register` 生成的客户端模板不含 secret
- `update` 不回写 secret 到 `config.json` 或客户端配置
- 只读工具在无写凭证时继续成功
- 写工具统一失败并指向新修复路径
- `config migrate-secrets` 可重复执行，且有备份可回滚
