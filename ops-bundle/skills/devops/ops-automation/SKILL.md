---
name: ops-automation
description: 服务器运维自动化工具集 — opsctl CLI + Ops自治引擎 + 智能分析。触发：任何服务器运维操作（查状态/部署/查数据/看日志/备份/SSL/重启/搜索代码）。
---

# Ops 自动化运维

## 架构（完整版，12个模块）

```
Hermes(大脑,~2500 token/天)
  ├─ opsctl(22条CLI) ──── 一条完成常用操作
  ├─ engine(17规则YAML) ── 60秒自动检测+修复
  ├─ intelligence(5特性) ── EWMA基线/异常/预测/关联/调参
  ├─ brain(LLM决策) ──── MiMo API分析根因+修复方案
  ├─ devloop(开发闭环) ── 检测→工单→Hermes处理→修复→部署
  ├─ autopilot ──────── 扫描模式→生成新工具
  ├─ decision_engine ─── 知识库+因果链+推理诊断
  ├─ remote_ops ──────── SSH多服务器管理(A→B)
  ├─ log_analyzer ────── 模式识别+错误分类+趋势
  ├─ auto_fixer ──────── 6类检测+自动修复
  ├─ alerts ──────────── 实时QQ/微信/文件告警
  ├─ preventive ──────── 磁盘预测+SSL续签+服务预检
  └─ websearch ──────── GitHub/PyPI搜索(替代web_search)
```

### 闭环流程
```
问题发生 → engine检测(60s) → 能自动修复? → 是 → 自动修复 ✅
                                              ↓ 否
                                    devloop创建工单 → brain LLM分析
                                    → Hermes读取(cron 3min) → 用户确认 → 修复
```

铁律：所有运维操作先用 opsctl，不要手写命令。

# Web搜索（无需web_search工具）

## Codex CLI + MiMo（代码审查/修复）

```bash
# 配置（已持久化到~/.codex/config.toml）
export OPENAI_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
export OPENAI_API_KEY="tp-c2hcz66we5sd0xbpgeuqf0vjqvyq1ix2wsyvdpve7ktv2wj8"

# 代码审查
codex exec -m mimo-v2.5-pro --dangerously-bypass-approvals-and-sandbox "审查backend/app/user.py"

# 修复建议
codex exec -m mimo-v2.5-pro --dangerously-bypass-approvals-and-sandbox "MySQL Too many connections怎么修"

# 代码生成
codex exec -m mimo-v2.5-pro --dangerously-bypass-approvals-and-sandbox "用Python写hello world"
```

## 铁律（永久执行）

1. **遇到问题** → 查官方文档 → 查不到搜互联网 → 制定方案 → 确认 → 执行
2. **不确定的事** → 先验证再说，不凭经验猜
3. **API/SDK** → 先读文档+手动测试
4. **价格** → 先查用户套餐
5. **兼容性** → 先看官方文档+测试最小用例
6. **配置** → 先看源码schema+示例
7. **代码修改** → 先读完整文件+理解上下文
8. **禁止** → 自信说"不支持/做不到"，必须验证后再说

## Web搜索（无需web_search工具）

```bash
# GitHub仓库搜索
python3 /opt/ttdazi/ops/websearch.py github "python server monitor"

# GitHub代码搜索
python3 /opt/ttdazi/ops/websearch.py code "anomaly detection python"

# PyPI包搜索
python3 /opt/ttdazi/ops/websearch.py pypi "process manager"

# 综合搜索
python3 /opt/ttdazi/ops/websearch.py all "python ops automation"
```

## opsctl 命令速查（22条）

```bash
OPS="python3 /opt/ttdazi/ops/opsctl.py"

# ── 状态(8) ──
$OPS status                    # 全站状态总览
$OPS health                    # 健康检查(12项)
$OPS disk                      # 磁盘分析
$OPS service                   # 服务列表(6个)
$OPS cron                      # 定时任务列表
$OPS network                   # DNS+连通性
$OPS port                      # 端口占用
$OPS top 10                    # CPU Top进程

# ── 部署(1) ──
$OPS deploy ttdazi|ttdazi-backend|pay|aiweb

# ── 数据库(4) ──
$OPS query --user/--order/--money/--tables/--users-count
$OPS db / db size / db optimize

# ── 日志+安全(3) ──
$OPS logs errors ttdazi        # 错误扫描
$OPS error-hunter              # 全日志错误猎手
$OPS db-health                 # 数据库深度健康

# ── 自动扩展(2) ──
$OPS user-lookup <关键词>      # 用户完整画像

# ── 运维(4) ──
$OPS backup / backup clean / ssl / git
$OPS search/find/read/restart
```

