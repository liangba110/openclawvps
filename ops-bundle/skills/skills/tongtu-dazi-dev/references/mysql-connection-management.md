# MySQL 连接管理陷阱与最佳实践

## 问题模式：连接泄漏与max_connections上限

### 典型症状
```
pymysql.err.OperationalError: (1042, 'Too many connections')
MySQL连接数达到max_connections上限
```

### 根因分析

#### 1. 无连接池（当前项目情况）
`/opt/ttdazi/backend/db/__init__.py` 中的 `get_connection()` 每次调用都创建新连接：
```python
def get_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
```

**问题**：每个API请求都创建新连接，高并发时连接数快速累积。

#### 2. 连接泄漏（代码缺陷）
如果 `conn.close()` 未在 `finally` 块中调用，异常时连接不会释放。

### 诊断步骤

```bash
# 1. 检查MySQL实际状态
mysql -u root -p'huizhiyun2026' -e "SHOW VARIABLES LIKE 'max_connections';"
mysql -u root -p'huizhiyun2026' -e "SHOW STATUS LIKE 'Threads_connected';"
mysql -u root -p'huizhiyun2026' -e "SHOW STATUS LIKE 'Max_used_connections';"

# 2. 检查应用代码中的连接管理
grep -n "get_connection\|conn.close" /opt/ttdazi/backend/db/__init__.py
grep -rn "get_connection" /opt/ttdazi/backend/app/ | head -20

# 3. 验证连接泄漏（每个get_connection必须有finally: conn.close()）
cd /opt/ttdazi/backend && python3 -c "
import os
for root, dirs, files in os.walk('app'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path) as fh:
                content = fh.read()
            if 'get_connection' not in content:
                continue
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'conn = get_connection()' in line:
                    # 检查后续是否有close
                    found_close = False
                    for j in range(i+1, min(i+50, len(lines))):
                        if 'conn.close()' in lines[j]:
                            found_close = True
                            break
                    if not found_close:
                        print(f'{path}:{i+1} - 可能的连接泄漏')
"
```

### 修复方案

#### 方案1：快速修复（提高max_connections）
```bash
# 修改MySQL配置
sudo sed -i 's/# max_connections\s*=\s*151/max_connections = 300/' /etc/mysql/mysql.conf.d/mysqld.cnf
sudo systemctl restart mysql

# 验证
mysql -u root -p'huizhiyun2026' -e "SHOW VARIABLES LIKE 'max_connections';"
```

#### 方案2：长期优化（引入连接池）
需要修改 `db/__init__.py`，使用连接池：
```python
from dbutils.pooled_db import PooledDB
import pymysql

pool = PooledDB(
    creator=pymysql,
    maxconnections=20,
    mincached=2,
    maxcached=10,
    blocking=True,
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB,
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

def get_connection():
    return pool.connection()
```

### 验证修复

```bash
# 1. 检查MySQL配置已生效
mysql -u root -p'huizhiyun2026' -e "SHOW VARIABLES LIKE 'max_connections';"
# 应显示 300

# 2. 重启应用服务
sudo systemctl restart ttdazi

# 3. 压力测试（可选）
# ab -n 1000 -c 50 http://127.0.0.1:5002/api/health

# 4. 监控连接数
watch -n 5 'mysql -u root -p"huizhiyun2026" -e "SHOW STATUS LIKE '\''Threads_connected'\'';"'
```

## 开发陷阱

### 1. 修复未实际生效
引擎标记工单"done"时声称已修复（如"增加max_connections到300"），但实际可能未执行。
**必须验证MySQL实际状态**，不能只看工单result字段。

### 2. 连接泄漏隐蔽性
函数有 `try` 但没有 `finally: conn.close()` 是最常见的泄漏模式。
Python不会自动关闭未释放的数据库连接。

### 3. PyMySQL默认不自动提交
```python
conn = get_connection()
with conn.cursor() as cur:
    cur.execute("INSERT ...")
# 必须显式调用
conn.commit()  # 不调用则数据不保存
```

## 相关文件
- `/opt/ttdazi/backend/db/__init__.py` - 连接管理核心
- `/opt/ttdazi/backend/config.py` - MySQL配置
- `/etc/mysql/mysql.conf.d/mysqld.cnf` - MySQL服务端配置
