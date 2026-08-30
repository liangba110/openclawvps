# Open Auto v2 — 全自动智能运维框架

> 腾讯云 VPS 全自动运维框架 v2：巡检→检测→修复→验证→通知→日报，闭环自治。

## v2 新增能力

| 模块 | 脚本 | 频率 | 说明 |
|------|------|------|------|
| 多站点巡检 | `multi-site-guard.cjs` | 每5分钟 | HTTP + PM2 双重检测，支持 N 站点 |
| 主动事件监控 | `event-watcher.cjs` | 持续/每分钟 | PM2 进程变化、磁盘>85%、内存>90% |
| 自愈日报 | `daily-report.cjs` | 每日 23:55 | 汇总当日巡检，输出 Markdown 报告 |
| QQ通知模板 | `notify_qq.sh` | 事件触发 | 统一队列入口，支持 QQ_BOT_TOKEN |

## 架构

```
┌──────────────────────────────────────────────────────┐
│                  Open Auto v2 运维框架                │
├────────────┬──────────────┬──────────────────────────┤
│  L1 心跳   │  L2 数据     │  L3 业务      │ v2 新增  │
│  watchdog  │  db_guard    │  toc_guard    │          │
│  每分钟    │  每分钟      │  每小时       │          │
├────────────┴──────────────┴──────────────────────────┤
│  event-watcher (PM2/磁盘/内存)  持续监控             │
│  multi-site-guard (N站点 HTTP+PM2)  每5分钟          │
├──────────────────────────────────────────────────────┤
│              修复引擎（闭环）                         │
│  检测 → 修复 → 二次验证 → 标记                      │
├──────────────────────────────────────────────────────┤
│              通知策略（降噪）                         │
│  修复成功=静默  失败/反复=notify_qq.sh → QQ         │
├──────────────────────────────────────────────────────┤
│              daily-report (每日汇总 Markdown)         │
└──────────────────────────────────────────────────────┘
```

## 全部脚本清单

### v1 原有

| 脚本 | 频率 | 职责 |
|------|------|------|
| `watchdog.mjs` | 每分钟(cron) | PM2 进程存活 + 站点 HTTP 200 + Codex 心跳 |
| `db-guard.cjs` | 每分钟(cron) | DB 完整性 + WAL 检查 + 自动恢复 |
| `toc-guard.cjs` | 每小时(cron) | store 产品 TOC L2 完整性 + 自动重建 |
| `schedule-runner-cloud.cjs` | 每5分钟(cron) | 定时任务调度器（文章生成/发布） |
| `codex_fix.sh` | 手动 | 故障修复工具脚本 |

### v2 新增

| 脚本 | 频率 | 职责 |
|------|------|------|
| `daily-report.cjs` | 每日 23:55 | 读取3份cron日志，统计巡检/问题/修复/需人工，输出Markdown |
| `multi-site-guard.cjs` | 每5分钟 | 读 sites-config.json，HTTP GET + PM2 jlist 逐站检查 |
| `event-watcher.cjs` | 每分钟(--once) | 监控 PM2 进程变化/状态、磁盘>85%、内存>90% |
| `notify_qq.sh` | 事件触发 | 统一通知入口，读 QQ_BOT_TOKEN 环境变量，写 notify_queue.log |

### v1 通知 Shell

| 脚本 | 调用方 |
|------|--------|
| `watchdog_notify.sh` | cron → watchdog.mjs |
| `db_guard_notify.sh` | cron → db-guard.cjs |
| `toc_guard_notify.sh` | cron → toc-guard.cjs |

## 通知策略

| 级别 | 触发条件 | 通知方式 |
|------|----------|----------|
| 🔴 严重 | 站点挂了 / DB损坏 / 修复失败 / PM2进程消失 | 立即 notify_qq.sh |
| 🟡 警告 | 自动修复成功 / 磁盘>85% / 内存>90% | 仅写日志 |
| 🟢 正常 | 全部 OK | 静默 |

## 配置

### sites-config.json

多站点巡检配置文件（放在项目根目录）：

```json
[
  {
    "name": "AI电商站",
    "url": "https://ai.openai2000.cn",
    "pm2_name": "ai-ecom-site",
    "expect_status": 200
  },
  {
    "name": "汇智云码",
    "url": "https://www.openai2000.cn",
    "pm2_name": "huizhiyunma-api",
    "expect_status": 200
  }
]
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QQ_BOT_TOKEN` | QQ 机器人 API Token | 空（仅写队列） |
| `QQ_BOT_API_URL` | QQ API 地址 | `https://api.qqbot.example.com/send` |
| `QQ_BOT_TARGET` | QQ 通知目标（群/用户） | 空 |
| `NOTIFY_QUEUE` | 通知队列路径 | `$HOME/notify_queue.log` |
| `LOG_DIR` | 日志目录 | `/opt/ai-ecom-site/data/logs` |
| `PM2_BIN` | PM2 路径 | `/home/ubuntu/.nvm/versions/node/v22.23.0/bin/pm2` |
| `DISK_THRESHOLD` | 磁盘告警阈值(%) | 85 |
| `MEM_THRESHOLD` | 内存告警阈值(%) | 90 |
| `SITES_CONFIG` | 站点配置文件路径 | `../sites-config.json` |
| `TOC_GUARD_DB` | toc-guard 数据库路径 | `/opt/ai-ecom-site/data/site.db` |

## crontab 部署

```bash
# v1 原有
* * * * * bash /opt/ai-ecom-site/scripts/watchdog_notify.sh > /dev/null 2>&1
* * * * * bash /opt/ai-ecom-site/scripts/db_guard_notify.sh > /dev/null 2>&1
7 * * * * bash /opt/ai-ecom-site/scripts/toc_guard_notify.sh > /dev/null 2>&1
*/5 * * * * /usr/bin/node /opt/ai-ecom-site/scripts/schedule-runner-cloud.cjs >> /opt/ai-ecom-site/data/logs/schedule-runner-cloud-cron.log 2>&1

# v2 新增
*/5 * * * * /usr/bin/node /opt/ai-ecom-site/scripts/multi-site-guard.cjs --once >> /opt/ai-ecom-site/data/logs/multi-site-guard-cron.log 2>&1
* * * * * /usr/bin/node /opt/ai-ecom-site/scripts/event-watcher.cjs --once >> /opt/ai-ecom-site/data/logs/event-watcher-cron.log 2>&1
55 23 * * * /usr/bin/node /opt/ai-ecom-site/scripts/daily-report.cjs >> /opt/ai-ecom-site/data/logs/daily-report-cron.log 2>&1
```

## 退出码约定

| 脚本 | 0 | 1 | 2 |
|------|---|---|---|
| daily-report.cjs | 无需人工 | - | 有需人工处理项 |
| multi-site-guard.cjs | 全部正常 | 脚本错误 | 有站点异常 |
| event-watcher.cjs | 全部正常 | 脚本错误 | 有事件告警 |
| toc-guard.cjs | 全部正常 | 脚本错误 | 有修复 |
| db-guard.cjs | 正常 | - | - |

## 依赖

- Node.js >= 18（使用 `node:sqlite` / `node:https` / `node:os`）
- PM2
- bash
- 零 npm 依赖

## License

MIT