## Autopilot（自动开发引擎）

Hermes调用此工具自动发现高频操作→生成新Python工具→扩展opsctl：

```bash
# 扫描操作模式
python3 /opt/ttdazi/ops/autopilot.py --report

# 生成新工具
python3 /opt/ttdazi/ops/autopilot.py --generate <tool_id>

# 安装到opsctl
python3 /opt/ttdazi/ops/autopilot.py --install <tool_id>
```

可用的自动工具模板：user_lookup, quick_deploy, error_hunter, db_health, backup_report, service_health, domain_check

## Ops 自治引擎

常驻systemd，每60秒扫描16条YAML规则，自动检测+自动修复。

```bash
# 查看引擎状态
python3 /opt/ttdazi/ops/engine.py --status

# 手动执行一次
python3 /opt/ttdazi/ops/engine.py

# 重启引擎
sudo systemctl restart ops-engine

# 查看升级队列（引擎处理不了需要Hermes介入的）
cat /opt/ttdazi/ops/state/escalation.json
```

### 规则文件（修改即生效，无需重启）

```
/opt/ttdazi/ops/rules/
├── services.yaml      # 服务守护（5个服务）
├── security.yaml      # 安全（SSH爆破/恶意进程/磁盘）
├── ssl.yaml           # SSL证书到期
├── database.yaml      # 数据库（连接数/碎片）
├── finance.yaml       # 资金异常
├── intelligence.yaml  # EWMA智能异常
└── preventive.yaml    # 预防性运维（磁盘/SSL/服务预检）
```

## 智能分析

```bash
# 综合报告（基线+异常+预测+关联）
python3 /opt/ttdazi/ops/intelligence.py --analyze

# 磁盘趋势预测
python3 /opt/ttdazi/ops/intelligence.py --predict

# 根因关联
python3 /opt/ttdazi/ops/intelligence.py --correlate

# 采集数据（cron每5分钟自动跑）
python3 /opt/ttdazi/ops/intelligence.py --collect
```

## GitHub仓库

完整代码+部署脚本+109个skills: `https://github.com/liangba110/ops-bundle`

```bash
# 任意服务器一键部署
git clone https://github.com/liangba110/ops-bundle.git
cd ops-bundle && bash deploy.sh

# Skills同步（每周日4:00自动）
bash /opt/ttdazi/ops/sync_skills.sh
```

## 标准工作流

### 用户问"平台怎样"
```bash
python3 /opt/ttdazi/ops/opsctl.py status
python3 /opt/ttdazi/ops/opsctl.py health
```

### 改代码后部署
```bash
python3 /opt/ttdazi/ops/opsctl.py deploy ttdazi
```

### 查业务数据
```bash
python3 /opt/ttdazi/ops/opsctl.py query --user <关键词>
python3 /opt/ttdazi/ops/opsctl.py query --order <状态>
```

### 排查问题
```bash
python3 /opt/ttdazi/ops/opsctl.py logs errors ttdazi
python3 /opt/ttdazi/ops/opsctl.py search "关键词"
```

### 处理引擎升级
```bash
cat /opt/ttdazi/ops/state/escalation.json  # 看升级原因
# 根据原因执行修复
python3 /opt/ttdazi/ops/opsctl.py restart <服务>
```

## 实时告警（alerts.py）

```bash
python3 /opt/ttdazi/ops/alerts.py send "⚠️ 磁盘80%" --level warn --channel all
python3 /opt/ttdazi/ops/alerts.py history 24   # 查告警历史
python3 /opt/ttdazi/ops/alerts.py stats        # 统计
python3 /opt/ttdazi/ops/alerts.py test         # 测试推送
```

渠道：console/file + QQ(escalation.json→Hermes) + 微信(wechat_queue.jsonl)
静默：同key冷却期不重复（info=60min, warn=30min, critical=10min, emergency=5min）

