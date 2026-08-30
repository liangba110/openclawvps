---
name: openclaw-server-deploy
description: OpenClaw/Clawdbot gateway 全新服务器安装与运维。覆盖 nvm+pnpm 全局安装、Playwright chromium 浏览器依赖、systemd user 服务+linger 开机自启、非交互 shell 的 PATH 陷阱、pnpm 11 新布局、多实例（B/E 服务器）管理。当用户要求在新服务器上安装/部署/复制 openclaw、维护 openclaw gateway 时触发。
---

# OpenClaw Gateway 服务器安装与运维

## 适用场景

用户把 openclaw（腾讯云 Server B 上已有实例）部署到新服务器（如东京 Server E），要求「保证服务器现有数据不动」。原则：**全新实例安装，不迁移已有实例的 agents/凭据/配置**（互不干扰）；数据隔离靠独立目录（`/root/.openclaw` 或 `$HOME/.openclaw`）。

## 现有实例参考（2026-08）

| 实例 | 服务器 | 运行用户 | 安装方式 | Gateway 端口 | 数据目录 |
|---|---|---|---|---|---|
| B | 82.157.202.24（腾讯云） | ubuntu | pnpm **旧布局** `global/5/.pnpm/` | 38598（**0.0.0.0 公网监听**） | /home/ubuntu/.openclaw |
| E | 185.239.224.191（东京） | root | pnpm **新布局** `global/v11/<hash>/` | 18789（**仅 127.0.0.1**） | /root/.openclaw |

版本对齐：`openclaw --version`（当前 2026.7.1，`pnpm add -g openclaw@2026.7.1` 装同版本）。

B/E 两实例的完整配置原文（controlUi、DeepSeek provider、渠道凭据状态）见 `references/openclaw-deployments.md`。

## 安装步骤（全新服务器，已验证 2026-08-09）

```bash
# 1. Node（openclaw 要求 node ≥22.22.3，推荐 24 LTS；实测 v22.23.2 可跑）
curl -sS -o /tmp/nvm_install.sh https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh
bash /tmp/nvm_install.sh
export NVM_DIR=$HOME/.nvm; . $HOME/.nvm/nvm.sh
nvm install 22 && nvm alias default 22

# 2. pnpm + openclaw（⚠️ pnpm setup 后要 source，见下方 PATH 陷阱）
npm i -g pnpm
pnpm setup && . ~/.bashrc   # 或手动 export PATH=$HOME/.local/share/pnpm/bin:$PATH
export PATH=$HOME/.local/share/pnpm/bin:$PATH
pnpm add -g openclaw@2026.7.1
openclaw --version

# 3. Playwright chromium（openclaw browser 功能依赖）
#    ⚠️ openclaw 没有 browser install 子命令！浏览器由 playwright-core 管理。
#    openclaw 自带 scripts/ensure-playwright-chromium.mjs，但在 pnpm 11 全局布局下
#    会 MODULE_NOT_FOUND（openclaw/node_modules 是空的，依赖在 store 里）——不要用它。
#    正确方式：找 store 里 playwright-core 的 cli.js 直接装：
CLI=$(find $HOME/.local/share/pnpm/store -path '*playwright-core*/cli.js' | head -1)
node "$CLI" install chromium        # 装 chromium-1228 + headless shell + ffmpeg
node "$CLI" install-deps chromium   # apt 装系统运行库（Ubuntu 24.04 必需）

# 4. gateway systemd 服务
openclaw daemon install   # 生成 user 级服务 /root/.config/systemd/user/openclaw-gateway.service
# ⚠️ user 服务不依赖登录会话自动跑？必须开 linger 否则重启后不启动：
loginctl enable-linger root
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user daemon-reload && systemctl --user start openclaw-gateway
systemctl --user status openclaw-gateway

# 5. 验证
curl -s http://127.0.0.1:<port>/health   # → {"ok":true,"status":"live"}
ss -tlnp | grep <port>                   # 默认绑 127.0.0.1（比 B 的 0.0.0.0 安全）
```

## 陷阱（都是实测踩过的）

1. **非交互 SSH shell 不加载 nvm**（root 的 .bashrc 有 `[ -z "$PS1" ] && return`）→ `openclaw` 报 `exec: node: not found`。SSH 单条命令跑 openclaw 前必须：`export NVM_DIR=/root/.nvm; . /root/.nvm/nvm.sh; export PATH=$HOME/.local/share/pnpm/bin:$PATH`。交互式登录（bash -l）不受影响。
2. **pnpm 11 全局布局变了**：`global/v11/<hash>/node_modules/openclaw/`（旧版是 `global/5/.pnpm/openclaw@x/node_modules/`）。openclaw 包内 node_modules 只有 `.bin`（依赖在 store），`find store -path '*playwright-core*/cli.js'` 定位依赖。B（旧 pnpm）的路径不能直接照抄到 E。
3. **pnpm 报 "global bin directory not in PATH"** 但明明 export 了：`pnpm config get global-bin-dir` 返回 undefined，pnpm 用 fallback 判断——先 `pnpm setup` 并 source，再 export PATH，再安装。
4. **daemon install 自动分配端口**（E 得 18789，B 是 38598）：端口是写死的还是自动的看环境变量 `OPENCLAW_GATEWAY_PORT`，无需手动指定，无冲突即可。
5. **user systemd 服务 + linger**：`openclaw daemon install` 生成的是 **user 级**服务，服务器重启后只有对应用户有登录会话才起；`loginctl enable-linger root` 一劳永逸。
6. **daemon install 首次运行自动生成** gateway token + `gateway.mode=local`，配置落 `/root/.openclaw/openclaw.json`——全新实例无需手动建配置。

