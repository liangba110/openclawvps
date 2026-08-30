# 订单资金冻结结算系统

## 流程

用户支付 → 确认开始(status=2) → 陪玩师完成(status=3) → 🧊 冻结3天 → ✅ 自动释放到余额

```
status: 0(待支付) → 1(进行中) → 2(待确认) → 3(已完成)
                                         ↓
                                  settle_at = NOW() + 3 DAY
                                         ↓
                             每5分钟检查 settle_at <= NOW()
                                         ↓
                                  settled=1, 资金释放
```

## 数据库

`orders` 表新增字段：
- `settle_at` datetime — 预计结算时间（完成订单时设为 3 天后）
- `settled` tinyint DEFAULT 0 — 是否已结算

```sql
ALTER TABLE orders ADD COLUMN settle_at datetime DEFAULT NULL AFTER status;
ALTER TABLE orders ADD COLUMN settled tinyint DEFAULT 0 AFTER settle_at;
```

## 后端改动

### order.py — 完成订单时设 settle_at

```python
cur.execute("UPDATE `orders` SET status=3, settle_at=DATE_ADD(NOW(), INTERVAL 3 DAY) WHERE id=%s", (order_id,))
```

### companion.py — 收入查询只计已结算订单

```python
# 总收入（只算已结算的）
SELECT COALESCE(SUM(companion_income),0) as total_income
FROM orders WHERE companion_id=%s AND (settled=1 OR settle_at <= NOW())

# 待结算金额
SELECT COALESCE(SUM(companion_income),0) as pending
FROM orders WHERE companion_id=%s AND settled=0 AND settle_at IS NOT NULL
```

## API 返回

```python
return success({
    'withdrawable': withdrawable,        # 可提现金额
    'pending_settle': pending_settle,    # 待结算金额（冻结中）
    'withdrawn': withdrawn,              # 累计已提现
    'frozen': frozen,                    # 申请中冻结（提现审核中）
    'min_withdraw': 100.0,               # 最低提现金额
})
```

## 定时结算脚本

`~/.hermes/scripts/settle_orders.py`（每5分钟执行）：

```python
cur.execute("""
    SELECT o.id, o.companion_id, o.companion_income,
           c.user_id as companion_user_id, u.nickname
    FROM orders o
    JOIN companion c ON c.id = o.companion_id
    JOIN user u ON u.id = c.user_id
    WHERE o.settled = 0 AND o.settle_at IS NOT NULL AND o.settle_at <= NOW()
""")
for o in orders:
    cur.execute("UPDATE orders SET settled=1 WHERE id=%s", (o['id'],))
    # 通知陪玩师
    INSERT INTO notification (user_id, type, title, content, created_at)
    VALUES (%s, 'system', '订单已结算', msg, NOW())
```

Cron 配置：`hermes cron job-name scheduled every 5m script settle_orders.py no_agent true`

## 前端显示

```html
<div v-if="hasPending" class="pending-bar">
  ⏳ 待结算金额：¥{{ formatNum(income.pending_settle) }}（3天后到账）
</div>

<script setup>
const hasPending = computed(() => Number(income.value.pending_settle || 0) > 0)
</script>
```

## 🔴 关键坑：companion_id 必须匹配当前用户

**症状**：创建了待结算订单（`settled=0, settle_at=3天后`），但 `pending_settle=0`。

**根因**：订单的 `companion_id` 属于其他陪玩师，而非当前登录用户。例如订单 `companion_id=1`（猫猫酱），但用户 13800138000（小甜心）的 `companion_id=23`。

**排查**：
```sql
-- 先查当前用户的 companion_id
SELECT c.id AS companion_id FROM companion c JOIN user u ON u.id=c.user_id WHERE u.phone='13800138000';
```

**修复**：使用正确的 `companion_id` 创建或修改测试订单。

## 注意

1. 待结算金额不纳入 `withdrawable` 计算
2. `total_income` 和 `month_income` 只计已结算订单
3. 结算脚本使用 `no_agent=true`（静默执行）
4. 脚本从 `~/.hermes/scripts/` 运行
