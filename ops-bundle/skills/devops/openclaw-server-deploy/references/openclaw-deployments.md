# OpenClaw 部署实例详情（2026-08 实测）

## B 实例（腾讯云 82.157.202.24）—— 参考/母版

| 项 | 值 |
|---|---|
| 运行用户 | ubuntu |
| openclaw | 2026.7.1，pnpm **旧布局** `global/5/.pnpm/openclaw@2026.7.1/` |
| Gateway | 端口 38598，`bind: lan`（0.0.0.0 公网监听），user systemd 服务 |
| 数据目录 | /home/ubuntu/.openclaw（agents 20+、credentials、devices、browser-existing-session） |
| Control UI | `http://82.157.202.24:38598/eucgbm`，basePath `/eucgbm` |
| 模型 | agents.defaults.model.primary = deepseek/deepseek-v4-flash |
| 渠道 | qqbot（appId 1904989300，enabled）、lightclawbot、openclaw-weixin（空） |

**B 的 models.providers.deepseek 自定义配置（openclaw.json 原文结构，E 照抄）**：
```json
"models": { "providers": { "deepseek": {
  "baseUrl": "https://api.deepseek.com/v1",
  "apiKey": "<key>",
  "api": "openai-completions",
  "models": [
    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash"},
    {"id": "deepseek-v4-pro",   "name": "DeepSeek V4 Pro"}
  ]
}}}
```
B 的 controlUi 配置：`allowedOrigins: ["http://82.157.202.24:38598"]`、`allowInsecureAuth: true`、`dangerouslyDisableDeviceAuth: true`、`basePath: "/eucgbm"`。

## E 实例（东京 185.239.224.191）—— 全新部署（2026-08-09/10）

| 项 | 值 |
|---|---|
| 运行用户 | root |
| openclaw | 2026.7.1，pnpm **新布局** `global/v11/<hash>/node_modules/openclaw/` |
| Gateway | user 服务 openclaw-gateway，端口 18789，`bind: lan`（0.0.0.0），linger 已开 |
| 数据目录 | /root/.openclaw（openclaw.json + identity + logs + state） |
| Control UI | `http://185.239.224.191:18789/oc3385`，basePath `/oc3385`，token 在 /root/.openclaw/openclaw.json `gateway.auth.token` |
| 模型 | deepseek/deepseek-v4-flash；key 复用 Hermes 的（/home/ubuntu/.hermes/.env DEEPSEEK_API_KEY），models.providers.deepseek 配置与 B 相同结构 |
| 渠道 | qqbot/weixin 插件已装，**未配凭据**（QQ appId 需新申请；公众号被同途搭子占用） |

E 上 openclaw 与现有服务共存：nginx 只服务 `www.ttdazi.xyz` 反代（api_upstream→Server A），openclaw 目录独立不冲突。

## 排障记录

- **agent 报 `Unknown model: deepseek/deepseek-v4-flash`** → openclaw 内置模型目录无此模型，配 `models.providers.deepseek.models` 自定义表即解决（改 config 后无需重启 gateway，`models status --plain` 立即生效）
- **`openclaw browser install` 报 Too many arguments** → 不存在该子命令；chromium 由 playwright-core 管理（store 里找 cli.js）
- **`ensure-playwright-chromium.mjs` 报 MODULE_NOT_FOUND** → pnpm 11 布局下 openclaw/node_modules 空，依赖在 store；别用该脚本
- **curl https 测 E 站点一直 301** → Host 头要带 `www.ttdazi.xyz`（server_name 精确匹配），带 `ttdazi.xyz` 裸域会落到默认 server 跳转
