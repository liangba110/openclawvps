# Open Auto v3 — 全自动运维方案

## 模块

| 模块 | 功能 | 频率 |
|------|------|------|
| predictive-guard.cjs | CPU/内存/磁盘趋势预测，提前6小时预警 | 每小时 |
| security-guard.cjs | nginx日志分析，自动封禁恶意IP，SSL检查 | 每5分钟 |
| heal-orchestrator.cjs | 站点健康检查→诊断→修复→回滚闭环 | 每3小时 |
| knowledge-base.cjs | 故障自动归档，相似匹配，LLM生成运维手册 | 每天02:00 |

## crontab

```
*/5 * * * * node /opt/ai-ecom-site/scripts/security-guard.cjs
0 * * * * node /opt/ai-ecom-site/scripts/predictive-guard.cjs
0 */3 * * * node /opt/ai-ecom-site/scripts/heal-orchestrator.cjs
0 2 * * * node /opt/ai-ecom-site/scripts/knowledge-base.cjs
```

## 退出码

- 0 = 正常
- 1 = 脚本异常
- 2 = 有告警/修复
