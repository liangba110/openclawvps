# WeChat Pay JSAPI — WeixinJSBridge 方式

## 背景

在公众号 H5 页面（微信内置浏览器）中调起微信支付，有两种方式：

| 方式 | 依赖 | 要求 | 可靠性 |
|------|------|------|--------|
| `wx.chooseWXPay` | 微信 JS-SDK（jweixin-1.6.0.js） | JS接口安全域名 + `wx.config` 签名 | ❌ 受签名 URL 影响 |
| `WeixinJSBridge.invoke('getBrandWCPayRequest')` | 微信原生注入 | JS接口安全域名 | ✅ 更稳定 |

**结论**：优先使用 `WeixinJSBridge.invoke('getBrandWCPayRequest')`，无需加载 JS-SDK，不依赖 `wx.config`。

## 推荐架构：支付中转页

不要在主站域名上处理支付，使用独立支付子域名：

```
dazi.openai2000.cn（主站，不注册JS接口）
  → 用户点「微信支付」
    → location.href = 'https://pay.openai2000.cn/pay?token=xxx&amount=xx'
      → pay.openai2000.cn 加载支付页
        → 创建 JSAPI 订单 → 调起微信支付
          → 支付成功 → 回调后台 → 跳回主站
```

### 优点

1. 支付域名独立，微信 JS 接口安全域名只需配 `pay.openai2000.cn`
2. 主站不加载任何微信 JS-SDK，避免域名冲突
3. 支付页面可复用，多个子站共用

## APIv3 JSAPI 参数组装

### 后端支付服务生成 JSAPI 参数

```python
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64, hashlib, time

def assemble_jsapi(prepay_id: str, appid: str, private_key_pem: str) -> dict:
    nonce_str = hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
    timestamp = str(int(time.time()))
    package = 'prepay_id=' + prepay_id
    # 签名字符串
    sign_str = appid + '\n' + timestamp + '\n' + nonce_str + '\n' + package + '\n'
    # 用商户私钥 RSA-SHA256 签名
    private_key = load_pem_private_key(private_key_pem.encode(), password=None)
    sig = private_key.sign(sign_str.encode(), padding.PKCS1v15(), hashes.SHA256())
    pay_sign = base64.b64encode(sig).decode()
    return {
        'appId': appid,
        'timeStamp': timestamp,
        'nonceStr': nonce_str,
        'package': package,
        'signType': 'RSA',        # APIv3 必须用 RSA，不能用 MD5
        'paySign': pay_sign,
    }
```

### 前端调起支付

```javascript
function doPay(jsapi) {
  WeixinJSBridge.invoke('getBrandWCPayRequest', {
    appId: jsapi.appId,
    timeStamp: jsapi.timeStamp,
    nonceStr: jsapi.nonceStr,
    package: jsapi.package,
    signType: jsapi.signType || 'RSA',
    paySign: jsapi.paySign
  }, function(res) {
    if (res.err_msg === 'get_brand_wcpay_request:ok') {
      // 支付成功
    } else {
      // 支付取消或失败
    }
  });
}
```

### WeixinJSBridge 就绪检测

```javascript
if (typeof WeixinJSBridge === 'undefined') {
  document.addEventListener('WeixinJSBridgeReady', function() {
    doPay(jsapi);
  }, false);
} else {
  doPay(jsapi);
}
```

## APIv3 vs APIv2 差异

| 项目 | APIv2 | APIv3 |
|------|-------|-------|
| 签名算法 | MD5 | RSA-SHA256 |
| signType | MD5 | RSA |
| 私钥文件 | 不适用 | apiclient_key.pem |
| 签名内容 | `appId\nnonceStr\npackage\ntimeStamp`（不同顺序） | `appId\n\ntimeStamp\nnonceStr\npackage\n` |
| 参数大小写 | `timeStamp` | `timeStamp`（APIv3 文档写 `time_stamp` 但 JS-SDK 需 `timeStamp`） |

## `wx.chooseWXPay` 方式（不推荐但备选）

如果必须使用 JS-SDK 方式：

```javascript
// 1. 加载 JS-SDK
<script src="https://res.wx.qq.com/open/js/jweixin-1.6.0.js"></script>

// 2. 配置（URL 必须与当前页面完全一致，不含#及其后部分）
const currentUrl = window.location.href.split('#')[0];
const res = await api.get('/wechat/config?url=' + encodeURIComponent(currentUrl));
wx.config({
  debug: false,
  appId: res.data.appId,
  timestamp: String(res.data.timestamp),
  nonceStr: res.data.nonceStr,
  signature: res.data.signature,
  jsApiList: ['chooseWXPay']
});

// 3. 调起支付
wx.ready(function() {
  wx.chooseWXPay({
    appId: 'wx...',  // ⚠️ 新版 JS-SDK 需要 appId 参数
    timestamp: String(jsapi.timeStamp),
    nonceStr: jsapi.nonceStr,
    package: jsapi.package,
    signType: 'RSA',
    paySign: jsapi.paySign,
    success: function(res) { },
    fail: function(err) { }
  });
});
```

### 常见错误

- **当前页面的url未注册**：当前域名未添加 JS接口安全域名
- **调用支付jsapi缺少参数appid**：新版 JS-SDK `chooseWXPay` 需要 `appId` 参数（从 `wx.config` 继承的版本不需要）
- **微信支付加载中**：`wx.ready` 未触发或 `wx.config` 签名失败

## 支付回调通知

支付服务确认支付后，通过 `_notify_merchant` 调用商户回调 URL：

```python
# 在 payment_service/api.py 中
def _notify_merchant(order_no, merchant, amount):
    callback_url = merchant.get('callback_url', '')
    if not callback_url:
        callback_url = 'https://dazi.openai2000.cn/api/pay/notify/recharge'
    payload = json.dumps({'order_no': order_no, 'amount': float(amount), 'status': 1})
    # POST 到回调 URL
```

后台充值回调处理（`notify_recharge`）：
1. 更新 `recharge` 表 `status=1`
2. 增加 `user.balance`
3. 写入 `money_log` 财务流水
