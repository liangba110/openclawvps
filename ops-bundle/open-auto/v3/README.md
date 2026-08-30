# Open Auto v3 - 预测性维护与安全自愈

## 概述

v3 在 v2 基础上新增 4 个核心模块，实现预测性维护、安全自愈、统一编排和知识库管理。

## 模块列表

### 1. predictive-guard.cjs - 预测性维护

**功能：** 系统资源指标采集、线性回归趋势预测、告警

```bash
# 采集指标
node v3/predictive-guard.cjs collect

# 生成报告
node v3/predictive-guard.cjs report

# 预测指标
node v3/predictive-guard.cjs predict diskPercent 24
```

**指标：** 磁盘、内存、CPU、负载、Inode、进程数

**阈值：** 磁盘 75%/85%、内存 80%/90%、CPU 70%/90%

### 2. security-guard.cjs - 安全自愈

**功能：** SSH暴力破解检测、自动封禁IP、过期清理

```bash
# 扫描并自动封禁
node v3/security-guard.cjs scan

# 查看安全报告
node v3/security-guard.cjs report

# 手动封禁/解封
node v3/security-guard.cjs block 1.2.3.4 "恶意扫描"
node v3/security-guard.cjs unblock 1.2.3.4

# 查看封禁列表
node v3/security-guard.cjs list
```

**阈值：** SSH失败 5次/分钟、20次/小时，封禁 24小时

### 3. heal-orchestrator.cjs - 修复编排引擎

**功能：** 统一事件总线、闭环修复、冷却期防重复

```bash
# 执行修复
node v3/heal-orchestrator.cjs run

# 试运行（不实际执行）
node v3/heal-orchestrator.cjs run --dry-run

# 查看报告
node v3/heal-orchestrator.cjs report

# 查看事件历史
node v3/heal-orchestrator.cjs events
```

**内置规则：** 磁盘清理、内存释放、Nginx重启、PM2重启

### 4. knowledge-base.cjs - 知识库

**功能：** 故障案例归档、运维手册生成、案例搜索

```bash
# 初始化（添加预置案例）
node v3/knowledge-base.cjs init

# 添加案例
node v3/knowledge-base.cjs add "网站502" "Nginx"

# 搜索案例
node v3/knowledge-base.cjs search "磁盘"

# 生成运维手册
node v3/knowledge-base.cjs runbook

# 查看报告
node v3/knowledge-base.cjs report
```

## 集成定时任务

```bash
# 每小时采集指标
0 * * * * node /opt/ai-ecom-site/scripts/v3/predictive-guard.cjs collect

# 每10分钟安全扫描
*/10 * * * * node /opt/ai-ecom-site/scripts/v3/security-guard.cjs scan

# 每2小时执行修复
0 */2 * * * node /opt/ai-ecom-site/scripts/v3/heal-orchestrator.cjs run
```

## 架构

```
v3/
├── predictive-guard.cjs  # 指标采集+趋势预测
├── security-guard.cjs    # 安全自愈
├── heal-orchestrator.cjs # 修复编排
├── knowledge-base.cjs    # 知识库
└── README.md
```

## 依赖

- Node.js >= 18
- 零第三方依赖（仅用 node 内置模块）
- sudo 权限（iptables/系统管理）
