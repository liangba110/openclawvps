# 提现/结算系统完整参考

## 资金冻结 + 自动结算流程

陪玩师完成订单 → 🧊 资金冻结3天 → ⏰ 自动释放到可提现余额

### 数据库字段

```sql
-- orders 表
ALTER TABLE orders ADD COLUMN settle_at datetime DEFAULT NULL AFTER status;   -- 冻结到期时间
ALTER TABLE orders ADD COLUMN settled tinyint DEFAULT 0 AFTER settle_at;       -- 已结算标记

-- companion 表（支付宝绑定）
ALTER TABLE companion ADD COLUMN alipay_account varchar(100) DEFAULT '';       -- 支付宝账号
ALTER TABLE companion ADD COLUMN account_name varchar(100) DEFAULT '';         -- 收款人姓名

-- withdraw 表（手续费记录）
ALTER TABLE withdraw ADD COLUMN fee decimal(12,2) DEFAULT 0.00 AFTER amount;   -- 手续费
ALTER TABLE withdraw ADD COLUMN alipay_account varchar(100) DEFAULT '';        -- 提现支付宝（冗余）
ALTER TABLE withdraw ADD COLUMN account_name varchar(100) DEFAULT '';          -- 提现收款人
```

### 后端代码位置

| 功能 | 文件 | 函数/路由 |
|------|------|----------|
| 完成订单时冻结 | `order.py` | `complete()` → `settle_at=DATE_ADD(NOW(), INTERVAL 3 DAY)` |
| 收入查询（只计已结算） | `companion.py` | `my_income()` → `WHERE (settled=1 OR settle_at <= NOW())` |
| 提现申请 | `playmate_api.py` | `withdraw()` → `POST /playmate/withdraw` |
| 定时结算脚本 | `~/.hermes/scripts/settle_orders.py` | cron `every 5m`, no_agent=true |

### 注意事项

1. **withdrawable 计算** = total_income - done(已通过) - frozen(待审核)
2. **手续费** = amount * withdraw_fee_rate% （从 site_config 读取，默认3%）
3. **拒绝退款**：被拒绝的提现不计入 withdrawn，金额释放回余额
4. **收入API与提现API必须用同一套计算逻辑** — 修改 companion.py 的 my_income() 必须同步修改 playmate_api.py 的 withdraw()

## 提现手续费存储规则

**⚠️ `amount` 存储申请总额（¥100），非净额。** `fee` 独立存储。前端/管理端显示时计算 `amount - fee` 作为到账金额。

```python
fee_rate = float(get_site_config('withdraw_fee_rate', 3)) / 100
fee = round(amount * fee_rate, 2)
cur.execute("INSERT INTO withdraw (companion_id, amount, fee, status) VALUES (%s, %s, %s, 0)", (companion_id, amount, fee))
```

## 余额计算

```python
done = SUM(amount) FROM withdraw WHERE status=1        # 只计已通过（不含 status=2 拒绝）
frozen = SUM(amount) FROM withdraw WHERE status=0       # 待审核
withdrawable = max(0, total_income - done - frozen)
```

## 前端显示规则

| 位置 | 显示 | 代码 |
|------|------|------|
| 提现弹窗 | 申请¥100 手续费¥3 到账¥97 | `withdrawAmount * feeRate / 100` |
| 确认弹窗 | 同上 | `formatNum(amt*withdrawFeeRate/100)` |
| 提现记录列表 | **¥97.00** 手续费¥3.00 | `w.fee > 0 ? w.amount - w.fee : w.amount` |
| 管理后台 | **到账金额¥97** 手续费¥3 | 同上计算 |

模板代码：
```vue
<div class="wd-amount">¥{{ formatNum(w.fee > 0 ? w.amount - w.fee : w.amount) }}</div>
<div v-if="w.fee > 0" class="wd-fee">手续费 ¥{{ formatNum(w.fee) }}</div>

<!-- 提现弹窗费用预览 -->
<div v-if="withdrawAmount > 0" class="fee-preview">
  <div class="fp-row"><span>提现金额</span><span>¥{{ formatNum(withdrawAmount) }}</span></div>
  <div class="fp-row"><span>手续费 ({{ withdrawFeeRate }}%)</span><span class="fp-fee">-¥{{ formatNum(withdrawAmount * withdrawFeeRate / 100) }}</span></div>
  <div class="fp-row fp-total"><span>实际到账</span><span class="fp-net">¥{{ formatNum(withdrawAmount * (1 - withdrawFeeRate / 100)) }}</span></div>
</div>
```

```javascript
const withdrawFeeRate = 3  // 与 site_config withdraw_fee_rate 一致
```

## 状态码映射

| 后端 status | 前端 statusLabel | 含义 |
|------------|-----------------|------|
| 0 | '审核中' | 待审核 |
| 1 | '已通过' | 审核通过 |
| 2 | '已拒绝' | 审核拒绝 |
| 3 | '已到账' | 已到账（当前未使用） |

```javascript
// ✅ 正确
function statusLabel(s) { return ({0:'审核中',1:'已通过',2:'已拒绝',3:'已到账'}[s]||s||'未知') }

// ❌ 错误（会导致 status=2 显示为"已到账"）
function statusLabel(s) { return ({0:'审核中',1:'已通过',2:'已到账',3:'已拒绝'}[s]||s||'未知') }
```

## 财务审计

所有提现操作（申请/通过/拒绝/调整）必须记录到 `money_log` 表：
```python
from app.money_log import log_money
log_money(uid, companion_id, 'withdraw_request', amount, fee, withdraw_id, desc, uid)
```
详见 `references/money-audit-log.md`。
