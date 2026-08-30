# Server E openclaw 安装实录（2026-08-10）

## 环境

- E: 185.239.224.191（东京，Ubuntu 24.04，2核3.8G/40G，root 密钥登录，fail2ban）
- openclaw 2026.7.1 → update → 2026.7.1-2 (0790d9f)
- 安装到 root（用户用 root 管 E）；B 上实例在 ubuntu 用户（/home/ubuntu/.openclaw）

## 报错样本与解法

### 1. pnpm 11 全局布局（非 5.x）

旧版 pnpm 全局在 `~/.local/share/pnpm/global/5/.pnpm/`，**pnpm 11 在 `~/.local/share/pnpm/global/v11/<hash>/node_modules/`**：
- 顶层 node_modules 只有 `.bin/`（依赖在 store，`store/v11/links/...`）
- `openclaw/node_modules/` 空 → `scripts/ensure-playwright-chromium.mjs` 跑挂（MODULE_NOT_FOUND）
- 解法：`find ~/.local/share/pnpm/store/v11/links -path '*playwright-core*/cli.js'` → `node $CLI install chromium`

### 2. 非交互 shell 找不到 node

`/root/.local/share/pnpm/bin/openclaw: 48: exec: node: not found`
→ nvm 装在 .bashrc 但非交互 SSH（ssh host 'cmd'）不加载。每条命令前：`export NVM_DIR=/root/.nvm; . /root/.nvm/nvm.sh; export PATH=/root/.local/share/pnpm/bin:$PATH`（或用完整 node 路径）。systemd 服务文件里 ExecStart 是完整路径，不受影响。

### 3. Control UI 鉴权

- 直接 curl `/oc3385` → 302（重定向到 `/oc3385/`），跟随返回 `<!doctype html><html data-openclaw-control-ui-base-path="/oc3385"` + title "OpenClaw Control"
- 浏览器打开：WebSocket URL 自动带出（ws://IP:port/basePath）+ 输入 token → Connect → 聊天界面（Gateway status: Online）

### 4. openclaw update 迁移锁

```
Reason: OpenClaw startup migrations are already running for this state directory; retry after the other gateway finishes or after 2026-08-10T07:07:30.339Z
```
- 触发：update 后首次启动进程被 systemd 重启打断，迁移锁残留 5 分钟
- systemd user 服务 StartLimitBurst=5/StartLimitIntervalSec=60：5 次失败后彻底 failed（不自动重试）
- 解法：锁过期后 `systemctl --user reset-failed openclaw-gateway && systemctl --user start openclaw-gateway`

### 5. 双版本残留

- update 装到 npm 全局 `~/.nvm/versions/node/v22.23.2/lib/node_modules/openclaw`（version 2026.7.1-2），服务文件 ExecStart 自动改写为新路径
- 但 `openclaw --version` 仍显示旧版（pnpm bin shim 在前）→ `pnpm remove -g openclaw` 后统一（CLI 指向 nvm bin）

## E 实例最终参数

- gateway: 127.0.0.1→bind lan, 端口 18789（B 用 38598）
- Control UI: http://185.239.224.191:18789/oc3385，token 见 /root/.openclaw/openclaw.json gateway.auth.token
- 服务: ~/.config/systemd/user/openclaw-gateway.service（root，linger=yes 开机自启）
- 模型: models.providers.deepseek {baseUrl api.deepseek.com/v1, api openai-completions, models [deepseek-v4-flash, deepseek-v4-pro]}
- 渠道: QQ/Weixin 插件已装未配（QQ appId 被 B 占用；公众号被同途搭子占用）
