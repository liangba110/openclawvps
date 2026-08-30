# MySQL Schema 陷阱 — Server A 特定

## information_schema 大写列名

pymysql DictCursor 查询 information_schema 时返回**大写**列名：

```python
# ❌ 错误 — KeyError: 'table_name'
cur.execute("SELECT table_name, data_length FROM information_schema.tables ...")
row['table_name']  # KeyError!

# ✅ 正确 — 用别名
cur.execute("SELECT TABLE_NAME as tname, DATA_LENGTH as dlen FROM information_schema.tables ...")
row['tname']  # OK
```

同样适用于 `DATA_FREE`, `INDEX_LENGTH`, `TABLE_ROWS` 等列。

## huizhiyun 库表结构

### money_log（无 order_id）
```sql
-- ❌ WHERE ml.order_id = ...
-- ✅ WHERE ml.relate_id = ...
-- relate_id 关联 orders.id 或 companion.id（按 type 区分）
```

### withdraw（无 user_id）
```sql
-- ❌ SELECT user_id FROM withdraw
-- ✅ JOIN companion 取 user_id
SELECT w.companion_id, c.user_id, w.amount 
FROM withdraw w JOIN companion c ON c.id = w.companion_id
WHERE w.status IN (0, 1)
```

### orders.status 值
- 0=待支付, 1=待确认(进行中), 2=已完成, 3=已取消, 4=退款

## software_auth 库表结构

### app_order（用 create_time）
```sql
-- ❌ WHERE DATE(created_at) = ...
-- ✅ WHERE DATE(create_time) = ...
```

### app_user（用 vip_expire_time）
```sql
-- ❌ WHERE vip_expire > NOW()
-- ✅ WHERE vip_expire_time > NOW()
```

## money_log.type 值与收支方向

| type | 方向 | 说明 |
|---|---|---|
| recharge | + | 充值 |
| order_income | + | 订单收入(平台) |
| admin_adjust | + | 管理员调整 |
| test_log | + | 测试 |
| order_settle | - | 订单结算(达人) |
| withdraw_request | - | 提现申请 |

**计算用户净值**：
```sql
SUM(CASE WHEN type IN ('recharge','order_income','admin_adjust','test_log') THEN amount
         WHEN type IN ('withdraw_request','order_settle') THEN -amount
         ELSE 0 END) as net
```
