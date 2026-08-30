# 陪玩师数据一致性与收入计算规范

## P0-1: companion 统计数据膨胀（2026-07-09 发现并修复）

### 问题

`companion` 表 `total_income` / `total_orders` 字段被 seed 数据严重污染。某陪玩师 `total_income=¥67,484`，但实际收入仅为 ¥339。页面展示的「总收入」数据完全不可信。

### 根因

1. Seed/测试脚本直接写入 `UPDATE companion SET total_income=99999`，从未从 `orders` 表同步
2. 页面/API 优先读取 `companion.total_income` 字段而非实时计算
3. 下单、支付、完成等操作后未更新 `companion` 表的统计字段

### SQL 修复（2026-07-09 执行）

```sql
UPDATE companion c
JOIN (
    SELECT companion_id,
           COALESCE(SUM(companion_income), 0) as real_income,
           COUNT(*) as real_orders
    FROM orders WHERE status >= 1
    GROUP BY companion_id
) o ON o.companion_id = c.id
SET c.total_income = o.real_income,
    c.total_orders = o.real_orders;
```

### 预防规则

- **永不信任 `companion.total_income`**：所有收入计算应从 `orders` 表实时聚合
- **订单操作必须更新 `companion` 统计数据**：每当订单支付/完成时，同步 `UPDATE companion SET total_income=total_income+X, total_orders=total_orders+1`
- **定期全量同步**：每季度执行一次 `UPDATE companion ... JOIN orders ... SET` 确保数据准确

---

## P0-3: 三处收入计算逻辑不一致（2026-07-09 发现并修复）

### 问题

前端三个页面展示的「可提现金额」不同，因为后端三个 API 使用不同的 SQL 条件：

| API 位置 | 路径 | 计算公式 | 
|----------|------|----------|
| `companion.py` | `GET /companion/my/income` | 正确: `SUM WHERE settled=1 OR settle_at<=NOW()` |
| `playmate_api.py` | `GET /playmate/income` | 错误: 直接读 `companion.total_income`（膨胀数据）|
| `playmate_api.py` | `POST /playmate/withdraw` | 错误: `SUM(amount * 0.9) WHERE status>=2` |

### 修复后的统一公式

```python
# 总收入（只计已结算或到期订单）
total_income = COALESCE(SUM(companion_income), 0)
FROM orders WHERE companion_id=%s AND (settled=1 OR settle_at<=NOW())

# 已提现（仅已通过，status=1）
withdrawn = COALESCE(SUM(amount), 0) FROM withdraw WHERE companion_id=%s AND status=1

# 冻结（审核中，status=0）
frozen = COALESCE(SUM(amount), 0) FROM withdraw WHERE companion_id=%s AND status=0

# 可提现
withdrawable = max(0, total_income - withdrawn - frozen)
```

### 检查清单

每次新增/修改收入查询时，确认以下几点：
1. ✅ 总收入 = `companion_income` 字段（非 `amount * 0.9`）
2. ✅ 已结算 = `settled=1` 或 `settle_at<=NOW()`
3. ✅ 已提现 = `status=1`（仅已通过，不含审核中或拒绝）
4. ✅ 冻结 = `status=0`（审核中的提现申请）

---

## P0-4: `pending_settle` 待结算金额计算漏单（2026-07-10 发现并修复）

### 问题

`companion.py` 的 `/companion/my/income` 接口中 `pending_settle` 字段使用 `settled=0 AND settle_at IS NOT NULL` 条件查询，漏掉了大量订单。

### 根因

只有已完成订单（status=3）才会设置 `settle_at`。status=1（已支付待接单）和 status=2（进行中待完成）的订单虽然没有 `settle_at`，却已有 `companion_income`。`settle_at IS NOT NULL` 过滤掉了所有 status<3 的订单。

### 修复后 SQL

```python
# ❌ 错误 — 只查到status=3有settle_at的订单
cur.execute("SELECT COALESCE(SUM(companion_income),0) as pending FROM orders WHERE companion_id=%s AND settled=0 AND settle_at IS NOT NULL", (id,))

# ✅ 正确 — 所有有收入的订单都计入pending_settle
cur.execute("SELECT COALESCE(SUM(companion_income),0) as pending FROM orders WHERE companion_id=%s AND settled=0 AND companion_income>0", (id,))
```

### 明细拆分子字段

| 字段 | 含义 | SQL 条件 |
|------|------|----------|
| `completed_pending` | 已完成待结算（3天冻结） | status=3 AND settled=0 |
| `in_progress_income` | 进行中（待完成） | status=2 AND settled=0 |
| `paid_pending_income` | 已支付（待接单） | status=1 AND settled=0 |

总和 = `pending_settle`。前端展示三行明细帮助陪玩师理解"钱在哪里"。

### 检查清单

每次修改收入/待结算查询时确认：
1. ✅ `pending_settle` 用 `companion_income>0` 而非 `settle_at IS NOT NULL`
2. ✅ 口径覆盖所有 `companion_income>0` 的订单，不论状态
3. ✅ `total_income`（可提现）用 `settled=1 OR settle_at<=NOW()` 只计已到期

---

## P1-1: 提现申请未保存账户信息（2026-07-09 发现并修复）

### 问题

`playmate_api.py` 的 `withdraw()` 函数 INSERT 语句未包含 `alipay_account` / `account_name` 字段：

```python
# ❌ 错误
cur.execute("INSERT INTO withdraw (companion_id, amount, fee, status) VALUES (%s, %s, %s, 0)", ...)

# ✅ 正确
cur.execute("INSERT INTO withdraw (companion_id, amount, fee, alipay_account, account_name, status) VALUES (%s, %s, %s, %s, %s, 0)",
            (companion_id, amount, fee, data.get('alipay_account',''), data.get('account_name','')))
```

### 后果

提现申请记录中的支付宝账号/收款人姓名永久丢失，管理员审核时看不到账户信息。

### 预防

- `INSERT INTO withdraw` 必须写全所有字段（共 6 列）
- 前端发送的 `alipay_account` / `account_name` 必须在后端写数据库

---

## P0-2: 两个 conflicting complete-order 接口（2026-07-09 修复）

### 问题

两个文件分别实现了「完成订单」逻辑，但行为不一致：

| 文件 | 路由 | 设 settle_at | 记 money_log | 读 site_config |
|------|------|:---:|:---:|:---:|
| `order.py` | `POST /order/complete` | ✅ | ❌ | ✅ |
| `playmate_api.py` | `PUT /playmate/complete-order/<id>` | ❌ | ❌ | ❌（硬编码0.8）|

前端 `PlaymateOrders.vue` 调用的是 `POST /order/complete`，所以 `playmate_api.py` 的版本虽未被前端调用，但不一致会导致混淆和后续维护风险。

### 修复

统一两者逻辑：
- 都从 `get_site_config('commission_rate', 20)` 读取抽成比例
- 都设置 `settle_at=DATE_ADD(NOW(), INTERVAL 3 DAY)`
- 都调用 `log_money()` 记录财务日志
- 都通知用户"订单已完成"

### 维护规则

- **不允许两个文件实现同一业务逻辑** — 统一到 `order.py`，`playmate_api.py` 的版本委托给 `order.py` 或改为完全相同逻辑
- **硬编码抽成比例（0.8）必须全部替换为 `get_site_config('commission_rate', 20)`** — 共出现过 3 处（已全部修复）
