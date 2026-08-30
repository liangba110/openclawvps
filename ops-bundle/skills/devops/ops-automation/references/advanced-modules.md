# 高级运维模块 API 参考

## decision_engine.py

### 知识库结构
```json
{
  "patterns": [
    {
      "symptoms": ["HTTP 502", "服务无响应"],
      "cause": "服务进程崩溃",
      "solution": "systemctl restart <service>",
      "auto_fix": true,
      "confidence": 0.9
    }
  ],
  "causal_chains": [
    {
      "trigger": "MySQL宕机",
      "effects": ["后端502", "支付失败"],
      "root_cause_candidates": ["磁盘满", "内存不足"],
      "priority": "critical"
    }
  ]
}
```

### 诊断流程
1. collect_context() → 收集15项系统指标
2. diagnose(symptom) → 匹配知识库模式
3. analyze_causal_chains() → 因果链分析
4. generate_recommendation() → 输出修复建议

## remote_ops.py

### SSH执行
```python
from remote_ops import ssh_exec, cmd_status, cmd_health
out, code = ssh_exec('82.157.202.24', 'systemctl status nginx', user='ubuntu')
result = cmd_status('B')  # B服务器完整状态
result = cmd_health('B')  # B服务器健康检查
```

### 服务器配置
```python
SERVERS = {
    'A': {'host': '42.193.113.230', 'user': 'root'},
    'B': {'host': '82.157.202.24', 'user': 'ubuntu'},
}
```

## log_analyzer.py

### 错误模式库
| 类型 | 严重度 | 自动修复 |
|---|---|---|
| crash | critical | restart_service |
| memory | critical | kill_process |
| disk | critical | cleanup |
| network | warn | — |
| auth | warn | block_ip |
| mysql | warn | optimize_db |
| nginx | warn | restart_service |
| ssl | warn | renew_cert |

## auto_fixer.py

### 检测器列表
1. check_nginx_config() — Nginx语法
2. check_service_stuck() — CPU 100%进程
3. check_file_permissions() — 关键文件权限
4. check_zombie_processes() — 僵尸进程
5. check_disk_inodes() — inode使用率
6. check_ssl_cert_files() — SSL证书文件
