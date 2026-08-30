---
name: openclaw-deployment
description: OpenClaw(Clawdbot) 的安装、配置、远程访问与升级运维。触发：任何服务器上装 openclaw、配 gateway/Control UI/模型渠道、openclaw update 升级、换 API key、排查 gateway 起不来/Unknown model/迁移锁问题。用户环境：B(腾讯云) 跑 ai-ecom-ops 等 agent，E(东京) 有全新实例。
---

# OpenClaw 部署与运维（2026-08 实测）

## 架构速览

- openclaw 2026.7.x：CLI + Gateway（systemd user 服务）+ Control UI（网页，gateway 端口自带）
- Gateway 端口本身提供 **OpenClaw Control 网页**（`openclaw dashboard` 只是打开浏览器）；浏览器登录页 = WebSocket URL + token
- B 上实例：`/home/ubuntu/.openclaw/`（openclaw.json 含 channels/agents/gateway 配置，agent 默认 deepseek/deepseek-v4-flash）
- E 上实例：`/home/openclaw/.openclaw/`（降权用户 openclaw，gateway 端口 18789；CLI 需 `export OPENCLAW_STATE_DIR=/home/openclaw/.openclaw`）

## 全新安装（Server E 实测路径）

```bash
# 1. nvm + node v22（openclaw 需要 node >=22.22.3）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
export NVM_DIR=$HOME/.nvm; . $HOME/.nvm/nvm.sh; nvm install 22; nvm alias default 22

# 2. pnpm + openclaw（版本与现有实例对齐，如 2026.7.1）
npm i -g pnpm && pnpm setup   # pnpm setup 后需 source ~/.bashrc 或手动 export PATH
export PATH=$HOME/.local/share/pnpm/bin:$PATH
pnpm add -g openclaw@2026.7.1
openclaw --version   # 验证（非交互 shell 必须手动 source nvm + export PATH，否则 exec: node: not found）

# 3. Playwright chromium（browser 功能必需）
#  ⚠️ openclaw 没有 `browser install` 子命令！且 pnpm 11 全局装的 openclaw，node_modules 顶层只有 .bin
#  （依赖都在 store，ensure-playwright-chromium.mjs 会 MODULE_NOT_FOUND）
CLI=$(find $HOME/.local/share/pnpm/store/v11/links -path '*playwright-core*/cli.js' | head -1)
node "$CLI" install chromium
node "$CLI" install-deps chromium   # 系统依赖（root 可跑）

# 4. systemd 服务 + 开机自启
openclaw daemon install    # 生成 ~/.config/systemd/user/openclaw-gateway.service + 自动生成 token
loginctl enable-linger root   # 必须！user 服务无 lingering 则重启后不自动起
export XDG_RUNTIME_DIR=/run/user/0; systemctl --user start openclaw-gateway
```

## Control UI 远程访问（网页接口）

gateway 端口自带 Control UI，远程暴露 = bind lan + basePath（随机串防扫描）：

```bash
openclaw config set gateway.bind lan
openclaw config set gateway.port 18789
openclaw config set gateway.controlUi.basePath /<随机串>
openclaw config set gateway.controlUi.allowedOrigins '["http://IP:PORT"]'
openclaw config set gateway.controlUi.allowInsecureAuth true
openclaw config set gateway.controlUi.dangerouslyDisableDeviceAuth true
systemctl --user restart openclaw-gateway
```

- 访问：`http://IP:PORT/<basePath>` → 302 到 basePath/ → token 登录（token 在 `~/.openclaw/openclaw.json` 的 gateway.auth.token）
- bind lan = 0.0.0.0 监听（裸 http + token，与 B 同模式）；bind 默认 127.0.0.1

## 模型 provider 配置（关键坑）

**`Unknown model: deepseek/deepseek-v4-flash`** = openclaw 内置模型目录不认识该模型。必须自定义 provider（参照 B 的 openclaw.json）：

