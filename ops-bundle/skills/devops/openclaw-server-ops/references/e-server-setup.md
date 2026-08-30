# Server E openclaw 实例参数（2026-08-10 部署 + 降权 + 能力授权）

## 实例信息

| 项 | 值 |
|---|---|
| 服务器 | E = 185.239.224.191（东京，Ubuntu 24.04，2核3.8G/40G，root 密钥 SSH） |
| 版本 | openclaw 2026.7.1-2 (0790d9f)，**npm 全局**，装在 **openclaw 用户**下 |
| 运行用户 | **`openclaw`（低权限，无 sudo）**——2026-08-10 从 root 降权迁移（见 security-hardening.md） |
| Node | openclaw 用户 v22.23.2（nvm，/home/openclaw/.nvm），pnpm 已从 openclaw 侧移除 |
| 数据目录 | `/home/openclaw/.openclaw`（⚠️ CLI 需 `export OPENCLAW_STATE_DIR=/home/openclaw/.openclaw`） |
| Gateway 服务 | openclaw 用户 systemd user 服务 `openclaw-gateway`，linger 已开，端口 18789（bind lan） |
| Control UI | `http://185.239.224.191:18789/oc3385`，token 在 `/home/openclaw/.openclaw/openclaw.json` 的 `gateway.auth.token` |
| Chromium | /home/openclaw/.cache/ms-playwright/chromium-1228 + headless_shell + ffmpeg |
| 系统组件 | MariaDB 10.11（root 密码 /root/.openclaw_db_pw）+ php8.3-fpm |

## 模型配置（2026-08-17 更新）

- provider: deepseek（baseUrl https://api.deepseek.com/v1, api openai-completions）
- 模型表：**仅 deepseek-v4-flash**（2026-08-17 用户要求删除 v4-pro），条目含 `maxTokens: 8192` + `contextTokens: 131072`（见 SKILL.md「上下文自动压缩」章节）
- `agents.defaults.compaction`：mode=default, reserveTokens=20000, keepRecentTokens=32000, reserveTokensFloor=20000, recentTurnsPreserve=3（长会话自动压缩防退化）
- API key：用户自备（auth profile deepseek:manual），换 key：`echo <key> | openclaw models auth paste-api-key --provider deepseek`

## 记忆体系（已搭建，业务信息已清空 = 全新个人助理）

- `MEMORY.md`：**业务信息已清空**（2026-08-10 用户要求全新实例），当前内容是：安全铁律 + 能力范围（可建站/建库/PHP、禁碰 ttdazi）
- `memory/daily/YYYY-MM-DD.md`：koompi-memory 规范目录（daily/projects/people/decisions/archive）
- BOOTSTRAP.md：已删除
- 已装技能（全 ready）：memory-boot、memory-mastery、memory=koompi-memory、self-improve
- self-improve：数据目录 `/root/.openclaw/self-improve/`（⚠️ 迁移时未动，实际在 root 家目录——如需降权隔离应迁到 /home/openclaw 下），cron `0 4 */3 * *` Asia/Shanghai，model deepseek/deepseek-v4-flash，target isolated
- session-logs 技能：jq/rg 已装但 check 仍显示 needs setup（非核心，未深究）

## 安全加固（已生效，三层）

1. OS 层：openclaw 用户无 /var/www、/etc 写权限（实测 rm/改/停服全 Permission denied）
2. exec-approvals：allowlist 模式（50 条安全命令）+ askFallback=deny；rm/systemctl/nginx/mysql/sudo 等不放行（文件 /home/openclaw/.openclaw/exec-approvals.json）
3. 记忆铁律：AGENTS.md 顶部 + MEMORY.md + SOUL.md（禁区：/var/www/ttdazi、/etc/nginx conf.d ttdazi-*、数据库、备份；永不提权）

sudoers 白名单（/etc/sudoers.d/openclaw）：`nginx -t`、`systemctl reload nginx[.service]`、`systemctl reload php8.3-fpm[.service]`——仅 reload，无 stop/restart。

## 能力授权（openclaw 可自建）

- 网站目录 `/var/www/openclaw-sites/` + nginx 配置 `/etc/nginx/openclaw-conf/*.conf`（nginx.conf 已 include）
- 数据库：`openclaw@localhost`（密码 /etc/openclaw-db-credentials，644），可建 `openclaw_*` 库
- PHP：php8.3-fpm；测试站 `http://185.239.224.191:8088/`（hello 示例，PHP+DB 连接正常）
- 详细配方见 capability-grants.md

## 渠道状态

- QQ/微信插件已安装，**未配置凭据**（QQ appId 1904989300 被 B 占用会互踢；公众号被同途搭子占用）。用户决定先用网页版
- 用户偏好：简洁中文回复、✅/❌ 标记、不展示中间调试步骤、视觉品质要求极高

## E 上其他服务（openclaw 禁碰）

- nginx：www.ttdazi.xyz 国际站反代（`/etc/nginx/sites-enabled/ttdazi-xyz` → api_upstream）
- `/var/www/ttdazi` 静态站（www-data），`/tmp/ttdazi*` 备份
- fail2ban 启用，certbot.timer 启用（证书 www.ttdazi.xyz）
