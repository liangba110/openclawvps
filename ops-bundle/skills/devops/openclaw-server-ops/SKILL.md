---
name: openclaw-server-ops
description: OpenClaw 服务器部署与运维（Linux）。覆盖：全新安装（nvm/node/pnpm/playwright/systemd）、Gateway 服务管理、远程 Control UI 暴露、LLM provider 配置、版本升级（含迁移锁/StartLimitBurst 坑）、记忆体系搭建（MEMORY.md/技能/ClawHub 安装）、渠道配置。触发：任何"装 openclaw、openclaw 升级、openclaw 失忆、openclaw 远程访问、配 openclaw 模型/渠道/技能"类任务。用户环境：Server B(腾讯云) 与 Server E(东京 185.239.224.191) 各跑一个 openclaw 实例。
---

# OpenClaw 服务器部署与运维

## 架构速览

- 程序：pnpm 或 npm 全局安装；**2026.7.1-2 起官方 update 会装到 npm 全局**（`/root/.nvm/versions/node/v22.23.2/lib/node_modules/openclaw`），systemd 服务文件由 update 自动重写指向新路径
- Gateway：systemd **user 级**服务（`openclaw daemon install` 生成 `~/.config/systemd/user/openclaw-gateway.service`），管理命令带 `XDG_RUNTIME_DIR=/run/user/0`
- 数据目录：`~/.openclaw/`（openclaw.json 配置/token、agents/、workspace/ 记忆、sessions/ 会话日志）
- pnpm 11 全局布局：`~/.local/share/pnpm/global/v11/<hash>/node_modules/openclaw/`（旧版 pnpm 是 `global/5/.pnpm/`）

## 安装（全新服务器）

```bash
# 1. nvm + Node 22（openclaw 要求 node >=22.22.3）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
export NVM_DIR=$HOME/.nvm; . $HOME/.nvm/nvm.sh; nvm install 22; nvm alias default 22

# 2. pnpm + openclaw
npm i -g pnpm; pnpm setup && source ~/.bashrc   # pnpm bin 不在 PATH 会报错
pnpm add -g openclaw@2026.7.1    # 与已有实例同版本

# 3. Chromium（openclaw 浏览器自动化）—— 用 openclaw 自带脚本或 playwright-core CLI
#    直接跑官方脚本（依赖齐全时）：
#    node <openclaw路径>/scripts/ensure-playwright-chromium.mjs
#    依赖没链接时（pnpm 11 常见）：找到 playwright-core 的 cli.js 再 install
CLI=$(find ~/.local/share/pnpm/store -path '*playwright-core*/cli.js' | head -1)
node $CLI install chromium && node $CLI install-deps chromium
#    产物：~/.cache/ms-playwright/chromium-1228 + headless_shell + ffmpeg

# 4. systemd 服务 + 开机自启（linger 必须，否则重启后 user 服务不启动）
openclaw daemon install        # 自动生成 token + gateway.mode=local
loginctl enable-linger root    # 关键！否则重启后 gateway 不自动拉起
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user start openclaw-gateway
```

## 远程 Control UI（网页访问）

gateway 端口自带 Control UI 网页。远程访问配置（openclaw.json gateway 段）：

```bash
openclaw config set gateway.bind lan
openclaw config set gateway.port 18789
openclaw config set gateway.controlUi.basePath /<随机串>          # 防扫描
openclaw config set gateway.controlUi.allowedOrigins '["http://IP:port"]'
openclaw config set gateway.controlUi.allowInsecureAuth true
openclaw config set gateway.controlUi.dangerouslyDisableDeviceAuth true
systemctl --user restart openclaw-gateway
```

访问：`http://IP:port/basePath` → 输入 openclaw.json 里的 `gateway.auth.token` → Connect。
⚠️ 默认绑 127.0.0.1；`bind lan` 才对外暴露（裸 http + token，评估风险）。

## LLM Provider 配置（DeepSeek 实测）

