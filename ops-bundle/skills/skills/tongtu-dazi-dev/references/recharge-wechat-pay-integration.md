# Recharge + WeChat Pay Integration

## Architecture

```
User clicks "微信支付" on Recharge.vue
  → POST /api/pay/wxpay/native (ttdazi backend, pay_api.py)
    → POST https://pay.openai2000.cn/api/v1/wxpay/native (payment microservice)
      → WeChat Pay API → returns code_url
    ← Returns { code_url, order_no }
  → Shows QR code modal (via qrserver.com API)
  → Starts 3s polling: GET /api/pay/wxpay/status?order_no=XXX
```

## Payment Notification (async)

```
WeChat Pay → POST pay.openai2000.cn/api/v1/wxpay/notify
  → payment service confirms order
  → calls _notify_merchant() → POST https://dazi.openai2000.cn/api/pay/notify/recharge
    → ttdazi backend: UPDATE recharge SET status=1 + UPDATE user SET balance=balance+amount
```

## Database

```sql
CREATE TABLE recharge (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  order_no VARCHAR(64) NOT NULL DEFAULT '',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '0=待支付 1=已支付',
  method VARCHAR(20) DEFAULT 'wechat',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  paid_at DATETIME NULL,
  INDEX idx_order_no (order_no),
  INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/pay/wxpay/native` | POST | @login_required | Create recharge order + get QR code |
| `/api/pay/wxpay/status` | GET | none | Check recharge payment status |
| `/api/pay/notify/recharge` | POST | none (internal) | Payment service callback |

## Frontend: Recharge.vue

### Key states
- `showQr` — QR code modal visibility
- `payStatus` — `pending` / `success` / `timeout`
- 3-minute polling timeout (180s, 3s interval)
- QR code generated via `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${code_url}`

### Polling
```js
function startPoll() {
  let elapsed = 0
  pollTimer = setInterval(async () => {
    elapsed += 3
    if (elapsed > 180) { payStatus.value = 'timeout'; stopPoll(); return }
    const r = await api.get(`/api/pay/wxpay/status?order_no=${orderNo}`)
    if (r.status === 1) { payStatus.value = 'success'; stopPoll(); loadBalance() }
  }, 3000)
}
```

### Important
- Must `onUnmounted(stopPoll)` to prevent polling after navigation
- `recharge_list` API queries `recharge` table (not `wallet_recharge`)
- Old `wallet_recharge` table was dropped after migration

## Hooks into payment service

Payment service `api.py` `_notify_merchant` function:
- When `callback_url` is empty (merchant has no callback_url), fallback to ttdazi notify URL:
```python
if not callback_url:
    callback_url = 'https://dazi.openai2000.cn/api/pay/notify/recharge'
```

## JSAPI 支付（微信内置浏览器）— 跳转到 pay.openai2000.cn

在微信内置浏览器中，Native 扫码无法使用（不能扫自己屏幕上的码）。改用 **跳转到 pay.openai2000.cn 独立页面** 的 JSAPI 支付方案：

```
Recharge.vue 检测 isWechat() === true
  → location.href = 'https://pay.openai2000.cn/pay?token=xxx&amount=30'
  → pay.openai2000.cn 页面加载 → 创建 JSAPI 订单
  → POST https://dazi.openai2000.cn/api/pay/wxpay/jsapi
    → 支付服务组装 JSAPI 参数（RSA签名）
  → WeixinJSBridge.invoke('getBrandWCPayRequest', ...) → 弹支付
  → 成功 → 通知 dazi.openai2000.cn/api/pay/notify/recharge → 到账
```

详见 📖 `references/weixin-jsbridge-payment.md`「支付域名跳转模式」

## Pitfalls

1. **Missing `@login_required`** on `/api/pay/wxpay/native` causes `AttributeError: 'Request' object has no attribute 'current_user'`
2. **`recharge` table didn't exist initially** — create before testing
3. **`recharge_list` API queried old `wallet_recharge` table** — must update to query `recharge` table
4. **QR code polling must be cleaned up** on component unmount
