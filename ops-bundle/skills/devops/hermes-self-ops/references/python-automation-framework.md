# Python 运维自动化框架参考

## 脚本标准模板

```python
#!/usr/bin/env python3
"""脚本描述 — cron: 0 8 * * * python3 /path/to/script.py > /var/log/script.log 2>&1"""
import sys, os, json
from datetime import datetime

def main():
    result = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'ok',  # ok / warn / error
        'alerts': [],     # 需要Hermes/用户关注的问题
        'checks': [],     # 逐项检测结果
        'summary': {}     # 汇总数据
    }
    
    # ... 检测逻辑 ...
    
    # 输出JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 退出码
    if result['status'] == 'error': sys.exit(2)
    elif result['status'] == 'warn': sys.exit(1)
    else: sys.exit(0)

if __name__ == '__main__':
    main()
```

## 数据库连接模板

```python
import sys
sys.path.insert(0, '/opt/ttdazi/backend')
sys.path.insert(0, '/home/ubuntu/.local/lib/python3.12/site-packages')

try:
    from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
except ImportError:
    sys.path.insert(0, '/opt/ttdazi/backend/app')
    from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

import pymysql

conn = pymysql.connect(
    host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
    password=MYSQL_PASSWORD, database=MYSQL_DB,
    charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
)
```

## Hermes Cron 配置

用 `no_agent=false`（LLM驱动），script 指向 Python 脚本，stdout JSON 注入 prompt：
```
cronjob action=create schedule="0 8 * * *" 
  prompt="读取脚本输出，分析JSON中的status/alerts/checks，如有异常通知用户"
  script="~/.hermes/scripts/finance_reconcile.py"
```

## 告警阈值参考

| 检查项 | warn | error |
|---|---|---|
| 资金差异 | 任何不一致 | ≥3项不一致 |
| 站点HTTP | 响应>3s | HTTP 5xx/超时 |
| SSL证书 | ≤14天到期 | ≤3天或检查失败 |
| 磁盘使用 | ≥85% | ≥90% |
| SSH爆破 | ≥100次/天 | fail2ban未运行 |
| 连接数 | ≥80% | ≥95% |
| 负余额 | 任何 | — |
| 服务宕机 | — | 重启后仍不可用 |