```bash
openclaw config set models.providers.deepseek.baseUrl https://api.deepseek.com/v1
openclaw config set models.providers.deepseek.api openai-completions
# ⚠️ maxTokens 必须配：不配则默认输出上限很小，写长文被截断（日志 stopReason=length / incomplete turn detected）
openclaw config set models.providers.deepseek.models '[{"id":"deepseek-v4-flash","name":"DeepSeek V4 Flash","maxTokens":8192},{"id":"deepseek-v4-pro","name":"DeepSeek V4 Pro","maxTokens":8192}]'
openclaw config set agents.defaults.model.primary deepseek/deepseek-v4-flash
```

API key（stdin 管道，非交互）：
```bash
echo 'sk-xxx' | openclaw models auth paste-api-key --provider deepseek
# 验证：openclaw models auth list → Profiles: - deepseek:manual [deepseek/api_key]
```

## 渠道配置

- `openclaw channels add --channel qqbot --token <appId>:<clientSecret>`（QQ Bot 插件自动安装）
- `openclaw channels add --channel weixin`（腾讯官方插件 @tencent-weixin/openclaw-weixin，**不支持非交互 add**，需交互引导）
- ⚠️ QQ bot 一个 appId 只能一个实例：B 已占用 appId 1904989300，E 再配会互相踢下线；公众号一个只能配一个服务器 URL（业务公众号被同途搭子占用后不能再给 openclaw）
- `openclaw channels list` / `openclaw channels list --all` 查看状态

## openclaw update 升级（✅ 实测流程 + 两个坑）

```bash
systemctl --user stop openclaw-gateway   # ① 必须先从 gateway 进程树外跑（update 在进程内会拒绝自己重启）
openclaw update                          # ②
systemctl --user start openclaw-gateway  # ③
```

**坑 1 — 迁移锁冲突**：update 后首次启动若迁移进程中断，后续启动报 `startup migrations are already running ... retry after <时间>`（锁 5 分钟过期）。无残留迁移进程时等过期即可；systemd 因 StartLimitBurst=5 停止重试后：`systemctl --user reset-failed openclaw-gateway && systemctl --user start openclaw-gateway`。

**坑 2 — 双版本残留**：update 会把主程序装到 **npm 全局**（`~/.nvm/versions/node/v22.x/lib/node_modules/openclaw`），并自动改写服务文件 ExecStart 指向新路径；但旧 pnpm 全局版仍在 PATH 前面（CLI 显示旧版本）。统一：
```bash
pnpm remove -g openclaw   # 清 pnpm 侧
which openclaw            # 应指向 ~/.nvm/versions/node/v22.x/bin/openclaw
openclaw --version        # 显示新版本如 2026.7.1-2
```

## 验证清单

1. `curl http://127.0.0.1:<port>/health` → `{"ok":true,"status":"live"}`
2. `openclaw agent --agent main -m '回复：成功'` → agent 正常回复（走 gateway）
3. Control UI：`curl -s -o /dev/null -w '%{http_code}' http://IP:port/<basePath>` → 302（鉴权跳转正常）
4. 升级后版本一致性：`openclaw --version` 与 `systemctl --user status openclaw-gateway` 描述一致

## 常见故障速查

| 症状 | 原因/修复 |
|---|---|
| 写长文被截断（日志 `stopReason=length` / incomplete turn detected） | 模型条目缺 `maxTokens` → 补 `"maxTokens": 8192`，重启 gateway |
| Control UI 里 agent 只说"现在执行"却从不调用工具 | 会话上下文撑爆（trajectory `model.completed.usage.cacheRead` >10 万），deepseek-v4-flash 退化只出文字不发 tool_calls → **New Chat 新开会话**即可，无需改配置；先 `openclaw agent --agent main -m "用工具读取 <路径>"` 验证工具链路本身正常 |
| 重启 gateway 后 health 立即 curl 报 exit 7 | 冷启动约 10s 才绑端口，sleep 后再验（服务 active + 端口未监听 = 启动中，非故障） |

## 参考

- B 的 openclaw.json 是渠道/agent 配置的权威参照（`/home/ubuntu/.openclaw/openclaw.json`）：qqbot appId+clientSecret、agents.defaults.model、gateway.controlUi
- 详细安装日志/报错样本见 `references/server-e-install-notes.md`