## 决策引擎（decision_engine.py）

```bash
python3 /opt/ttdazi/ops/decision_engine.py analyze    # 分析当前异常+推理诊断
python3 /opt/ttdazi/ops/decision_engine.py diagnose "症状描述"  # 诊断特定问题
python3 /opt/ttdazi/ops/decision_engine.py learn      # 从历史事件学习
```

原理：知识库(10种已知模式) + 因果链(3条链式分析) + 上下文收集(15项指标) → 综合建议
输出：每个问题给出根因+解决方案+是否可自动修复+置信度

## 多服务器管理（remote_ops.py）

```bash
python3 /opt/ttdazi/ops/remote_ops.py status B        # B服务器状态
python3 /opt/ttdazi/ops/remote_ops.py health B        # B服务器健康检查
python3 /opt/ttdazi/ops/remote_ops.py exec "命令" B   # 远程执行
python3 /opt/ttdazi/ops/remote_ops.py all-status      # 所有服务器状态
python3 /opt/ttdazi/ops/remote_ops.py sync <file>     # 同步文件到B
```

支持A(42.193.113.230)↔B(82.157.202.24)互操作

## 日志智能分析（log_analyzer.py）

```bash
python3 /opt/ttdazi/ops/log_analyzer.py scan          # 扫描所有日志(7个)
python3 /opt/ttdazi/ops/log_analyzer.py scan auth     # 扫描单个日志
python3 /opt/ttdazi/ops/log_analyzer.py trend 24      # 24小时错误趋势
python3 /opt/ttdazi/ops/log_analyzer.py pattern       # 识别重复模式
```

8种错误模式识别：崩溃/内存/磁盘/网络/认证/数据库/Web服务/SSL
自动分类+严重度+修复建议

## 自动修复（auto_fixer.py）

```bash
python3 /opt/ttdazi/ops/auto_fixer.py scan            # 扫描可修复问题
python3 /opt/ttdazi/ops/auto_fixer.py fix-all         # 修复所有可修复问题
python3 /opt/ttdazi/ops/auto_fixer.py fix <id>        # 修复指定问题
```

6类自动检测：Nginx配置/进程卡死/文件权限/僵尸进程/inode/SSL证书
每个问题给出：id+标题+严重度+修复命令+是否可自动修复

## 预防性运维（preventive.py）

```bash
python3 /opt/ttdazi/ops/preventive.py check    # 全面预检
python3 /opt/ttdazi/ops/preventive.py disk     # 磁盘预测+清理
python3 /opt/ttdazi/ops/preventive.py ssl      # SSL到期续签
python3 /opt/ttdazi/ops/preventive.py service  # 服务健康预检
```

预防动作：磁盘≥90%紧急清理 / ≥80%预防清理 / 预测30天撑满轻度清理 / SSL≤7天自动certbot续签 / 内存>85%基线告警 / 连接数>80%上限告警 / 僵尸进程检测

## GitHub同步（sync_skills.sh）

```bash
# 同步所有skills到GitHub（自动commit+push）
bash /opt/ttdazi/ops/sync_skills.sh

# 自定义commit消息
bash /opt/ttdazi/ops/sync_skills.sh "📝 自定义消息"

# Cron: 每周日4:00自动同步
```

GitHub仓库: `https://github.com/liangba110/ops-bundle`

## GitHub同步

```bash
# 手动同步
bash /opt/ttdazi/ops/sync_skills.sh

# 自定义消息
bash /opt/ttdazi/ops/sync_skills.sh "📝 描述"
```

**铁律：每次 session 结束前，运行 `bash /opt/ttdazi/ops/sync_skills.sh` 确保变更推送到 GitHub。**
Cron已配置每周日4:00自动同步。

GitHub: `https://github.com/liangba110/ops-bundle`

## 跨服务器部署

```bash
# A→B 部署
cd /opt/ttdazi && tar czf /tmp/ops-bundle.tar.gz --exclude='__pycache__' --exclude='*.pyc' --exclude='data/metrics.db' ops/
scp /tmp/ops-bundle.tar.gz ubuntu@82.157.202.24:/tmp/
ssh ubuntu@82.157.202.24 "cd /opt/ttdazi && sudo tar xzf /tmp/ops-bundle.tar.gz && bash ops/deploy.sh"
```

