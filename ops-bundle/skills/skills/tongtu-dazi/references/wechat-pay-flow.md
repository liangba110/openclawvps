# 同途搭子 WeChat Pay 支付流程

## 架构
```
dazi.openai2000.cn (Flask:5002, 后端API)
     │ 创建订单 / 确认支付
     │
     ▼
pay.openai2000.cn (Flask:5005, Caddy反代, 独立支付微服务)
     │ WeixinJSBridge.invoke 调起支付
     │
     ▼
微信支付 → 回调 → pay.openai2000.cn → 通知 → dazi.openai2000.cn
```

## 完整链路

### 1. 用户点击「立即对接/聊一聊」
1. `Detail.vue` → `goOrder()` / `goChat()` → `router.push('/order/create?companion_id=X')`
2. `CreateOrder.vue` → 显示搭子信息 → 用户点「微信支付 ¥10」
3. `POST /api/order/create` → 后端创建 orders 记录（status=0）→ 返回 `order_no`
4. 跳转 `pay.openai2000.cn/pay?token=X&amount=10&order_no=X&subject=...&redirect=...`

### 2. pay.openai2000.cn/pay 支付中转页
1. 页面加载 → `POST https://dazi.openai2000.cn/api/pay/wxpay/jsapi` （携带token）
2. 后端JSAPI端点 → 查wx_openid → 调pay.openai2000.cn:5005创建JSAPI订单 → 创建recharge记录 → 返回jsapi参数
3. 用户点「确认支付」→ `WeixinJSBridge.invoke('getBrandWCPayRequest', jsapiData, callback)`
4. 支付成功 → 跳转 `https://dazi.openai2000.cn/api/pay/wxpay/confirm?order_no=X&redirect=Y`

### 3. 后端确认（GET /api/pay/wxpay/confirm）
```python
order_no = request.args.get('order_no')
redirect_url = request.args.get('redirect', '/#/recharge')

# 1. 查recharge表
cur.execute("SELECT status, amount, user_id FROM recharge WHERE order_no=%s", (order_no,))
# 2. 如果已支付 → redirect + paid=1
# 3. 如果待支付 → 查WeChat Pay API
req = urllib.request.Request(f'https://pay.openai2000.cn/api/v1/wxpay/query?out_trade_no={order_no}')
result = json.loads(resp.read().decode())
trade_state = result.get('trade_state') or (result.get('data') or {}).get('trade_state')
# 4. 如果SUCCESS → UPDATE + log_money + redirect
```

### 4. 回调双重保障
- **Image beacon**: `new Image().src = '/api/pay/notify/recharge?order_no=X&status=1&amount=X'`
  - 同域 GET，无CORS问题
- **微信服务器通知**: POST → `/api/v1/wxpay/notify` → 解密通知 → update订单 → 调用 `_notify_merchant` → 通知ttdazi后端

## 关键代码路径

| 文件 | 职责 |
|------|------|
| `frontend/.../Recharge.vue` | 信息服务页面，展示套餐/单次 |
| `frontend/.../CreateOrder.vue` | 信息匹配下单页 |
| `frontend/.../Detail.vue` | 详情页，goOrder/goChat |
| `payment_service/templates/pay.html` | 支付中转页面 |
| `payment_service/api.py` | 支付API（jsapi/native/query/notify） |
| `payment_service/wxpay.py` | WeChat Pay APIv3 封装 |
| `backend/app/pay_api.py` | ttdazi后端支付API |
| `backend/app/order.py` | 订单创建 |

## 坑点

1. `companion/detail` 返回 `{data: {info: {...}}}` → 用 `r?.info || r`
2. `wx.chooseWXPay` 兼容性差 → 用 `WeixinJSBridge.invoke('getBrandWCPayRequest')`
3. 跨域POST回调在微信浏览器被拦截 → 用 Image beacon (GET)
4. JSAPI订单的 `subject` 必须写"信息匹配服务"而非"充值"
