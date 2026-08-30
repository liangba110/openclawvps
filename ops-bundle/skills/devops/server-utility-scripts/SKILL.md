---
name: server-utility-scripts
description: 轻量Python运维脚本开发模式。覆盖：日常监控/探活/日报/清理/巡检脚本编写，crontab集成，MySQL跨库查询陷阱，零依赖纯Python实现。触发：写运维脚本、cron自动化、服务器日常巡检、磁盘清理、站点探活、运营日报。⚠️ 新项目优先用ops-automation skill（包含完整的opsctl+engine+brain+devloop体系），本skill仅用于写独立的轻量脚本或理解底层脚本模式。
---

# 服务器轻量 Python 运维脚本开发

## 核心原则
- **零外部依赖**：只用 pymysql + 标准库（ssl/socket/subprocess/json/os/glob）
- **纯只读优先**：监控/探活/统计类脚本只读不写数据库；清理类脚本有明确的删除规则
- **crontab 集成**：脚本通过 crontab 定时执行，输出到 `/var/log/`，异常时输出告警
- **静默模式**：正常时输出一行确认；异常时才输出详细告警
- **每次执行<1秒**：不消耗算力，不影响业务服务

## 脚本模板结构

```python
#!/usr/bin/env python3
"""脚本用途说明"""
import sys
sys.path.insert(0, '/opt/ttdazi/backend')
sys.path.insert(0, '/home/ubuntu/.local/lib/python3.12/site-packages')

try:
    from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
except ImportError:
    sys.path.insert(0, '/opt/ttdazi/backend/app')
    from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

import pymysql

def main():
    conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
        password=MYSQL_PASSWORD, database=MYSQL_DB,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cur:
            cur.execute("...")
            result = cur.fetchall()
    finally:
        conn.close()
    # 输出结果

if __name__ == '__main__':
    main()
```

## 常见脚本类型

| 类型 | 频率 | 功能 |
|---|---|---|
| daily_report.py | 每日8:00 | 运营日报（用户/订单/资金/评价/异常检测） |
| site_uptime.py | 每30分钟 | HTTP探活 + SSL证书到期预警 |
| log_cleanup.py | 每周日 | 清理过期备份/日志/tmp/binlog |
| money_anomaly.py | 每日 | 资金异常检测（大额/频繁提现/余额负数） |
| db_health.py | 每日 | MySQL健康巡检（慢查询/表碎片/连接数） |

## Crontab 配置规范

```bash
# 格式：分 时 日 月 命令 >> 日志 2>&1
0 8 * * * python3 /opt/ttdazi/scripts/daily_report.py >> /var/log/daily_report.log 2>&1
*/30 * * * * python3 /opt/ttdazi/scripts/site_uptime.py >> /var/log/site_uptime.log 2>&1
0 4 * * 0 python3 /opt/ttdazi/scripts/log_cleanup.py >> /var/log/log_cleanup.log 2>&1
```

追加到现有 crontab 时用 `crontab -l | cat - new_entries | crontab -`，不要覆盖。

## ⚠️ 跨库查询 MySQL 字段名陷阱

Server A 上多个数据库字段命名不一致，**写查询前必须 DESCRIBE 表**。详见 📖 `references/mysql-schema-pitfalls.md`

## SSL 证书检查（零依赖）

```python
import ssl, socket
from datetime import datetime

ctx = ssl.create_default_context()
with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
    s.settimeout(5)
    s.connect((host, 443))
    cert = s.getpeercert()
    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
    days_left = (not_after - datetime.now()).days
```

## HTTP 探活（curl方式）

```python
import subprocess
cmd = ['curl', '-sk', '-o', '/dev/null', '-w', '%{http_code} %{time_total}',
       '--max-time', '10', '-A', 'Mozilla/5.0 (compatible; UptimeBot/1.0)', url]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
# 正常=200, 301/302重定向也算正常
```

注意：不要对本机域名用 `--resolve` 强制 IP（Caddy/TLS 可能不匹配），直接用 DNS 解析即可。

## 磁盘清理模式