GitHub仓库: `git@github.com:liangba110/ops-bundle.git`

## 开发闭环（devloop.py）

引擎无法自动修复的问题 → 自动创建工单 → Hermes处理：

```bash
python3 /opt/ttdazi/ops/devloop.py ticket "错误描述"  # 创建工单
python3 /opt/ttdazi/ops/devloop.py status             # 查看工单队列
python3 /opt/ttdazi/ops/devloop.py context <id>       # 工单完整上下文(含LLM分析)
python3 /opt/ttdazi/ops/devloop.py done <id>          # 标记完成
python3 /opt/ttdazi/ops/devloop.py auto               # 引擎自动创建工单
```

### 工单分析流程（Cron自动执行）

1. `status` 检查open工单数量
2. `context <id>` 获取第一个open工单的完整上下文（含错误、文件、建议）
3. **验证历史修复**：如果类似工单已标记done，检查其result字段，然后验证实际状态（如MySQL变量）
4. 分析根因：检查相关文件（config.py, db.py等）、运行诊断命令
5. 给出修复方案，发送用户确认
6. 用户确认后执行修复
7. `done <id>` 标记完成

### MySQL连接数问题分析模板

```bash
# 1. 检查MySQL实际状态
mysql -u root -p'huizhiyun2026' -e "SHOW VARIABLES LIKE 'max_connections'; SHOW STATUS LIKE 'Threads_connected'; SHOW STATUS LIKE 'Max_used_connections';"

# 2. 检查应用代码中的连接管理
grep -n "get_connection\|conn.close" /opt/ttdazi/backend/db/__init__.py
grep -rn "get_connection" /opt/ttdazi/backend/app/ | head -20

# 3. 验证连接泄漏（每个get_connection必须有finally: conn.close()）
python3 -c "检查所有函数是否正确关闭连接"
```

## LLM决策引擎（brain.py）— 新增

```bash
python3 /opt/ttdazi/ops/brain.py decide "MySQL连接数150，CPU 95%"  # AI修复方案
python3 /opt/ttdazi/ops/brain.py analyze    # 系统状态分析
python3 /opt/ttdazi/ops/brain.py explain "错误日志内容"            # 错误解释+修复
```

调用MiMo API（`token-plan-cn.xiaomimimo.com`），返回JSON格式的修复命令+风险评估。
配置在`brain.py`的`API_CONFIG`中。换模型需改`base_url`/`api_key`/`model`。

## 开发Agent（dev_agent.py）

替代Codex CLI，用Python+MiMo直接做代码修改：

```bash
python3 /opt/ttdazi/ops/dev_agent.py fix "MySQL连接数过高"  # 自动修复
python3 /opt/ttdazi/ops/dev_agent.py review backend/app/config.py  # 代码审查
```

安全护栏：Git快照→文件白名单→语法检查→LLM审查→人工确认
详见 `references/dev-agent-safety.md`

## MySQL连接池优化（DBUtils）

当 pymysql 项目出现 "Too many connections" 或连接数持续增长时，核心问题是 `get_connection()` 每次创建新TCP连接且无池化。

### 诊断步骤

```bash
# 1. 检查MySQL实际状态
mysql -u root -p'密码' -e "SHOW VARIABLES LIKE 'max_connections'; SHOW STATUS LIKE 'Threads_connected'; SHOW STATUS LIKE 'Max_used_connections';"

# 2. 检查连接泄漏（get_connection调用数 vs conn.close调用数）
grep -c "get_connection" /path/to/backend/app/*.py    # 调用次数
grep -c "conn.close" /path/to/backend/app/*.py        # 关闭次数
# 差值 = 潜在泄漏数，每个泄漏的连接在进程退出前不会释放

# 3. 运行时提升max_connections（无需重启MySQL）
mysql -u root -p'密码' -e "SET GLOBAL max_connections = 300;"
```

### 修复模板（DBUtils PooledDB）

