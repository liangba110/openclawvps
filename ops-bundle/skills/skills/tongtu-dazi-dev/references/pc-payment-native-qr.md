# PC端扫码支付流程（Native QR）

## 架构

```
PC/手机浏览器 → pay.openai2000.cn/pay?token=X&amount=X&order_no=X
       ↓ 检测 User-Agent
┌─ WeChat JSAPI（微信内置浏览器）──┐   ┌─ Native QR（桌面浏览器）───┐
│ WeixinJSBridge.invoke(...)      │   │ 显示微信支付二维码         │
│ 直接调起微信支付                │   │ 手机扫码 → 支付            │
│                                 │   │ 前端轮询 /api/pay/order-status │
└─────────────────────────────────┘   └───────────────────────────┘
```

## 支付页面

`/opt/ttdazi/payment_service/templates/pay.html`

### 自动环境检测

```javascript
var isWeChat = typeof WeixinJSBridge !== 'undefined' 
    || navigator.userAgent.toLowerCase().indexOf('micromessenger') !== -1;
```

### 桌面端流程

1. 检测到非微信浏览器 → 调用 `POST /api/pay/wxpay/native`
2. 请求体: `{order_no, amount, subject}`
3. 后端返回 `{code_url}` (微信支付二维码链接)
4. 前端用 `qrcode.min.js` (CDN) 渲染二维码
5. 启动 3秒间隔轮询: `GET /api/pay/order-status?order_no=X`
6. 返回 `{paid: true}` → 跳转回平台

## 后端接口

### `/api/pay/wxpay/native` (支付服务 5005)

```python
# /opt/ttdazi/payment_service/jsapi_pay_endpoint.py
@pay_api.route('/wxpay/native', methods=['POST'])
def wx_native_pay():
    from wxpay import native_pay
    result = native_pay(out_trade_no=order_no, amount=分, description=subject[:32])
    # result['code_url'] = 二维码链接
```

### `/api/pay/order-status` (后端 5002)

```python
# /opt/ttdazi/backend/app/pay_api.py
@PAY_API.route('/order-status', methods=['GET'])
def order_status():
    # 查 recharge 表 + orders 表
    # 返回 {paid: bool}
```

## 微信支付模块

`/opt/ttdazi/payment_service/wxpay.py` — 支持三种模式：

| 函数 | 微信模式 | 适用场景 |
|------|---------|---------|
| `jsapi_pay()` | JSAPI | 微信内置浏览器 |
| `native_pay()` | NATIVE | PC端扫码 |
| `h5_pay()` | H5 | 手机浏览器（非微信） |

## 关键文件

| 文件 | 说明 |
|------|------|
| `/opt/ttdazi/payment_service/templates/pay.html` | 支付中转页面（JSAPI + Native 双模） |
| `/opt/ttdazi/payment_service/jsapi_pay_endpoint.py` | JSAPI + Native 端点 |
| `/opt/ttdazi/payment_service/wxpay.py` | 微信支付 APIv3 封装 |
| `/opt/ttdazi/backend/app/pay_api.py` | 后端支付确认 + 订单状态轮询 |
