# 充值双订单Bug：前端和pay页面都创建订单

## 症状
用户支付成功后充值记录出现两条，一条已支付（status=1），一条待支付（status=0）。

## 根因
前端 Recharge.vue 在跳转到 `pay.openai2000.cn` 之前先调用了 `api.post('/pay/wxpay/jsapi')` 创建订单，pay.html 的 `window.onload` 中又再次调用同一 API 创建了第二条订单。

## 修复
前端只做跳转，不创建订单：

```javascript
// ❌ 错误
const r = await api.post('/pay/wxpay/jsapi', { amount: amt })
location.href = 'https://pay.openai2000.cn/pay?token=' + token + '&amount=' + amt

// ✅ 正确
const token = localStorage.getItem('token')
location.href = 'https://pay.openai2000.cn/pay?token=' + encodeURIComponent(token) + '&amount=' + amt
```

pay.html 的 `window.onload` 会自己调用 JSAPI 创建订单并保存返回的 `order_no`。