```python
# backend/db/__init__.py
from dbutils.pooled_db import PooledDB
import pymysql

_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=50,        # 池中最大连接数
            mincached=5,              # 最小空闲连接
            maxcached=20,             # 最大空闲连接
            blocking=True,            # 池满时阻塞等待
            ping=1,                   # 每次获取时ping检查
            host=MYSQL_HOST, port=MYSQL_PORT,
            user=MYSQL_USER, password=MYSQL_PASSWORD,
            database=MYSQL_DB, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
    return _pool

def get_connection():
    return _get_pool().connection()
```

安装：`pip3 install --break-system-packages DBUtils`（PEP 668 系统必须加 `--break-system-packages`）

### 关键参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| maxconnections | 50 | gunicorn workers × 25 每 worker |
| mincached | 5 | 启动时预建连接数 |
| maxcached | 20 | 空闲连接上限 |
| MySQL max_connections | 300 | 所有应用池上限之和 + 余量 |

## Codex CLI + MiMo 配置（已验证可用 ✅）

Codex CLI v0.150.1 **可以对接 MiMo Token Plan**，需要正确配置。

### 正确配置（~/.codex/config.toml）

```toml
model = "mimo-v2.5-pro"
model_provider = "mimo"
web_search = "disabled"
approval_policy = "never"

[model_providers.mimo]
name = "MiMo"
base_url = "https://token-plan-cn.xiaomimimo.com/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
```

### 环境变量

```bash
export OPENAI_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
export OPENAI_API_KEY="tp-c2hcz66we5sd0xbpgeuqf0vjqvyq1ix2wsyvdpve7ktv2wj8"
```

### 关键配置项

| 字段 | 值 | 必须原因 |
|---|---|---|
| `name` | "MiMo" | **必须有**，否则报 "provider name must not be empty" |
| `env_key` | "OPENAI_API_KEY" | **必须有**，否则API Key不附带→401 |
| `web_search` | "disabled" | **必须禁用**，MiMo不支持web_search tool→400 |
| `wire_api` | "responses" | MiMo支持Responses API格式 |

### 常见错误

| 错误 | 原因 | 修复 |
|---|---|---|
| `provider name must not be empty` | config缺少`name`字段 | 加`name = "MiMo"` |
| `401 Unauthorized` | 没设`env_key` | 加`env_key = "OPENAI_API_KEY"` |
| `web_search not supported` | 没禁用web_search | 加`web_search = "disabled"` |
| `Model metadata not found` | MiMo模型名不在Codex列表 | 正常警告，不影响使用 |

### 验证

```bash
codex exec -m mimo-v2.5-pro "输出hello world"
# 输出: hello world ✅

codex exec -m mimo-v2.5-pro "MySQL Too many connections怎么修"
# 输出: 详细6步修复方案 ✅
```

### 注意事项

- Codex用sandbox模式，文件读取受限。加`approval_policy = "never"`跳过确认
- MiMo是推理模型，`content`字段可能为空，实际在`reasoning_content`
- Codex的`web_search`功能必须禁用，MiMo不支持该tool type
- 配置文件路径：`~/.codex/config.toml`

## 每日健康报告（daily_health.py）

```bash
python3 /opt/ttdazi/ops/daily_health.py  # 生成系统+业务综合日报
```

Cron: 每日8:00自动推送到QQ。内容：服务状态+资源+SSL+备份+引擎告警。

## Codex集成到工单

devloop.py已集成Codex：工单处理时优先调用Codex CLI（更强大），失败回退dev_agent.py。

```bash
# Codex处理工单（自动）
# devloop.py会自动尝试：codex exec → 失败则 dev_agent.py fix
```

如需手动用Codex：
```bash
export OPENAI_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
export OPENAI_API_KEY="tp-c2hcz66we5sd0xbpgeuqf0vjqvyq1ix2wsyvdpve7ktv2wj8"
codex exec -m mimo-v2.5-pro --dangerously-bypass-approvals-and-sandbox "你的问题"
```

## 本Session关键发现

1. **Codex CLI 可以对接 MiMo** — 需要正确配置：`name`字段 + `env_key` + `web_search=disabled`。详见 `references/codex-cli-mimo-compatibility.md`
2. **MiMo支持Responses API** — Codex用`wire_api=responses`格式可以正常通信
3. **dev_agent.py代码审查有效** — 成功发现user.py中4个安全漏洞+3个性能问题
4. **工单系统打通** — engine→devloop→brain→Hermes→用户确认→修复
5. **GitHub同步铁律** — 每次session结束前sync_skills.sh
6. **web_search禁用必须在全局** — `web_search = "disabled"`放在config顶层，不在`[model_providers]`内