## 与现有系统共存（用户铁律：数据不动）

- 新实例目录独立（/root/.openclaw），不碰 `/var/www`、nginx、数据库。
- E 上 nginx 是 `www.ttdazi.xyz` 反代到 `api_upstream`（Server A），openclaw 装完必须回归验证：`curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/ -H 'Host: www.ttdazi.xyz'` → 200。
- 磁盘/内存预算：chromium ~200MB + gateway ~320MB 内存；装前 `df -h` + `free -h` 确认够。

## Control UI 远程网页访问（gateway 端口自带）

gateway 端口本身提供 **OpenClaw Control 网页**（`openclaw dashboard` 只是本地开浏览器；`curl http://127.0.0.1:<port>/` 返回 `<title>OpenClaw Control</title>`）。远程暴露配置（与 B 一致的做法）：

```bash
openclaw config set gateway.bind lan
openclaw config set gateway.port <port>
openclaw config set gateway.controlUi.basePath /<随机串>        # 防扫描，如 E=/oc3385、B=/eucgbm
openclaw config set gateway.controlUi.allowedOrigins '["http://<IP>:<port>"]'
openclaw config set gateway.controlUi.allowInsecureAuth true
openclaw config set gateway.controlUi.dangerouslyDisableDeviceAuth true   # 关设备配对，直接 token 登录
export XDG_RUNTIME_DIR=/run/user/0
systemctl --user restart openclaw-gateway
ss -tlnp | grep <port>   # bind lan 后监听 0.0.0.0
```

访问：`http://<IP>:<port>/<basePath>`（302 到带斜杠是正常的鉴权跳转）→ 填 WebSocket URL（自动带出）+ **token**（`openclaw.json` 里 `gateway.auth.token`）→ Connect → 聊天界面。浏览器实测验证登录成功才算交付。
⚠️ 裸 http + token 有明文风险，basePath 随机串缓解；用户接受此方式时保持与 B 一致。

## 模型 provider 配置（DeepSeek 例）

```bash
# 1. API key（stdin 管道，非交互）
echo 'sk-xxx' | openclaw models auth paste-api-key --provider deepseek
#    → Auth profile: deepseek:manual (deepseek/api_key)

# 2. ★自定义模型表——否则 agent 报 "FailoverError: Unknown model: deepseek/deepseek-v4-flash"
#    openclaw 内置模型目录不认识 v4-flash/v4-pro，必须在 config 注册（参考 B 的配置）：
openclaw config set models.providers.deepseek.baseUrl https://api.deepseek.com/v1
openclaw config set models.providers.deepseek.api openai-completions
openclaw config set models.providers.deepseek.models '[{"id":"deepseek-v4-flash","name":"DeepSeek V4 Flash"},{"id":"deepseek-v4-pro","name":"DeepSeek V4 Pro"}]'

# 3. 默认模型
openclaw config set agents.defaults.model.primary deepseek/deepseek-v4-flash
#    验证：openclaw models status --plain → deepseek/deepseek-v4-flash

# 4. agent 实测回复
openclaw agent --local --agent main -m '用一句话介绍你自己'
#    报错 "Pass --to ... choose a session" → 必须加 --agent main；消息用 -m 参数不是位置参数
```

## 渠道配置（QQ / 微信）

```bash
openclaw channels list --all    # 看可用渠道；channels add --channel <name> 首次运行会自动装插件
openclaw channels add --channel qqbot --token '<appId>:<clientSecret>'
```

- **QQ（qqbot）**：插件自动装；凭据格式 `--token appId:clientSecret`。⚠️ **一个 QQ 开放平台 appId 只能一个 WebSocket 连接实例**——已有实例占用（如 B 用 1904989300）时，另一台服务器再配会互相踢下线。必须新申请 appId。
- **微信（openclaw-weixin）**：插件 `@tencent-weixin/openclaw-weixin`（腾讯官方）；"does not support non-interactive add"，需交互式引导；公众号一个账号只能配一个服务器 URL，被业务系统占用时无法给 openclaw 用。
- 凭据缺失时如实列出用户需提供什么（key/新 appId/公众号），不要拿其他服务器凭据硬配（冲突/合规风险）。
- 用户说"先直接用网页版"时：模型配好 + Control UI 可用即交付，渠道待凭据就位再配。

## 验证清单（交付前全过）

1. `openclaw --version` ✅
2. `curl http://127.0.0.1:<port>/health` → `{"ok":true,"status":"live"}` ✅
3. `ss -tlnp | grep <port>` 监听确认 ✅
4. 浏览器打开 `http://IP:port/basePath` + token 登录 → 聊天界面 ✅
5. `openclaw agent --local --agent main -m '你好'` 有真实回复 ✅
6. 现有数据零影响：nginx 站点 200（`curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/ -H 'Host: <域名>'`）、数据目录完好、`df -h`/`free -h` 余量 ✅

## 后续配置

渠道凭据就位后 `openclaw channels add ...` 逐个配；`openclaw daemon status` 检查服务；`openclaw backup` 做状态备份。
