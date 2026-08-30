# 提现手续费系统（从 site_config 读取）

## 数据库

```sql
ALTER TABLE withdraw ADD COLUMN fee decimal(12,2) DEFAULT 0.00 AFTER amount;
```

- `amount` = 申请提现金额（毛额，含手续费）→ 显示时前端计算净额
- `fee` = 手续费
- 净额（实际到账）= `amount - fee`
- **余额扣除全额**（`amount`），手续费不留在余额里

## 配置（site_config 表）

| key | value | 说明 |
|-----|-------|------|
| `commission_rate` | 20 | 平台抽成比例(%) |
| `withdraw_fee_rate` | 3 | 提现手续费率(%) |
| `withdraw_min` | 100 | 最低提现金额(元) |

配置值在管理后台 → 系统设置 → 财务配置 中修改。

## 后端（playmate_api.py withdraw）

```python
# 从配置读取参数
min_wd = float(get_site_config('withdraw_min', 100))
if amount < min_wd:
    return fail(f'提现金额不能少于 ¥{int(min_wd)}')

fee_rate = float(get_site_config('withdraw_fee_rate', 3)) / 100
fee = round(amount * fee_rate, 2)

# 记录提现申请（amount 存毛额，fee 存手续费）
cur.execute(
    "INSERT INTO `withdraw` (companion_id, amount, fee, status) VALUES (%s, %s, %s, 0)",
    (companion_id, amount, fee)
)
```

### 🔴 关键：amount 存毛额，不是净额

**记录流：**
1. 用户申请提现 ¥100 → `amount=100, fee=3` 写入数据库
2. 余额扣除 ¥100（全额，含手续费）
3. 前端显示：¥97（`amount - fee`，净额）
4. 管理员看到：到账金额 ¥97

**为什么：** 如果存净额（¥97），余额只扣 ¥97，手续费 ¥3 会残留在余额中。

### 可提现金额计算（playmate_api.py + companion.py）

两个文件必须一致：

```python
# 已通过的提现 - 只统计 status=1（已通过），不含 status=2（已拒绝）
SELECT IFNULL(SUM(amount), 0) as done FROM withdraw WHERE companion_id=%s AND status=1

# 申请中的冻结
SELECT IFNULL(SUM(amount), 0) as frozen FROM withdraw WHERE companion_id=%s AND status=0

withdrawable = total_income - done - frozen
```

**注意：** `done` 只统计 `status=1`（已通过）。被拒绝的提现（`status=2`）释放回可提现余额。

### 收入展示（companion.py my_income）

```python
comm_rate = float(get_site_config('commission_rate', 20))
return success({
    'commission_rate': comm_rate,
    'withdrawable': withdrawable,
    'pending_settle': pending_settle,
    'withdrawn': withdrawn,
    'frozen': frozen,
    'min_withdraw': float(get_site_config('withdraw_min', 100)),
})
```

## 前端提现弹窗

```html
<div v-if="withdrawAmount > 0" class="fee-preview">
  <div class="fp-row"><span>提现金额</span><span>¥{{ formatNum(withdrawAmount) }}</span></div>
  <div class="fp-row"><span>手续费 ({{ withdrawFeeRate }}%)</span><span class="fp-fee">-¥{{ formatNum(withdrawAmount * withdrawFeeRate / 100) }}</span></div>
  <div class="fp-row fp-total"><span>实际到账</span><span class="fp-net">¥{{ formatNum(withdrawAmount * (1 - withdrawFeeRate / 100)) }}</span></div>
</div>
```

确认弹窗：
```
提现 ¥100.00，手续费 ¥3.00，实际到账 ¥97.00，是否继续？
```

声明手续费率常量：
```js
const withdrawFeeRate = 3  // 与 site_config.withdraw_fee_rate 一致
```

## 提现记录显示（净额）

```html
<!-- amount 是毛额（100），显示净额（97） -->
<div class="wd-amount">¥{{ formatNum(w.fee > 0 ? w.amount - w.fee : w.amount) }}</div>
<div v-if="w.fee > 0" class="wd-fee">手续费 ¥{{ formatNum(w.fee) }}</div>
```

