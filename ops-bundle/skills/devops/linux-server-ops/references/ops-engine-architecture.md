# Ops自治引擎架构参考

## 设计原则
1. **Python做苦力，Hermes做大脑** — routine操作0 token，只在升级时消耗token
2. **YAML声明规则** — 新增规则只需加文件，无需重启引擎
3. **反转check逻辑** — 条件满足=有问题(fail)，不满足=正常(pass)
4. **冷却+重试** — 防重复触发，max_retries后升级

## Check类型

### http
```yaml
check:
  type: http
  url: http://127.0.0.1:5002/api/health
  timeout: 5
  expected_code: 200
```

### command（反转逻辑）
```yaml
check:
  type: command
  cmd: "grep 'Failed password' /var/log/auth.log | wc -l"
  threshold: 50    # >=50 就告警
  operator: ">="   # 反转：满足=fail，不满足=pass
```

### systemd
```yaml
check:
  type: systemd
  service: mysql
```

### disk_usage
```yaml
check:
  type: disk_usage
  paths: ["/", "/data/disk"]
  warn_threshold: 80
  critical_threshold: 90
```

### ssl
```yaml
check:
  type: ssl
  hosts: [www.ttdazi.xyz, pay.openai2000.cn]
  warn_days: 14
```

## Action类型

### restart_systemd
```yaml
- type: restart_systemd
  service: ttdazi
  cooldown: 300        # 5分钟内不重复
  max_retries: 3       # 最多重试3次
  on_failure: escalate # 3次失败→升级给Hermes
```

### cleanup
```yaml
- type: cleanup
  targets:
    - pattern: "/data/disk/daily_*"
      keep_days: 15
    - pattern: "/var/log/*.log"
      keep_days: 30
  when: ">= 80%"      # 磁盘>=80%时才清理
  cooldown: 3600
```

### block_ip_top
```yaml
- type: block_ip_top
  count: 10           # 封禁Top 10个IP
  duration: 3600
  cooldown: 1800
```

### optimize_db
```yaml
- type: optimize_db
  database: huizhiyun
  tables: [money_log]
  cooldown: 86400     # 每天最多优化一次
```

### notify（升级给Hermes）
```yaml
- type: notify
  severity: critical
  message: "🚨 {detail}"
  when: on_fail       # 只在检查失败时通知
```

## 升级机制
Python无法处理的问题写入 `state/escalation.json`：
```json
{
  "pending": [
    {
      "timestamp": "2026-08-29T02:11:02",
      "severity": "critical",
      "message": "🔒 SSL证书将在7天到期！"
    }
  ]
}
```
Hermes cron读取此文件，有pending项则通知用户。

## 状态文件
- `state/counters.json` — 规则触发计数+冷却追踪
- `state/escalation.json` — 待处理告警队列
- `logs/summary_*.json` — 每次执行摘要（保留50个）
- `logs/YYYY-MM-DD.jsonl` — 事件日志

## 扩展新规则
1. 在 `rules/` 下新建或编辑 `.yaml` 文件
2. 引擎每周期自动加载（无需重启）
3. 测试：`python3 /opt/ttdazi/ops/engine.py --rule 新规则.yaml`
4. 验证通过后加入常驻规则集
