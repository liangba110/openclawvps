# 微信 JSAPI 支付：WeixinJSBridge 调起方案

## 问题背景
`wx.chooseWXPay` 依赖 `wx.config` + `wx.ready`，需要加载 JS-SDK、获取签名、配置后等待 ready。实际使用中频繁遇到「缺少参数appId」「微信支付加载中」等问题。

## 解决方案：WeixinJSBridge.invoke('getBrandWCPayRequest')
微信内置浏览器原生提供 `WeixinJSBridge` 对象，不依赖外部 JS-SDK 加载：

```javascript
function doWxPay(jsapi) {
  WeixinJSBridge.invoke('getBrandWCPayRequest', {
    appId: 'wxd274e174ddadd4cb',
    timeStamp: jsapi.timeStamp,
    nonceStr: jsapi.nonceStr,
    package: jsapi.package,
    signType: jsapi.signType || 'RSA',
    paySign: jsapi.paySign
  }, (res) => {
    if (res.err_msg === 'get_brand_wcpay_request:ok') {
      // 支付成功
    } else {
      // 支付取消或失败
    }
  })
}
```

### WeixinJSBridge 未就绪处理
```javascript
if (typeof WeixinJSBridge === 'undefined') {
  document.addEventListener('WeixinJSBridgeReady', () => doWxPay(jsapi), false)
} else {
  doWxPay(jsapi)
}
```

## 后端 JSAPI 参数组装（APIv3 RSA 签名）
```python
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64, hashlib, time

def build_jsapi_params(prepay_id, appid, private_key_pem):
    nonce_str = hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
    timestamp = str(int(time.time()))
    package_val = 'prepay_id=' + prepay_id
    sign_str = appid + '\n' + timestamp + '\n' + nonce_str + '\n' + package_val + '\n'
    private_key = load_pem_private_key(private_key_pem.encode(), password=None)
    sig = private_key.sign(sign_str.encode(), padding.PKCS1v15(), hashes.SHA256())
    pay_sign = base64.b64encode(sig).decode()
    return {'appId': appid, 'timeStamp': timestamp, 'nonceStr': nonce_str, 'package': package_val, 'signType': 'RSA', 'paySign': pay_sign}
```

## 支付域名跳转模式（推荐方案，避免 JS 接口安全域名问题）

最可靠的方案是 **不在主域名上做 JSAPI 支付，而是跳转到独立的支付域名**：

### 流程
1. 用户在 `dazi.openai2000.cn` 下单
2. 前端跳转 `https://pay.openai2000.cn/pay?token=xxx&amount=30`
3. pay.openai2000.cn 的页面使用 WeixinJSBridge 直接调起支付
4. 支付成功后回调通知 `dazi.openai2000.cn/api/pay/notify/recharge`
5. 前端点「返回」跳回主站

### 优势
- **JS接口安全域名**只需添加 `pay.openai2000.cn`（支付专用域名），不影响主站
- 无需在主站加载微信 JS-SDK 或配置 `wx.config`
- `WeixinJSBridge` 原生可用，无需等待 SDK 加载
- 支付页面和主站解耦，互不影响

### pay.openai2000.cn 支付页面模板

```html
<!-- pay.openai2000.cn/pay?token=xxx&amount=30 -->
<script>
// 页面load后自动创建订单并调起支付
window.onload = function() {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', 'https://dazi.openai2000.cn/api/pay/wxpay/jsapi', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.setRequestHeader('Authorization', 'Bearer ' + token);
  xhr.onload = function() {
    var res = JSON.parse(xhr.responseText);
    if (res.code === 0 && res.data && res.data.jsapi) {
      orderData = res.data.jsapi;
      // 用户点「确认支付」后
      WeixinJSBridge.invoke('getBrandWCPayRequest', {
        appId: 'wxd274e174ddadd4cb',
        timeStamp: orderData.timeStamp,
        nonceStr: orderData.nonceStr,
        package: orderData.package,
        signType: orderData.signType || 'RSA',
        paySign: orderData.paySign
      }, function(res) {
        if (res.err_msg === 'get_brand_wcpay_request:ok') {
          // 通知后端充值成功
          fetch('https://dazi.openai2000.cn/api/pay/notify/recharge', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({order_no: orderNo, status: 1, amount: amount})
          });
        }
      });
    }
  };
  xhr.send(JSON.stringify({amount: amount}));
};
</script>
```

## 关键注意点
1. **appId 前端硬编码**，不要从 API 响应读取
2. **wx.chooseWXPay vs WeixinJSBridge**：后者原生可用更可靠
3. **JSAPI 需要 wx_openid**：用户必须先微信 OAuth 登录
4. **Native 支付不需要 wx_openid**
5. **签名不匹配**：JSAPI 签名与 wx.config 签名（ticket）不同
6. **pay.openai2000.cn 回调通知** → 更新 recharge 表 → 加余额 → money_log
