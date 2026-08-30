# MySQL 跨库字段名陷阱

## 核心教训
**写跨库 SQL 前必须 `DESCRIBE 表名` 确认字段**。不同数据库/表的同义字段命名可能完全不同。

## huizhiyun 库（同途搭子）

| 表 | 常用字段 | 备注 |
|---|---|---|
| orders | `created_at`, `updated_at` | 标准 datetime |
| companion | `created_at`, `expires_at`, `is_online` | |
| user | `created_at` | |
| money_log | `created_at`, `type`, `amount` | type: recharge/withdraw_request/order_settle/order_income/admin_adjust |
| review | `created_at`, `rating` | |
| complaint | `created_at` | |
| violation_log | `created_at` | |
| notifications | `user_id`, `title`, `content`, `type`, `created_at` | user_id=1 为管理员 |
| site_config | — | 提现规则/手续费等配置 |

## software_auth 库（软件授权）

| 表 | 字段 | 与 huizhiyun 差异 |
|---|---|---|
| app_order | `create_time`（非 created_at）, `order_sn`, `amount`, `status` | ⚠️ 用 `create_time` 不是 `created_at` |
| app_user | `vip_expire_time`（非 vip_expire）, `username`（非 user_id）, `create_time` | ⚠️ 无 user_id 字段，用 username 区分用户 |
| app | `app_id`, `app_name` | |
| recharge_order | `create_time` | |

## 查询示例（已验证正确）

```sql
-- 软件授权昨日订单
SELECT COUNT(*) as cnt FROM software_auth.app_order WHERE DATE(create_time) = '2026-08-28'

-- 软件授权有效VIP用户数
SELECT COUNT(*) as c FROM software_auth.app_user WHERE vip_expire_time > NOW()

-- 搭子到期提醒
SELECT u.id, c.expires_at FROM companion c
JOIN user u ON u.id = c.user_id
WHERE c.expires_at <= DATE_ADD(NOW(), INTERVAL 3 DAY) AND c.is_online = 1

-- 资金异常：同日多次提现
SELECT user_id, COUNT(*) as cnt FROM money_log
WHERE type='withdraw_request' AND DATE(created_at) = CURDATE()
GROUP BY user_id HAVING cnt >= 3
```

## pymysql DictCursor + information_schema 字段名大小写

**pymysql DictCursor 查询 information_schema 时返回大写字段名**（`TABLE_NAME` 不是 `table_name`）。必须用别名统一为小写：

```sql
-- ❌ 错误：DictCursor 返回 {'TABLE_NAME': 'xxx'}，代码里 t['table_name'] 报 KeyError
SELECT table_name, data_length FROM information_schema.tables WHERE table_schema='huizhiyun'

-- ✅ 正确：用 AS 别名
SELECT TABLE_NAME as tname, DATA_LENGTH as data_mb FROM information_schema.tables WHERE table_schema='huizhiyun'
```

其他库（huizhiyun/software_auth）的普通表不受影响，字段名保持原样。

## withdraw 表无 user_id

withdraw 表只有 `companion_id`，需 JOIN companion 获取 user_id：

```sql
-- ✅ 正确
SELECT w.companion_id, c.user_id, SUM(w.amount) as frozen
FROM withdraw w JOIN companion c ON c.id = w.companion_id
WHERE w.status IN (0, 1) GROUP BY w.companion_id, c.user_id
```

## money_log 无 order_id

money_log 用 `relate_id` 关联订单（不是 `order_id`）：

```sql
-- ✅ 正确
SELECT ml.id, ml.relate_id FROM money_log ml
LEFT JOIN orders o ON o.id = ml.relate_id
WHERE ml.relate_id IS NOT NULL AND ml.relate_id > 0 AND o.id IS NULL
```

## 检查流程

写任何跨库查询前：
1. `mysql -uroot -p'huizhiyun2026' <库名> -e "DESCRIBE <表名>;"` 确认字段
2. 特别注意 `created_at` vs `create_time`、`user_id` vs `username`、`vip_expire` vs `vip_expire_time`
3. 测试 SQL 先 SELECT 验证，确认无报错再写入脚本