## 开发陷阱

**⚠️ 最高铁律：先查后说，不确定的事先验证再说**
1. **遇到问题先查官方文档** → 查不到搜互联网权威资料 → 制定方案 → 确认 → 执行
2. **禁止凭经验猜** — API兼容性/价格/配置格式，必须验证后再说
3. **教训**：2026-08-29 配置Codex时错误说"不支持MiMo"浪费1小时，说"API收费"实际已包月。根因是没查文档没测试就下结论。

1. **工单修复验证陷阱** — 引擎标记工单"done"时声称已修复（如"增加max_connections到300"），但实际可能未生效。分析新工单时必须先验证MySQL实际状态：
   ```bash
   mysql -u root -p'huizhiyun2026' -e "SHOW VARIABLES LIKE 'max_connections'; SHOW STATUS LIKE 'Threads_connected';"
   ```
   如果新工单与已"修复"工单相同错误，说明上次修复未实际执行。

2. **pymysql DictCursor信息表大写** — information_schema查询返回`TABLE_NAME`不是`table_name`，必须用alias: `SELECT TABLE_NAME as tname`
2. **表字段名差异** — money_log用`relate_id`不是`order_id`，withdraw用`companion_id`不是`user_id`，app_order用`create_time`不是`created_at`。写SQL前先`DESCRIBE table`
3. **CHECKERS字典顺序** — Python中`dict[key] = func`必须在func定义之后。把赋值放在`if __name__`之前、函数定义之后。engine.py曾因此报`NameError: name 'check_anomaly' is not defined`
4. **文件反复patch会损坏** — 多次patch同一个文件容易破坏结构（opsctl.py曾被patch到只剩131行）。超过3次patch时直接`write_file`重写整个文件
5. **opsctl日志记录** — 每次opsctl调用自动记录到`logs/ops_YYYY-MM-DD.jsonl`，供autopilot分析高频模式
6. **YAML规则check语义反转** — command类型检查中`value > threshold`时，`pass = not triggered`（条件满足=有问题=fail）。之前用`pass = triggered`导致0值误触发所有告警
7. **MiMo推理模型** — content字段始终为空，实际输出在reasoning_content。brain.py已适配：优先content，为空则用reasoning_content
8. **GitHub Token权限** — fine-grained token可能无repo创建权限，需用classic token或gh CLI auth
9. **函数重复定义** — 多次append代码到文件会导致同名函数重复（cmd_error_hunt出现3次）。安装autopilot生成的工具后需检查去重
10. **PEP 668 pip install 失败** — Ubuntu 24.04+ 的系统 Python 被标记 externally-managed，`pip3 install` 直接报错。必须用 `pip3 install --break-system-packages <包名>`。安装后验证：`/usr/bin/python3.12 -c "import <包名>; print('OK')"`（注意目标 Python 版本要匹配）。
11. **连接泄漏快速诊断** — pymysql 项目出现 "Too many connections" 时，先统计 `grep -c "get_connection" app/*.py` vs `grep -c "conn.close" app/*.py`。差值即潜在泄漏数。299调用/243关闭=56泄漏 是本次实战数据。每个泄漏连接在 gunicorn worker 退出前不会释放。→ 详见 `references/mysql-connection-pool-pattern.md`
12. **engine.py append代码陷阱** — `cat >> engine.py`追加的函数/CHKERS赋值如果在`if __name__`之后，运行时不会执行。新函数必须插入到main()之前、CHECKERS字典之后
11. **Brain LLM JSON解析** — MiMo返回的JSON可能不完整（reasoning_content中），需要逐字符匹配括号深度而非简单find('{')。devloop.py已用深度匹配修复
13. **MiMo Token Plan 计费** — 用户是 ¥99/月包月套餐，API调用不额外收费。不要报 ¥0.025/百万token 这个价格（那是别人的缓存价）。brain.py/dev_agent.py 每次调用成本 = ¥0
14. **cron job deliver='origin'** — 告警推送到当前QQ对话必须用`deliver='origin'`，不能用`deliver='local'`（后者不推送）