```python
def cleanup_pattern(pattern, retention_days, label):
    cutoff = time.time() - retention_days * 86400
    cleaned, freed = 0, 0
    for path in sorted(glob.glob(pattern)):
        if os.path.getmtime(path) < cutoff:
            size = os.path.getsize(path) if os.path.isfile(path) else dir_size(path)
            os.remove(path) if os.path.isfile(path) else shutil.rmtree(path)
            cleaned += 1; freed += size
    return cleaned, freed
```

## JSON 输出约定（供 Hermes 解析决策）

脚本应输出 JSON 格式，Hermes 解析后决策。退出码语义：0=正常 1=有告警 2=严重

```python
import json, sys
result = {
    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'status': 'ok',  # ok / warn / error
    'alerts': [],     # 需要关注的问题列表
    'checks': [],     # 各项检查结果
    'summary': {}     # 摘要数据
}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if result['status'] == 'ok' else (2 if result['status'] == 'error' else 1))
```

## "Python 执行 + Hermes 调度" 架构

核心分层：
- **Python 脚本层**（苦力）：纯执行，不决策，输出 JSON，零 token 消耗
- **Hermes 调度层**（大脑）：cron 调用脚本 → 读 stdout → 分析 → 决策/通知
- **升级机制**：脚本检测到问题只报告，修复由 Hermes 或通知用户

日均 token 对比：旧方案 ~75,000 → 新方案 ~2,500（节省 97%）

## YAML 规则驱动自治引擎

当脚本数量 >5 个时，升级为 YAML 规则引擎（`/opt/ttdazi/ops/`）：

```yaml
# rules/services.yaml 示例
- name: 后端存活
  check:
    type: http
    url: http://127.0.0.1:5002/api/health
    timeout: 5
  actions:
    - type: restart_systemd
      service: ttdazi
      cooldown: 300      # 5分钟内不重复
      max_retries: 3     # 最多重启3次
      on_failure: escalate  # 3次失败→通知Hermes
    - type: notify
      message: "🔄 {service}已重启"
```

引擎特性：Check 类型（http/command/systemd/disk_usage/ssl/anomaly）+ Action 类型（restart/cleanup/block_ip/optimize_db/notify）

systemd 常驻：`/etc/systemd/system/ops-engine.service`

## 智能分析层（intelligence.py）

5 个智能特性，纯 numpy + 标准库，零外部 ML 依赖：

| 特性 | 原理 | 用途 |
|---|---|---|
| EWMA 自学习基线 | 指数加权移动平均 | 自动学习"正常"CPU/内存/连接数范围 |
| z-score 异常检测 | 偏离基线 >2.5σ 才告警 | 避免固定阈值误报 |
| 线性回归预测 | 最小二乘法拟合趋势 | 预测"N天后磁盘满" |
| 根因关联 | 5分钟窗口多事件聚类 | "MySQL挂+后端挂→MySQL故障" |
| 自动调参 | 基线动态调整 YAML 阈值 | 连接数阈值随负载浮动 |

数据采集 cron：`*/5 * * * * python3 /opt/ttdazi/ops/intelligence.py --collect`

## 通知集成

日报等统计脚本可写入 `notifications` 表（user_id=1 为管理员），管理后台可展示：
```python
cur.execute("INSERT INTO notifications (user_id, title, content, type) VALUES (1, %s, %s, 'daily_report')", (title, content))
```

## 文件位置规范

- 脚本统一放 `/opt/ttdazi/scripts/`
- 引擎放 `/opt/ttdazi/ops/`（engine.py + rules/ + state/ + logs/）
- 日志放 `/var/log/<脚本名>.log`
- JSON 历史数据放 `/var/log/<脚本名>.json` 或 `/opt/ttdazi/ops/data/`
- 权限 `chmod +x` 脚本文件

## 模板与参考

- 📖 `templates/ops-engine.py` — 完整自治引擎模板（复制即用）
- 📖 `templates/ops-rules.yaml` — YAML规则模板示例
- 📖 `references/intelligence-patterns.md` — EWMA/异常检测/趋势预测代码模式
- 📖 `references/mysql-schema-pitfalls.md` — 跨库字段名陷阱