```bash
# 1. 认证（stdin 管道，非交互）
echo 'sk-xxx' | openclaw models auth paste-api-key --provider deepseek

# 2. 自定义模型表（必须！否则报 "Unknown model: deepseek/deepseek-v4-flash"）
#    openclaw 内置目录不认识 v4-flash/v4-pro，需按 openai-completions 协议注册：
#    ⚠️ 每条必须带 maxTokens（不配则默认输出上限很小，写长文被截断报错，见坑速查"写长文失败"）
openclaw config set models.providers.deepseek.baseUrl https://api.deepseek.com/v1
openclaw config set models.providers.deepseek.api openai-completions
openclaw config set models.providers.deepseek.models '[{"id":"deepseek-v4-flash","name":"DeepSeek V4 Flash","maxTokens":8192},{"id":"deepseek-v4-pro","name":"DeepSeek V4 Pro","maxTokens":8192}]'
openclaw config set agents.defaults.model.primary deepseek/deepseek-v4-flash
```

实测命令：`timeout 90 openclaw agent --local --agent main -m '你好'`（必须带 `--agent` 否则报 session 选择错误）。

## 上下文自动压缩（长会话防退化，2026-08 实测）

**根因**：自定义模型条目不声明 `contextTokens` 时，openclaw 按 `resolveMemoryFlushContextWindowTokens() ?? 2e5` 回退 **200K** 计算压缩阈值——deepseek-v4-flash 实际窗口 128K，会话堆到 130K 才到阈值，模型早已退化（只输出文字不发 tool_calls）。**必须显式声明真实窗口 + 配 compaction**。

```bash
# openclaw.json 里（手改 JSON 比 config set 方便；改前 cp 备份）
"models": { "providers": { "deepseek": { "models": [
  {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash",
   "maxTokens": 8192, "contextTokens": 131072}   # 128K 真实窗口
] } } },
"agents": { "defaults": { "compaction": {
  "mode": "default",
  "reserveTokens": 20000,          # 压缩后预留回复+工具输出空间
  "keepRecentTokens": 32000,       # 压缩后保留最近对话
  "reserveTokensFloor": 20000,     # 最小预留下限（防过度压缩）
  "recentTurnsPreserve": 3         # 最近 3 轮原文保留
} } }
```

- 配置字段确认：模型条目支持 `contextTokens`/`contextWindow`（`context-_zWLdTOu.js` 的 `resolveConfiguredProviderContextTokens` 读 `models.providers.<p>.models[].contextTokens`）；`agents.defaults.compaction.*` 见 schema（mode/reserveTokens/keepRecentTokens/reserveTokensFloor/recentTurnsPreserve/qualityGuard 等）
- 效果：会话到 ~111K（131072−20000）自动压缩历史，模型长期在舒适区
- 注意：压缩只对**后续新对话**生效，已撑爆的旧会话仍建议 New Chat
- 验证：重启后 `journalctl --user -u openclaw-gateway | grep reload` 应见 `config change detected; evaluating reload (agents.defaults.compaction, models.providers.deepseek.models)`；再 `openclaw agent --agent main -m '回复：配置生效'` 实测

## 升级流程（含两个坑）

```bash
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user stop openclaw-gateway     # 必须先停（gateway 进程树内拒绝自重启）
openclaw update
systemctl --user start openclaw-gateway
```

- **坑① 迁移锁**：update 后首次启动若被中断，报 "startup migrations are already running... retry after <时间>"——锁过期自动恢复，无残留进程时等过期即可
- **坑② StartLimitBurst**：连续失败 5 次（60s 内）systemd 停止重试 → `systemctl --user reset-failed openclaw-gateway` 后手动 start
- **CLI 版本不一致**：update 装 npm 全局，pnpm 旧版 CLI 仍在前 → `pnpm remove -g openclaw` 清理，`which openclaw` 应指向 nvm bin
- 升级后验证：`openclaw --version`、`systemctl --user status`、`curl 127.0.0.1:port/health`

