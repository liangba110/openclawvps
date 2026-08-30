# Order Status 0 (待支付) — Missing from Orders.vue

## Problem

The `Orders.vue` page did not handle order status 0 (pending payment). All newly created orders have status 0, but:
- `statusText` map only had `{1:'进行中', 2:'待确认', 3:'已完成', 4:'已取消'}` — no entry for 0
- Tabs only had 全部/进行中/待确认/已完成/已取消 — no 待支付 tab
- Action buttons had no "去支付" button for status 0
- CSS had no `.s0` class — badge rendered with default styles

## Fix Checklist

All 4 changes needed:

### 1. statusText map
```js
const statusText = { 0: '待支付', 1: '进行中', 2: '待确认', 3: '已完成', 4: '已取消' }
```

### 2. Tabs (add 待支付 before 进行中)
```js
const tabs = [
  { label: '全部', value: 'all' },
  { label: '待支付', value: '0' },     // ← NEW
  { label: '进行中', value: '1' },
  { label: '待确认', value: '2' },
  { label: '已完成', value: '3' },
  { label: '已取消', value: '4' },
]
```

### 3. Action buttons (add 去支付 + 取消 for status 0)
```html
<span v-if="order.status === 0" class="action-btn primary" @click="payOrder(order)">去支付</span>
<span v-if="order.status === 3 && !order.reviewed" class="action-btn" @click="goReview(order)">去评价</span>
<span v-if="order.status === 0" class="action-btn danger" @click="cancelOrder(order)">取消</span>
<span v-if="order.status === 1" class="action-btn danger" @click="cancelOrder(order)">取消</span>
```

### 4. payOrder function
```js
async function payOrder(order) {
  showLoading('处理中...')
  try {
    await api.post('/order/pay', { order_id: order.id })
    await hideLoadingAndToast('支付成功')
    load()
  } catch(e) {
    await hideLoadingAndToast(e.message || '支付失败')
  }
}
```

### 5. CSS badge
```css
.s0 { background: #fff3e0; color: #e65100; }
```

## Backend Pay Endpoint

`POST /api/order/pay` — body `{order_id}`:
- Checks order exists and belongs to user
- Checks status === 0
- Sets `status=1, paid_at=NOW()`
- Returns success

The pay endpoint also fires a notification to the user (`💚 支付成功`).

## Testing

1. Create a new order from CreateOrder.vue → status 0
2. Go to /orders → should show "待支付" badge and [去支付] [取消] buttons
3. Click 去支付 → toast "支付成功" → status changes to 1 (进行中)
4. Notification should appear in /messages: `💚 支付成功: 订单(#xxx)支付成功，等待陪玩师接单`
