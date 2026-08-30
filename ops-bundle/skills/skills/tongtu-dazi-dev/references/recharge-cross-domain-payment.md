# 跨域微信支付流程 (dazi → pay 中转)

## 架构

```
dazi.openai2000.cn (SPA)
  └─ 充值中心: 只做跳转，不加载任何 WeChat JS-SDK
     └─ 点「微信支付」
        └─ location.href → pay.openai2000.cn/pay?token=xxx&amount=30
           └─ pay.html 页面:
              1. POST https://dazi.openai2000.cn/api/pay/wxpay/jsapi (带 token)
                 → 返回 { order_no, jsapi: { appId, timeStamp, nonceStr, package, signType, paySign } }
              2. 保存 order_no 到 myOrderNo 变量 ← ⚠️ 必须从 API 返回中提取
              3. WeixinJSBridge.invoke('getBrandWCPayRequest', jsapi)
              4. 支付成功 → 跳回 dazi.openai2000.cn/#/recharge?order=订单号
                 └─ Recharge.vue 检测 route.query.order → POST /api/pay/notify/recharge → 更新余额

  备用: WeChat Pay 直接通知 pay.openai2000.cn/api/v1/wxpay/notify
    → 解密验证 → 更新 pay_order → 调用 _notify_merchant → POST dazi.../notify/recharge
```

## 双重回调保障

| 方式 | 触发时机 | 可靠性 |
|------|---------|--------|
| 页面跳转回调 | 支付成功后 `location.href` 跳回 dazi 时带上 order 参数 | 高（页面跳转比 XHR 更可靠） |
| 微信服务器通知 | 微信支付成功后异步通知 pay.openai2000.cn | 最高（即使浏览器关闭也能到账） |

## 🔴 关键陷阱

### 1. order_no 必须从 API 返回提取，不能从 URL 参数取

```javascript
// ❌ 错误: URL 参数没有 order_no
var orderNo = getQuery('order_no');  // 永远为空
// 支付成功后用空 order_no 通知后端 → 找不到记录 → 余额不加

// ✅ 正确: 从 API 响应中提取
xhr.onload = function() {
  var res = JSON.parse(xhr.responseText);
  myOrderNo = res.data.order_no;  // ← 保存！
  orderData = res.data.jsapi;
};
```

### 2. 两个域名都必须在 JS接口安全域名

错误「当前页面的url未注册」可能出现于 **两个域名**：
- `dazi.openai2000.cn` — 用户点击支付前所在的页面（WeixinJSBridge 会检查来源页面的域名）
- `pay.openai2000.cn` — 支付中转页面

**必须同时添加两个域名**，只加一个不够。即使前端不再加载 JS-SDK，`WeixinJSBridge.invoke('getBrandWCPayRequest')` 仍会校验域名配置。

### 3. 页面跳转回调（推荐方式）

支付页不直接发 XHR 回调（跨域可能被拦截），改为跳回 dazi 域名：

**pay.html 支付成功：**
```javascript
location.href = 'https://dazi.openai2000.cn/#/recharge?order=' + myOrderNo;
```

**Recharge.vue 检测回调：**
```javascript
onMounted(async () => {
  const orderNo = route.query.order
  if (orderNo) {
    try {
      await api.post('/pay/notify/recharge', {order_no: orderNo, status: 1, amount: 0})
      safeToast('充值到账成功！')
    } catch(e) {}
    window.history.replaceState({}, '', '/#/recharge')
  }
  load()
})
```

### 4. 微信支付通知处理器

`/opt/ttdazi/payment_service/api.py` 中的 `@pay_api.route('/wxpay/notify')` 处理 WeChat Pay 回调通知：
- 验证通知签名（`verify_notify`）
- AES-GCM 解密 `ciphertext` 获取支付结果
- 更新 `pay_order` 状态为已支付
- 调用 `_notify_merchant` → 通知 `dazi.openai2000.cn/api/pay/notify/recharge`

Webhook URL 通过 `wxpay.py` 中的 `WX_NOTIFY_URL` 设置：
```python
WX_NOTIFY_URL = 'https://pay.openai2000.cn/api/v1/wxpay/notify'
```

该 URL 在 JSAPI/Native/H5 支付请求中以 `notify_url` 参数传给微信支付。

### 5. CORS 配置

ttdazi 后端的 CORS 必须允许 pay.openai2000.cn 来源：
```python
CORS(app, resources={r"/api/*": {"origins": [..., "https://pay.openai2000.cn"]}})
```

## pay.html 模板

位于 `/opt/ttdazi/payment_service/templates/pay.html`，由 payment_service app.py 的 `/pay` 路由渲染。

启动流程:
1. 页面加载 → POST /api/pay/wxpay/jsapi → 创建订单 → 返回 jsapi 参数
2. 显示「确认支付」按钮
3. 用户点确认 → WeixinJSBridge.invoke → 微信支付弹窗
4. 支付成功 → 跳回 dazi 域名 + order 参数 → Recharge.vue 检测到账
5. 显示结果 → 点「返回」→ 跳回 dazi.openai2000.cn/#/recharge