### 🔴 `fee` 字段缺失导致显示错误

**症状：** 提现记录显示 ¥100 而非 ¥97，因为 `w.fee` 为 undefined。

**根因：** `withdraw/history` API 的 SELECT 漏了 `fee` 字段：
```python
# ❌ 错误：漏了 fee
cur.execute("""SELECT id, amount, status, created_at, updated_at
    FROM `withdraw` WHERE companion_id=%s ORDER BY id DESC LIMIT 50""")

# ✅ 正确：包含 fee
cur.execute("""SELECT id, amount, fee, status, created_at, updated_at
    FROM `withdraw` WHERE companion_id=%s ORDER BY id DESC LIMIT 50""")
```

**排查：** 用 curl 检查 API 返回是否包含 `fee` 字段：
```bash
curl -s /api/playmate/withdraw/history | python3 -c \
  "import sys,json;d=json.load(sys.stdin);print(d['data'][0].keys())"
```

## 规则文本动态化

```html
<div class="rules-line">· 完成订单的 {{ incomeShare }}% 收入进入可提现余额</div>

<script setup>
const incomeShare = computed(() => 100 - Number(income.value.commission_rate || 20))
</script>
```

## 🔴 状态码映射（前后端一致）

| 后端 status | 含义 | 前端显示 |
|-------------|------|---------|
| 0 | 待审核 | 审核中 |
| 1 | 已通过 | 已通过 |
| 2 | **已拒绝** | **已拒绝** |
| 3 | 已到账 | 已到账（暂未使用） |

```javascript
function statusLabel(s) { return ({0:'审核中',1:'已通过',2:'已拒绝',3:'已到账'}[s]||s||'未知') }
```

**🔴 常见 Bug：** `{0:'审核中',1:'已通过',2:'已到账',3:'已拒绝'}` — status=2 映射为"已到账"是错误的。后端 status=2 是"已拒绝"。

## 管理员后台显示

AdminWithdrawals.vue：

| 列 | 值 |
|----|-----|
| 到账金额 | `w.amount - w.fee`（净额） |
| 手续费 | `w.fee` |
| 状态 | 待审核/已通过/已拒绝 |

```html
<td class="mono" style="font-weight:600;">¥{{ w.fee > 0 ? (w.amount - w.fee) : w.amount }}</td>
<td>¥{{ w.fee || '0' }}</td>
```

## 费用结构

```
订单金额 ¥200
  → 平台抽成 20%（commission_rate）= ¥40
  → 陪玩师收入 ¥160（companion_income）
    → 冻结 3 天（待结算）
    → 释放到可提现余额
    → 提现 ¥100
      → 手续费 3%（withdraw_fee_rate）= ¥3
      → 实际到账 ¥97
```

## ⚠️ 收入计算冲突（companion.py vs playmate_api.py）

两个文件都有收入计算逻辑，必须保持一致：

| 文件 | 函数 | 旧查询（错误） | 新查询（正确） |
|------|------|--------------|--------------|
| companion.py | `my_income()` | `status>=2` | `(settled=1 OR settle_at <= NOW())` |
| playmate_api.py | `withdraw()` | `o.amount * 0.9` + `o.status=3` | `companion_income` + `o.settled=1` |

**症状：** 用户端收入页显示 `withdrawable=100`，但提现时报"可提现余额不足"。

**排查：** 同时检查两个文件的 `total_income` 查询和 `done`（已提现）查询：
1. `total_income` 是否使用相同字段（`companion_income` vs `amount * 0.9`）
2. `done` 是否只统计 `status=1`（不含被拒绝的 `status=2`）
3. `frozen` 是否包含 `status=0`（申请中的提现）

## 🔴 `get_site_config` 导入坑

```python
# ✅ 正确
from app.utils import get_site_config

# ❌ 错误（config.py 不存在）
from app.config import get_site_config
```

`get_site_config` 定义在 `utils.py` 中。修改 `utils.py` 后必须清除 `__pycache__`：
```bash
find /opt/ttdazi/backend -name "__pycache__" -type d -exec rm -rf {} +
systemctl restart ttdazi
```
