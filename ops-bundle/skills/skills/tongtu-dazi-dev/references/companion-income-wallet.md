# 陪玩师收入/钱包/提现领域参考

> 本项目所有"钱"相关接口的字段口径、提现流程、Decimal 处理、边界校验。

## 1. 核心接口与字段口径

| 接口 | 方法 | 用途 | 关键返回字段 |
|------|------|------|--------------|
| `/api/companion/my/income` | GET | 陪玩师收入总览 | `total_income, month_income, order_count, review_count, withdrawable, withdrawn, frozen, min_withdraw, trend` |
| `/api/playmate/withdraw` | POST | 申请提现 | `{amount}` → 成功则冻结对应金额 |
| `/api/playmate/withdraw/history` | GET | 提现记录列表 | 数组（每条 `id, amount, status, created_at, updated_at`） |
| `/api/playmate/income` | GET | 收入明细（分页） | `total_income, withdrawable, records, total, page, page_size` |

### `withdraw` 表 status 字段（tinyint）

| 值 | 含义 | UI 标签 |
|----|------|---------|
| 0 | 审核中 | 审核中（橙色） |
| 1 | 已通过 | 已通过（蓝色） |
| 2 | 已到账 | 已到账（绿色） |
| 3 | 已拒绝 | 已拒绝（红色） |

> 注意：后端 SQL 全部用整型 0/1/2/3，不要存 'pending'/'approved' 字符串。

## 2. 关键口径公式

```python
# 可提现 = 累计已完成订单收入(80%) - 已提现 - 申请中
total_income = SUM(orders.companion_income WHERE status>=2)  # 进行中+已完成
withdrawn    = SUM(withdraw.amount WHERE status IN (1,2))    # 已通过+已到账
frozen       = SUM(withdraw.amount WHERE status=0)           # 审核中
withdrawable = max(0, total_income - withdrawn - frozen)
min_withdraw = 10.0  # 最低提现金额
```

### ⚠️ total_income 口径争议

当前 `my/income` 用 `status>=2`（进行中+已完成）算 total_income。**进行中订单的 80% 还没真正到账**就被算进可提现，可能造成超提。

**改进方向**（如果业务要求严格）：改用 `status=3`（仅已完成）算 total_income。需要业务确认。

## 3. 提现接口必备校验（缺一就出 BUG）

```python
@playmate_bp.route('/withdraw', methods=['POST'])
@companion_required
def withdraw():
    data = request.get_json() or {}
    amount = float(data.get("amount", 0))

    # ✅ 必加：金额 > 0
    if amount <= 0:
        return fail('提现金额不正确')

    # ✅ 必加：最低提现金额（前端 UI 提示依赖此字段）
    if amount < 10:
        return fail('提现金额不能少于 ¥10')

    # ✅ 必加：余额不足（已有）
    if amount > withdrawable:
        return fail(f'可提现余额不足，当前可提现¥{withdrawable:.2f}')

    # ✅ 必加：通知用户
    send_notification(uid, f'提现¥{amount:.2f}申请已提交，等待管理员审核',
        ntype='system', title='提现申请已提交', icon='💰', data_id=0)
```

## 4. Decimal → JSON String 序列化陷阱

`withdraw.amount` 是 MySQL `DECIMAL(12,2)`，Python pymysql 返回 `Decimal('50.00')`。  
`jsonify` 默认不序列化 Decimal，但实际表现是变成 **字符串 `"50.00"`** 返回：

```json
{"id": 1, "amount": "50.00", "status": 0}
```

**前端必须用 `Number(v) || 0` 包装**：

```js
function formatNum(v) {
  const n = Number(v) || 0
  return n.toFixed(2)
}
```

不能直接 `parseFloat(v).toFixed(2)` —— `parseFloat('50.00')` 是 50 OK，但 `parseFloat(null)` 是 NaN。

## 5. 模板字段 vs API 响应审计（必做）

