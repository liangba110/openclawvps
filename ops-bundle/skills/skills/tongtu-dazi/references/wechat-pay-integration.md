# WeChat Pay Integration (2026-07-14 Final Solution)

## 架构

```
dazi.openai2000.cn  (平台主站, JS接口安全域名✅)
  ↕ 跳转
pay.openai2000.cn   (支付中转, JS接口安全域名✅)
  ↕ WeixinJSBridge
微信支付
```

**双域名都必须添加 JS接口安全域名！** 只加一个不行。

## 支付流程

### 微信内（JSAPI）— 推荐流程

```
充值中心(dazi) → 选套餐 → 点「微信支付」
  → 跳转 pay.openai2000.cn/pay?token=xxx&amount=30&subject=套餐名
    → pay页面创建订单（POST dazi/api/pay/wxpay/jsapi → 获取JSAPI参数）
    → 点「确认支付」
      → WeixinJSBridge.invoke('getBrandWCPayRequest', jsapi参数)
        → 支付成功
          → 跳转 dazi/api/pay/wxpay/confirm?order_no=xxx
            → 后端查微信支付结果 → 到账 → 跳回充值页
```

### 关键模式：服务器端确认支付

**不要依赖前端XHR回调更新余额！** XHR回调在微信浏览器中可能被拦截（CORS/跨域问题）。

### 浏览器（Native）— 备用

```
充值中心(dazi) → 选套餐 → JS检测非微信环境
  → POST dazi/api/pay/wxpay/native → 返回 code_url
  → 显示二维码 → 手机微信扫码支付
```

## pay.openai2000.cn 支付页面

`/opt/ttdazi/payment_service/templates/pay.html`

接收参数：`?token=JWT&amount=30&subject=套餐名`

流程：
1. 显示金额 +「确认支付」按钮
2. 页面加载后 POST `dazi/api/pay/wxpay/jsapi` 创建订单（带 Authorization bearer token）
3. 返回 `{order_no, jsapi: {appId, timeStamp, nonceStr, package, signType, paySign}}`
4. 用户点击确认 → `WeixinJSBridge.invoke('getBrandWCPayRequest', jsapi数据)`
5. 成功 → 跳转 `dazi/api/pay/wxpay/confirm?order_no=xxx`

## 后端关键端点

| 路由 | 说明 |
|------|------|
| `GET /api/pay/wxpay/confirm?order_no=xxx` | 服务器端查微信→到账→跳回充值页 |
| `POST /api/pay/wxpay/jsapi` | 创建JSAPI订单（需openid） |
| `POST /api/pay/notify/recharge` | 回调更新余额 |
| `POST /api/v1/wxpay/notify` (pay服务) | 微信支付结果通知（AES-GCM解密） |

## 关键陷阱

| 问题 | 原因 | 修复 |
|------|------|------|
| URL未注册 | JS接口安全域名缺了其中一个域名 | 两个域名都要加 |
| 重复创建两个订单 | 前端create + pay页面又create | 前端只跳转不create |
| 充值后余额不变 | XHR回调被微信拦截 | 改用服务端confirm查询 |
| 支付页面白屏 | CORS配置缺pay域名 | 加 pay.openai2000.cn 到CORS origins |
| subject显示"充值" | 微信支付商品名含敏感词 | 改为"信息匹配服务" |
