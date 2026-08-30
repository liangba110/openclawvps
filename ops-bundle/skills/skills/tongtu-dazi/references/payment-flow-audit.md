# 支付全流程审计（2026-07-09）

## 订单状态流

```
用户下单 → 用户支付 → 用户确认开始 → 陪玩师完成 → 3天冻结 → 自动结算
  status=0 → 1 → 2 → 3 → settled=1
              支付  确认  完成
```

## 发现Bug

### Bug 1: 用户支付后无「确认开始」按钮

**症状：** 用户支付后订单卡在 status=1（进行中），无法进入 status=2（待确认），陪玩师也无法完成订单。

**根因：** `Orders.vue` 模板只定义了 status=0 和 status=2 的操作按钮，缺少 status=1 的「确认开始」按钮。

**修复：** 在 `Orders.vue` 模板中添加：
```html
<span v-if="order.status === 1" class="action-btn primary" @click="confirmStart(order)">▶️ 确认开始</span>
```

### Bug 2: confirm 请求参数 `id` → `order_id`

**症状：** 调用 `/order/confirm` 时后端报错/不生效。

**根因：** 前端发 `{id: order.id}`，后端 `confirm()` 函数读 `data.get('order_id')`。

**修复：** 改为 `{order_id: order.id}`。

### Bug 3: PlaymateHome 接单/拒单 API 路径错误

**症状：** 陪玩师主页接单/拒单按钮点击后 404。

**根因：** 前端调用 `api.post('/order/accept/${id}')` 和 `api.post('/order/reject/${id}')`，但后端正确路由是 `PUT /api/playmate/accept-order/<id>` 和 `PUT /api/playmate/reject-order/<id>`。

**修复：** 改为 `api.put('/playmate/accept-order/${id}')` 和 `api.put('/playmate/reject-order/${id}')`。

## 排查清单（新增订单/支付功能时）

1. **状态按钮全覆盖**：确认 status=0~4 每个状态都有对应的操作按钮
2. **参数名一致**：前端发 `{order_id: id}` 不是 `{id: id}`
3. **路径正确**：订单API在 `order_bp` (`/api/order/`)，陪玩师API在 `playmate_bp` (`/api/playmate/`)
4. **`companion_income` 更新**：`pay()` 函数必须同时更新 `companion_income`
5. **通知双端**：支付→通知用户+陪玩师；确认→通知陪玩师；完成→通知用户
6. **3天结算**：`complete()` 设置 `settle_at=DATE_ADD(NOW(), INTERVAL 3 DAY)`
