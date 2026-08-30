# Image Beacon 支付回调模式（无跨域方案）

## 问题背景

微信内置浏览器对跨域 XHR 请求有限制。当支付页（`pay.openai2000.cn`）需要通知后端（`dazi.openai2000.cn`）时，标准 XHR POST 或 fetch 在 WeChat 浏览器中可能被拦截。

## 方案对比

| 方案 | 可靠性 | 复杂度 |
|------|--------|--------|
| XHR POST with CORS | ⭐⭐ | 低（需后端配置 CORS） |
| Image Beacon (GET) | ⭐⭐⭐⭐⭐ | 极低（无需 CORS） |
| 页面跳转回调 | ⭐⭐⭐ | 中（URL参数传递） |
| 微信服务器通知 | ⭐⭐⭐⭐⭐ | 高（需解密 notify） |

## Image Beacon 实现

```javascript
// ✅ 支付成功回调 — 用 new Image() 触发 GET 请求，无跨域限制
new Image().src = '/api/pay/notify/recharge?order_no=' + encodeURIComponent(orderNo) + '&status=1&amount=' + amount;
```

原理：浏览器加载 `<img>` 标签不受同源策略限制，即使跨域也能正常发出 GET 请求。后端收到请求后处理到账逻辑即可。

## 后端适配（GET + POST 双模式）

为了让后端同时支持 POST 回调（来自微信服务器通知）和 GET 回调（来自 Image Beacon）：

```python
@PAY_API.route('/notify/recharge', methods=['POST', 'GET'])
def notify_recharge():
    if request.method == 'GET':
        data = request.args
    else:
        data = request.get_json() or {}
    order_no = data.get('order_no', '')
    # ... 处理到账逻辑
```

## 完整支付流程（推荐方案）

```
① 用户在 dazi.openai2000.cn 充值页
② 前端 POST /api/pay/wxpay/jsapi → 后端创建订单 + 返回 JSAPI 参数
③ 前端调用 WeixinJSBridge.invoke('getBrandWCPayRequest', jsapiData)
④ 用户输入密码 → 支付成功
⑤ 前端 new Image().src = GET /api/pay/notify/recharge?order_no=XX
   ↓ 后端更新 recharge 表 + 增加 balance + 记 money_log
⑥ 前端 setTimeout 3秒后 reload 余额
⑦ 双重保障：微信服务器异步通知 → pay.openai2000.cn/wxpay/notify
   → _notify_merchant → dazi.openai2000.cn/api/pay/notify/recharge
```

## 关键陷阱

### ❌ order_no 从 URL 参数取（永远为空）

```javascript
// ❌ 错误 — 前端跳转 pay.openai2000.cn/pay?token=xxx&amount=30
// 没有传 order_no 参数！
var orderNo = getQuery('order_no');  // 空字符串
// 支付成功回调用空 order_no → 后端找不到记录 → 不加余额

// ✅ 正确 — 从 API 响应中提取
xhr.onload = function() {
  var res = JSON.parse(xhr.responseText);
  myOrderNo = res.data.order_no;  // 后端创建订单时返回的 out_trade_no
};
```

### ❌ WeixinJSBridge 仍需 JS接口安全域名

`WeixinJSBridge.invoke('getBrandWCPayRequest')` 在较新版本的微信中会校验页面域名是否在 JS接口安全域名中。**即使不加载 wx JS-SDK，WeixinJSBridge 也需要域名白名单。**

当使用跨域支付流程时，**两个域名都必须添加**：
- `dazi.openai2000.cn` — 用户点击支付时所在的页面
- `pay.openai2000.cn` — 支付中转页面（如果使用了）

只加一个域名会在另一个域名上出现「当前页面的url未注册」错误。

### ✅ 服务器端支付确认（最可靠）

最可靠的方案是让**服务器端**查询微信支付结果，而不是依赖前端回调：

```python
@PAY_API.route('/wxpay/confirm', methods=['GET'])
def wxpay_confirm():
    """支付成功后跳转到此，服务器端查询微信支付结果并到账"""
    order_no = request.args.get('order_no', '')
    # 1. 查本地 recharge 记录
    # 2. 调用 pay.openai2000.cn/api/v1/wxpay/query 查微信状态
    # 3. 如果 trade_state == 'SUCCESS' → 更新余额
    # 4. 重定向回充值页
    return redirect('https://dazi.openai2000.cn/#/recharge')
```

前端：
```javascript
WeixinJSBridge.invoke('getBrandWCPayRequest', {...}, function(res) {
  if (res.err_msg === 'get_brand_wcpay_request:ok') {
    location.href = '/api/pay/wxpay/confirm?order_no=' + encodeURIComponent(orderNo);
  }
});
```

注意：查询微信支付结果时，`trade_state` 字段可能嵌套在 `data` 对象中（`result.get('data', {}).get('trade_state', '')`），需要兼容两种返回格式。