**事故还原**：`PlaymateIncome.vue` 模板用了 `income.value.withdrawable`，但 `/api/companion/my/income` 根本没返回 `withdrawable` 字段。前端永远拿到 `undefined`，按钮文案 fallback 到"暂无可提现金额"，用户看不到真实余额。

**预防检查清单**（任何 read-API 上线前）：

1. `grep -rn 'income\.\|stats\.' frontend/src/views/` — 列出所有模板引用的字段
2. 对比后端 SQL `SELECT` 和 `return success({...})` 实际返回的字段
3. 缺的字段全部补全（前端加 fallback OR 后端补字段，**优先后端**）
4. curl 真实 token 验证返回 JSON 结构

## 6. CLI 直接生成测试 Token（绕过图形验证码）

```python
# /opt/ttdazi/backend/app/token_auth.py 暴露的是 gen_token，不是 create_token
from app.token_auth import gen_token
print(gen_token(user_id=10001, device_id='cli-test'))
# 输出: v2.10001.1783310748.1800.57529e61cac83de9089f0480.cli-test
```

格式：`v2.{user_id}.{ts}.{ttl_sec}.{rand16}.{device_id}`

**用法**：先在 DB 查 user_id（`SELECT id FROM user WHERE phone='13800138000'`），再生成 token，curl 时 `-H "Authorization: Bearer $TOKEN"` 即可跳过登录验证码。

## 7. 提现弹窗 — 自定义 v-if 模式（不用 Vant）

`van-dialog` / `van-popup` 在移动 WebView 容易残留遮罩。提现这种带输入框的弹窗，**全部用自定义 v-if 模式**：

```vue
<div v-if="withdrawShow" class="modal-overlay" @click.self="withdrawShow=false">
  <div class="modal-box">
    <input v-model.number="withdrawAmount" type="number" />
    <button @click="confirmWithdraw" :disabled="submitting">确认</button>
  </div>
</div>
```

**关键**：
- `v-if`（不是 v-show）— 隐藏时无 DOM
- `@click.self` — 点遮罩关闭
- `onUnmounted(() => { withdrawShow.value = false })` 兜底
- `submitting` 状态在 `try/finally` 中重置

## 8. 浏览器验证不可用时的替代方案

**触发条件**：`browser_navigate` 返回 `net::ERR_BLOCKED_BY_CLIENT`（广告拦截器）  
**降级路径**：
1. curl 直接打后端（`http://127.0.0.1:5002`）— 不走 Nginx 代理
2. curl 走 Server B 代理（`http://82.157.202.24`）— 模拟用户路径
3. 检查构建产物（`dist/assets/index-XXXX.js`）确认 hash 已同步
4. 用 `python3.12 -c "from app.module import fn; print('OK')"` 验证后端 import 正常

**不能放弃验证**：只写代码不 curl 等于没做。

## 9. 真实数据示例（陪玩师 13800138000/小甜心）

```json
{
  "total_income": 593.25,
  "month_income": 0.0,
  "withdrawable": 593.25,
  "withdrawn": 0.0,
  "frozen": 0.0,
  "min_withdraw": 10.0,
  "order_count": 8,
  "review_count": 4
}
```

测试提现 ¥10 → `frozen:10, withdrawable:583.25`，再次查询记录列表有 1 条 status=0 的记录。

## 10. 完整改文件清单（陪玩师"我的"页面修复）

| 文件 | 改动 |
|------|------|
| `backend/app/companion.py` | `my_income()` 增 `withdrawable/withdrawn/frozen/min_withdraw` 4 字段 |
| `backend/app/playmate_api.py` | `withdraw()` 加 `if amount < 10: return fail(...)` |
| `frontend/src/views/playmate/PlaymateIncome.vue` | 完整重写：余额主卡 + 4 概览 + 规则说明 + 提现弹窗 + 记录列表 |
| `frontend/src/views/playmate/PlaymateHome.vue` | 头部加"可提现金额条"（可点跳钱包页），script 加 formatNum + 提取新字段 |
