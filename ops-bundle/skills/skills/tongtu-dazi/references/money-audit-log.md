# 资金审计日志系统（money_log）

## 表结构

```sql
CREATE TABLE IF NOT EXISTS money_log (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL COMMENT '用户ID',
    companion_id INT UNSIGNED DEFAULT 0 COMMENT '陪玩师ID',
    type VARCHAR(30) NOT NULL COMMENT '类型',
    amount DECIMAL(12,2) NOT NULL COMMENT '金额',
    fee DECIMAL(12,2) DEFAULT 0.00 COMMENT '手续费',
    relate_id INT UNSIGNED DEFAULT 0 COMMENT '关联ID(订单ID/提现ID)',
    `desc` VARCHAR(255) DEFAULT '' COMMENT '描述',
    operator INT UNSIGNED DEFAULT 0 COMMENT '操作人(0=系统)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id),
    KEY idx_type (type),
    KEY idx_relate (relate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务日志'
```

## 日志函数

```python
# app/money_log.py
def log_money(user_id, companion_id, type_name, amount, fee, relate_id, desc, operator=0):
    try:
        from db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO money_log (user_id, companion_id, type, amount, fee, relate_id, `desc`, operator) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (user_id, companion_id, type_name, amount, fee, relate_id, desc, operator)
                )
                conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
```

## 类型枚举（7种）

| type | 触发点 | 记录位置 | amount | fee |
|------|--------|---------|--------|-----|
| `order_income` | 用户支付订单 | `order.py pay()`(⚠️非payment.py) | 订单金额 | 平台抽成 |
| `order_settle` | 3天后自动结算 | `settle_orders.py`(cron) | companion_income | 0 |
| `withdraw_request` | 陪玩师申请提现 | `playmate_api.py withdraw()` | 申请总额 | 手续费 |
| `withdraw_approve` | 管理员审核通过 | `admin.py withdrawal_audit()` | 申请总额 | 0 |
| `withdraw_reject` | 管理员审核拒绝 | `admin.py withdrawal_audit()` | 申请总额 | 0 |
| `admin_adjust` | 后台手动调整 | 手动SQL/API | 调整金额 | 0 |
| `recharge` | 用户充值 | `wallet_api.py recharge()` | 充值金额 | 0 |

## 管理后台查看

**入口：** 侧栏 → 📊 财务日志（AdminMoneyLogs.vue, 路由 `/op-*/money-logs`）

**API：** `GET /api/admin/money/logs?page=&size=&type=&user_id=`

返回 `{list, total, page}`，每条含 `nickname`(操作人)。

## ⚠️ 注意事项

1. **日志失败不阻塞主流程** — `except: pass`
2. **`desc` 存人类可读描述**（含金额明细）
3. **`payment.py` vs `order.py`**：前端调 `order.py pay()`，不是 `payment.py`
4. **`get_site_config` import 容易遗漏**：`order.py` 默认没有，手动追加
5. **`__pycache__` 缓存**：修改后必须清_cache 并重启