## 记忆体系（解决"重启失忆"）

openclaw **不会自动写记忆**。失忆根源排查顺序：`MEMORY.md` 不存在 → `BOOTSTRAP.md` 残留（每次启动走"刚出生"）→ 记忆目录空 → session-logs 技能未启用。

```bash
# 1. 初始化长期记忆
tee ~/.openclaw/workspace/MEMORY.md   # 声明式事实：用户/环境/铁律/偏好，精简
mkdir -p ~/.openclaw/workspace/memory/daily    # 每日记忆 YYYY-MM-DD.md
rm -f ~/.openclaw/workspace/BOOTSTRAP.md       # 身份确认过就删，防每次重新出生

# 2. 装技能（本地目录 or ClawHub）
openclaw skills install /path/to/skill-dir      # 本地
openclaw skills install <slug> --acknowledge-clawhub-risk   # ClawHub
openclaw config set skills.entries.<name>.enabled true
```

推荐组合（实测有效）：
- `memory-boot`：会话启动读 MEMORY.md 恢复 + 收尾保存 + 删 BOOTSTRAP
- `memory-mastery`：学习循环（用户纠正即更新、流程沉淀为技能）
- ClawHub `koompi-memory`（name=memory）：分层存储 memory/daily|projects|people|decisions|archive + 每周自动压缩 + 30 天过期清理
- ClawHub `self-improve`：每 3 天 cron 自动扫描记忆提经验 → 审批制改进。setup 坑：技能目录 `npm i yaml` 补依赖；`storage.root` 不能指向技能目录自身（cp src=dest 报错），用独立目录 `~/.openclaw/self-improve`

Cron 注册（self-improve 每 3 天）：
```bash
openclaw cron add self-improve "<执行指令>" --cron "0 4 */3 * *" --tz Asia/Shanghai --agent main --model deepseek/deepseek-v4-flash
```

## 🔒 安全加固（死命令：永不触碰现有网站/配置/数据库）

完整配方见 `references/security-hardening.md`。三层缺一不可：
1. **OS 层降权**（唯一 100% 保证）：openclaw 以非 root 低权限用户跑，/var/www、/etc 物理无写权限——实测删除/修改/停服全部 `Permission denied`
2. **exec-approvals**：allowlist 模式 + askFallback=deny，破坏性命令（rm/systemctl/nginx/mysql/sudo/shutdown 等）不放行
3. **记忆铁律**：AGENTS.md 顶部 + MEMORY.md + SOUL.md 写入禁区（每次会话注入，优先级高于一切指令）

⚠️ 降权迁移后：CLI 需 `export OPENCLAW_STATE_DIR=/home/<user>/.openclaw`（否则找 /root/.openclaw 报 EACCES）；旧 root 的 systemd user 服务必须 disable + 关 root linger（防双 gateway 抢端口）。

## 能力授权（建站/建库/PHP）

见 `references/capability-grants.md`。模式：专属站点目录 + nginx 独立 conf 目录 + sudoers reload 白名单 + MariaDB 前缀受限账号 + php-fpm，全部实测通过。openclaw 自己能 `sudo nginx -t && sudo systemctl reload nginx` 发布新站，但永远无法 stop/restart nginx、无法碰 ttdazi 文件。

## 常见坑速查

