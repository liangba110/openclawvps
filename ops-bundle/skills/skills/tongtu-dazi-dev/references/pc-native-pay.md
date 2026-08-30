# PC 端扫码支付（WeChat Pay Native）

## 概述

支付页面 `pay.openai2000.cn/pay` 自动适配客户端环境：
- **微信内置浏览器** → JSAPI 模式（WeixinJSBridge 调起支付）
- **桌面浏览器/非微信环境** → Native 模式（显示二维码，手机扫码付）

## 检测逻辑（pay.html）

```javascript
var isWeChat = typeof WeixinJSBridge !== 'undefined'
  || navigator.userAgent.toLowerCase().indexOf('micromessenger') !== -1;
```

## Native 支付端点

`POST /api/v1/wxpay/native`（支付微服务，端口 5005）

**请求体：**
```json
{
  "order_no": "XXX",
  "amount": 10,
  "subject": "展示服务费-30天"
}
```

**成功响应：**
```json
{
  "code": 0,
  "data": {
    "code_url": "weixin://wxpay/bizpayurl?pr=xxxxx",
    "order_no": "XXX",
    "amount": 10
  }
}
```

`code_url` 直接传给 `QRCode.js` 库生成二维码图片。

## 轮询确认

PC 端无法接收微信支付异步回调，因此前端每 3 秒轮询后端订单状态：

`GET /api/pay/order-status?order_no=XXX`

**响应：**
```json
{
  "code": 0,
  "data": {
    "paid": true/false,
    "status": 0/1/2
  }
}
```

后端查询 `recharge` 和 `orders` 两张表的 `status` 字段。

## 相关文件

- `/opt/ttdazi/payment_service/templates/pay.html` — 支付页面模板
- `/opt/ttdazi/payment_service/jsapi_pay_endpoint.py` — Native 端点 + JSAPI 端点
- `/opt/ttdazi/payment_service/wxpay.py` — `native_pay()` 函数调微信 APIv3
- `/opt/ttdazi/backend/app/pay_api.py` — `/api/pay/order-status` 轮询端点

## 注意

- Native 支付使用微信 APIv3 `/v3/pay/transactions/native`
- `amount` 参数单位为**元**，后端自动转**分**（×100）
- 需配置 JSAPI 安全域名：`dazi.openai2000.cn` 和 `pay.openai2000.cn`
