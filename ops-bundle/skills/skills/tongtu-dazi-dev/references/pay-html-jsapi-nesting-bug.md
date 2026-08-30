# pay.html JSAPI 参数嵌套修复记录

**修复时间**：2026-07-18
**修改文件**：`/opt/ttdazi/payment_service/templates/pay.html`

## Bug: `res.data.jsapi` 被当作 `res.data` 传给 WeixinJSBridge

### 症状

微信浏览器内点击「确认支付」按钮 → 微信支付窗口没有弹出 → 页面提示"jsapi 失败"。

### 后端响应结构

后端 `dazi.openai2000.cn/api/pay/wxpay/jsapi` 返回：
```json
{
  "code": 0,
  "data": {
    "amount": 69,
    "jsapi": {                    // ← 微信支付参数在这里面
      "appId": "wxd274e174ddadd4cb",
      "timeStamp": "1784375136",
      "nonceStr": "cf18b357719301c6",
      "package": "prepay_id=wx181945363037280db09053ca9d1adb0001",
      "signType": "RSA",
      "paySign": "Geddk5KHmI1Q/..."
    },
    "order_no": "JS100471784375135"
  }
}
```

### 错误代码

```javascript
// ❌ 错误：把整个 data 对象传给了微信
xhr.onload = function() {
  var res = JSON.parse(xhr.responseText);
  if (res.code === 0 && res.data) {
    orderData = res.data;  // ← {amount:69, jsapi:{...}, order_no:"..."}
    // WeixinJSBridge 收到的是 {amount, jsapi, order_no}
    // 而不是它期望的 {appId, timeStamp, nonceStr, package, signType, paySign}
    WeixinJSBridge.invoke('getBrandWCPayRequest', orderData, callback);
    // → 微信找不到所需字段 → 返回 err_msg 异常 → "jsapi 失败"
  }
};

// ✅ 正确：提取 data.jsapi 才是微信需要的参数
orderData = res.data.jsapi || res.data;
myOrderNo = res.data.order_no || myOrderNo;
WeixinJSBridge.invoke('getBrandWCPayRequest', orderData, callback);
```

### 影响范围

pay.html 中有 **两处** 需要修改：
1. `myOrderNoParam` 分支（CreateOrder.vue 带着订单号跳过来）
2. 无订单号分支（pay.html 自己创建订单）

## 额外修复：JSAPI 失败后立即降级到扫码支付

### 问题

旧版 pay.html 在 JSAPI 失败后只显示错误文字，没有降级到 Native 扫码。

### 修复

```javascript
// ❌ 旧：只显示错误，不降级
} else {
    document.getElementById('status').textContent = res.msg || '下单失败';
}

// ✅ 新：错误后立即展示二维码
} else {
    document.getElementById('status').textContent = res.msg || '下单失败';
    createNativePay();  // 立即降级到扫码
}
```

## pay.html 最终架构（2026-07-18 重写）

```javascript
// 微信浏览器检测（不等 WeixinJSBridge，先检测 UA）
var isWeChat = navigator.userAgent.toLowerCase().indexOf('micromessenger') !== -1;

// JSAPI 支付初始化（自动等待 WeixinJSBridge 就绪）
function initJsapiPay() {
  if (!isWeChat || jsapiAttempted) return;
  jsapiAttempted = true;
  if (typeof WeixinJSBridge === 'undefined') {
    document.addEventListener('WeixinJSBridgeReady', function() { doJsapiPay(); }, false);
    return;
  }
  doJsapiPay();
}

// 实际调起 JSAPI
function doJsapiPay() {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', 'https://dazi.openai2000.cn/api/pay/wxpay/jsapi', true);
  xhr.setRequestHeader('Authorization', 'Bearer ' + token);
  xhr.onload = function() {
    var res = JSON.parse(xhr.responseText);
    if (res.code === 0 && res.data) {
      var params = res.data.jsapi || res.data;  // ← 关键：取 jsapi 字段
      myOrderNo = res.data.order_no || myOrderNo;
      WeixinJSBridge.invoke('getBrandWCPayRequest', params, function(r) {
        if (r.err_msg === 'get_brand_wcpay_request:ok') {
          // 成功 → 跳转确认
          location.href = 'https://dazi.openai2000.cn/api/pay/wxpay/confirm?order_no=' + encodeURIComponent(myOrderNo) + '&redirect=' + encodeURIComponent(myRedirect);
        } else {
          // 失败 → 立即降级到扫码
          createNativePay();
        }
      });
    } else {
      createNativePay();  // JSAPI 创建失败 → 立即降级
    }
  };
  xhr.onerror = function() { createNativePay(); };
  xhr.send(JSON.stringify({amount: myAmount, subject: mySubject}));
}

// PC端/降级：Native 扫码支付
function createNativePay() {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', 'https://dazi.openai2000.cn/api/pay/wxpay/native', true);
  xhr.setRequestHeader('Authorization', 'Bearer ' + token);
  xhr.onload = function() {
    var res = JSON.parse(xhr.responseText);
    if (res.code === 0 && res.data && res.data.code_url) {
      // 显示二维码
      new QRCode(document.getElementById('qrcode'), { text: res.data.code_url, width: 200, height: 200 });
      startPolling();  // 开始轮询支付状态
    }
  };
  xhr.send(JSON.stringify({order_no: myOrderNo, amount: myAmount, subject: mySubject}));
}
```

### 核心原则

1. **微信浏览器 → 先试 JSAPI，失败立即降级 Native 扫码**
2. **PC端 → 直接 Native 扫码**
3. **WeixinJSBridge 可能未就绪 → 监听 `WeixinJSBridgeReady` 事件**
4. **JSAPI 参数在 `res.data.jsapi` 不在 `res.data` 顶层**
5. **所有 JSAPI 失败路径都必须触发 `createNativePay()` 降级**