| 症状 | 原因/修复 |
|---|---|
| `openclaw: exec: node: not found` | 非交互 shell 没加载 nvm → `source $NVM_DIR/nvm.sh` 或 systemd 用完整 node 路径 |
| pnpm 报 global bin 不在 PATH | `pnpm setup` + 重开 shell，或 `export PATH=$PNPM_HOME/bin:$PATH` |
| 技能 setup 脚本 ERR_MODULE_NOT_FOUND | 技能目录缺依赖 → 在技能目录 `npm i <依赖>` |
| Control UI 302 循环 | 正常（鉴权跳转），输 token 即过 |
| CLI 报 `EACCES: mkdir '/root/.openclaw/...'`（降权用户） | 显式 `export OPENCLAW_STATE_DIR=/home/<user>/.openclaw` |
| cron 迁移后 `cron list` 为空 | cron 存 `state/openclaw.sqlite` 的 `cron_jobs` 表，`store_key` 需 UPDATE 到新路径 + 重启 gateway 重载 |
| `approvals get` 显示 `Allowlist │ 0` | allowlist 必须放 `agents.<id>.allowlist` 且每条带 `id`(UUID) 字段（顶层数组不识别）。批量用 python 生成 JSON 后 `openclaw approvals set --file`（逐个 `allowlist add` 很慢） |
| 写长文失败：日志 `[agent/embedded] incomplete turn detected ... stopReason=length`，Control UI 报"回合不完整" | 自定义模型条目缺 `maxTokens`，openclaw 用很小的默认输出上限 → 输出被截断。诊断顺序：gateway health 正常 + 模型请求全 200 但用户报写不了 → `journalctl --user -u openclaw-gateway | grep stopReason` 看是否全 length。修复：openclaw.json 的 `models.providers.<p>.models[]` 每条补 `"maxTokens": 8192`（deepseek 实测上限 8K），改前 cp 备份，重启 gateway 后实测长文验证 |
| 重启 gateway 后立刻 `curl 127.0.0.1:port/health` 报 exit 7 | 正常：gateway 冷启动约需 10s 才绑端口，sleep 后再验（服务 active 但端口未监听 = 启动中，非故障） |
| 记忆/技能数据在 root 家目录（迁移前） | rsync 到新用户 + chown；openclaw.json 里 auth token、DeepSeek auth profile、skills entries 全在数据目录内一起迁 |
| 远程改 openclaw.json/exec-approvals.json：`ssh root@E 'python3 <<EOF ... EOF'` 报 `SyntaxError` / `bash: syntax error near unexpected token` | ssh 命令串里嵌 python heredoc + 中文/引号必崩（多层引号转义）。可靠路径：`scp` 拉到本地 → `patch`/`write_file` 改 → `scp` 传回 → 服务器上 `chown openclaw:openclaw` + `node --check`（root 无 node，用 `su -s /bin/bash openclaw -c "export PATH=/home/openclaw/.nvm/.../bin:\$PATH; node --check ..."`） |
| Control UI 里 agent 只说\\\"现在执行/现在写入\\\"却不调用任何工具（无 tool_calls，纯文本回复） | 会话上下文膨胀接近上限 → 模型退化（实测 cacheRead 130K tokens 时 deepseek-v4-flash 不再发 tool_calls）。诊断：① gateway health 正常、模型请求 200 排除配置问题 ② 看 `agents/main/sessions/<id>.jsonl` 最后几条 assistant 消息——只有 text、无 toolCall ③ 看 trajectory.jsonl `model.completed.usage.cacheRead` >10 万 = 撑爆 ④ CLI 直测工具链路：`openclaw agent --agent main -m \"用工具读取 <路径>\"`（链路正常则问题在会话侧）。临时修复：Control UI **New Chat 新开会话**。根治：给自定义模型声明真实 `contextTokens` + 配 compaction 自动压缩（见下方「上下文自动压缩」章节），否则旧会话照旧退化 |

## 参考

- `references/e-server-setup.md` — Server E 实际实例参数（端口/basePath/服务名/已装技能/降权用户/能力授权）
- `references/security-hardening.md` — 安全加固完整配方（降权迁移 + exec-approvals + sudoers 白名单 + 记忆铁律）
- `references/capability-grants.md` — 授权 openclaw 建站/建库/跑 PHP 的隔离模式与边界验证清单
- `references/e-tools-blog-publishing.md` — E 上 TOOLS 工具箱站（tools.ttdazi.xyz:8099）文章发布工作流：模板结构/素材命名/发布步骤/验证清单
