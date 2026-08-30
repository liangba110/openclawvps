# Pay.html 双平台自动适配（JSAPI + Native 扫码）

## 背景

支付中转页 `pay.openai2000.cn/pay` 需同时支持：
- **微信内置浏览器** → 调起 `WeixinJSBridge.invoke('getBrandWCPayRequest')`（JSAPI）
- **电脑浏览器 / 手机非微信浏览器** → 显示微信支付二维码（Native）

## 核心检测逻辑

```javascript
// pay.html
var isWeChat = typeof WeixinJSBridge !== 'undefined' || 
               navigator.userAgent.toLowerCase().indexOf('micromessenger') !== -1;
```

## 流程

```
用户跳转到 pay.html
  │
  ├─ order_no 参数存在？
  │   ├─ 是 → 已有订单号
  │   │   ├─ isWeChat？ → 调 JSAPI 支付（需要 openid）
  │   │   └─ 非微信 → Native 扫码支付 + 3s轮询
  │   │
  │   └─ 否 → 需要创建订单
  │       ├─ isWeChat？ → 先调 /api/pay/wxpay/jsapi 创建订单
  │       │                 ├─ 成功 → 显示「确认支付」按钮
  │       │                 └─ 失败 → 2s后降级为 Native 扫码
  │       └─ 非微信 → 直接调 /api/pay/wxpay/native 创建+展示二维码
  │
  └─ 轮询（Native模式）
       GET /api/pay/order-status?order_no=XXX  每3秒
       ├─ paid=true → 显示支付成功 → 1.5s后跳回
       └─ paid=false → 继续轮询
```

## 关键端点

| 端点 | 方法 | 用途 | 所在服务 |
|------|------|------|---------|
| `/api/pay/wxpay/jsapi` | POST | JSAPI 下单，返回 prepay_id 签名的 jsapi 数据 | 支付微服务(5005) |
| `/api/pay/wxpay/native` | POST | Native 下单，返回 code_url（二维码链接） | 支付微服务(5005) |
| `/api/pay/order-status` | GET | 查询订单支付状态（同时查 recharge 和 orders 表） | 后端(5002) |

## Native 扫码支付端点实现（jsapi_pay_endpoint.py）

```python
@pay_api.route('/wxpay/native', methods=['POST'])
def wx_native_pay():
    from wxpay import native_pay
    data = request.get_json() or {}
    amount = data.get('amount', 0)
    subject = data.get('subject', '信息匹配服务')
    order_no = data.get('order_no', '')
    if not order_no: return fail('缺少订单号')
    try:
        result = native_pay(
            out_trade_no=order_no,
            amount=int(float(amount) * 100),  # 元→分
            description=subject[:32]
        )
        if 'code_url' in result:
            return success({'code_url': result['code_url'], 'order_no': order_no, 'amount': amount})
        return fail(str(result.get('message', '微信支付下单失败')))
    except Exception as e:
        return fail(f'支付错误: {str(e)[:80]}')
```

## 订单状态轮询端点

```python
@PAY_API.route('/order-status', methods=['GET'])
def order_status():
    order_no = request.args.get('order_no', '')
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM recharge WHERE order_no=%s", (order_no,))
            row = cur.fetchone()
            if row: return success({'status': row['status'], 'paid': row['status'] == 1}, 'ok')
            cur.execute("SELECT status FROM `orders` WHERE order_no=%s", (order_no,))
            row2 = cur.fetchone()
            if row2: return success({'status': row2['status'], 'paid': row2['status'] >= 2}, 'ok')
            return success({'status': -1, 'paid': False}, '未找到订单')
    finally:
        conn.close()
```

## 坑点

1. **非微信环境跳过 JSAPI**：直接调 Native，避免「参数不完整」报错
2. **JSAPI 失败降级**：在微信内但无 openid 时，2 秒后自动降级到 Native 二维码
3. **QR 库使用 CDN**：`https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js`
4. **轮询间隔 3 秒**：不要太快避免服务器压力，3 秒对扫码支付足够
5. **支付成功跳转**：使用 `location.href` 跳转到 `redirect` 参数指定的地址
