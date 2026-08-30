# DB 种子数据注入模式

当前端页面需要展示内容但后端 API 不支持创建（如需求发布接口已关闭）时，直接通过 Python 脚本向 MySQL 插入数据。

## 场景
- 需求大厅需要展示需求，但 `POST /api/demand/create` 已返回 `"发布功能已关闭"`
- 同城达人列表需要丰富内容，但无批量导入后台

## 流程

### 1. 分析表结构
```python
# 先用脚本查看表结构
from db import get_connection
conn = get_connection()
with conn.cursor() as cur:
    cur.execute('DESCRIBE demand_order')
    for r in cur.fetchall(): print(r)
conn.close()
```

### 2. 检查外键关联
确认 user 表中有可用用户，companion 表中有关联记录。

### 3. 编写种子脚本
```python
#!/usr/bin/env python3
"""种子数据脚本"""
import sys
sys.path.insert(0, '/opt/ttdazi/backend')
from db import get_connection
from datetime import datetime

conn = get_connection()

# 数据列表
seeds = [
    ('标题', game_id, '描述', '时长', 价格),
]

with conn.cursor() as cur:
    for title, game_id, desc, duration, price in seeds:
        # 随机选择发布者
        cur.execute("SELECT id FROM user WHERE ... ORDER BY RAND() LIMIT 1")
        user = cur.fetchone()
        cur.execute("""
            INSERT INTO demand_order (user_id, game_id, title, description, duration, price, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
        """, (user['id'], game_id, title, desc, duration, price, datetime.now()))

conn.commit()
conn.close()
```

### 4. 记住 conn.commit()
PyMySQL 默认不自动提交，必须显式调用 `conn.commit()`。

### 5. 验证
```bash
curl -s "http://127.0.0.1:5002/api/demand/list" | python3.12 -c "import sys,json;d=json.load(sys.stdin);print(f'共 {d[\"data\"][\"total\"]} 条')"
```

## 陷阱

### 用户名或电话必须唯一
`user` 表的 `phone` 字段有 UNIQUE 索引。种子用户手机号不可重复。建议用 `13900000XXX` 范围。

### status 必须匹配 API 过滤条件
- `demand_order` 列表接口只返回 `status=0` 的需求
- `companion` 列表需要 `status=1` + `is_online=1`

### PyMySQL % 转义
SQL 中写 `'95%'` 时 `%` 会被 Python 的 `%` 格式化解析为占位符：
```python
# ❌ 错误
"VALUES ('95%', %s)"   # %' 被解释为格式符
# ✅ 正确
"VALUES ('95%%', %s)"  # %% 转义为字面 %
```

### 日期范围
检查 `expires_at` / `expires_at_travel` 等过期字段。列表查询会过滤过期记录，种子数据必须设置未来时间：
```python
from datetime import datetime, timedelta
expires = datetime.now() + timedelta(days=365)
```
