---
name: ops-bundle
description: 服务器运维自动化完整包 — opsctl(22命令) + 自治引擎(15规则) + 智能分析(5特性) + 自动开发(autopilot)。一键部署到任意服务器。触发：部署运维工具、服务器自动化、opsctl安装。
---

# Ops Bundle — 完整运维自动化包

## 一键部署（B服务器）

```bash
# 在B服务器上执行（A服务器传文件过去）
scp -r /opt/ttdazi/ops/ ubuntu@82.157.202.24:/opt/ttdazi/ops/
ssh ubuntu@82.157.202.24 "bash /opt/ttdazi/ops/deploy.sh"
```

或本地部署：
```bash
bash /opt/ttdazi/ops/deploy.sh
```

## 架构

```
Hermes(大脑) → opsctl(22命令) → 引擎(15规则YAML) → 智能分析 → autopilot(自动开发)
```

## opsctl 命令（22条）

```bash
OPS="python3 /opt/ttdazi/ops/opsctl.py"

# 状态(8)
$OPS status          # 全站状态
$OPS health          # 健康检查(12项)
$OPS disk            # 磁盘分析
$OPS service         # 服务列表
$OPS cron            # 定时任务
$OPS network         # DNS+连通性
$OPS port            # 端口占用
$OPS top [N]         # CPU Top

# 部署(1)
$OPS deploy <project>  # ttdazi/ttdazi-backend/pay/aiweb

# 数据库(4)
$OPS query --user <kw>         # 查用户
$OPS query --order <status>    # 查订单
$OPS query --money [days]      # 资金流水
$OPS query --tables            # 表大小
$OPS db / db size / db optimize

# 日志+安全(3)
$OPS logs errors <svc>   # 错误扫描
$OPS error-hunter        # 全日志错误猎手
$OPS db-health           # 数据库深度健康

# 自动扩展(2)
$OPS user-lookup <kw>    # 用户完整画像

# 运维(4)
$OPS backup / backup clean / ssl / git "msg"
$OPS search / find / read / restart
```

## 自治引擎

```bash
# 状态
python3 /opt/ttdazi/ops/engine.py --status

# 手动执行
python3 /opt/ttdazi/ops/engine.py

# 重启
sudo systemctl restart ops-engine
```

### YAML规则（6文件15条）

| 文件 | 规则 |
|---|---|
| services.yaml | 后端/支付/AI/MySQL/Caddy 存活+自动重启 |
| security.yaml | SSH爆破封禁/恶意进程/磁盘清理 |
| ssl.yaml | 证书到期预警 |
| database.yaml | 连接数/碎片自动优化 |
| finance.yaml | 负余额/大额/重复订单 |
| intelligence.yaml | EWMA智能异常检测 |

规则修改即生效，无需重启引擎。

## 智能分析

```bash
python3 /opt/ttdazi/ops/intelligence.py --analyze    # 综合报告
python3 /opt/ttdazi/ops/intelligence.py --predict    # 磁盘预测
python3 /opt/ttdazi/ops/intelligence.py --correlate  # 根因关联
```

5个特性：EWMA基线 / z-score异常 / 线性回归预测 / 根因关联 / 自动调参

## Autopilot（自动开发）

```bash
python3 /opt/ttdazi/ops/autopilot.py --report     # 扫描+建议
python3 /opt/ttdazi/ops/autopilot.py --generate <id>  # 生成工具
python3 /opt/ttdazi/ops/autopilot.py --install <id>   # 安装到opsctl
```

7个工具模板：user_lookup, quick_deploy, error_hunter, db_health, backup_report, service_health, domain_check

## 文件结构

```
/opt/ttdazi/ops/
├── opsctl.py           # CLI工具(22命令)
├── engine.py           # 自治引擎
├── intelligence.py     # 智能分析
├── autopilot.py        # 自动开发
├── deploy.sh           # 一键部署脚本
├── rules/              # YAML规则
│   ├── services.yaml
│   ├── security.yaml
│   ├── ssl.yaml
│   ├── database.yaml
│   ├── finance.yaml
│   └── intelligence.yaml
├── data/               # 学习数据(SQLite+JSON)
├── state/              # 运行状态
├── auto_tools/         # 自动生成的工具
└── logs/               # 执行日志
```

## 依赖

- Python 3.10+
- numpy (可选，智能分析用)
- pymysql (数据库查询用)
- pyyaml (规则解析用)
- mysql client
- openssl, curl, dig

安装：`pip3 install numpy pymysql pyyaml`
