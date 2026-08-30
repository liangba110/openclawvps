# WeChat Pay Notification Handler

## 位置

`/opt/ttdazi/payment_service/api.py` → `@pay_api.route('/wxpay/notify')`

## 触发方式

微信支付在用户支付成功后，异步 POST 通知到 `WX_NOTIFY_URL`（配置在 `/opt/ttdazi/payment_service/wxpay.py`）：

```python
WX_NOTIFY_URL = 'https://pay.openai2000.cn/api/v1/wxpay/notify'
```

这个 URL 在每次创建 JSAPI/Native/H5 支付订单时作为 `notify_url` 参数传给微信支付。

## 处理流程

```
微信支付 → POST /wxpay/notify (XML格式)
  1. verify_notify(headers, body) → 验证签名
  2. 解析 JSON body 中的 event_type
  3. event_type == 'TRANSACTION.SUCCESS':
     a. AES-GCM 解密 resource.ciphertext → 获取 out_trade_no + trade_state
     b. trade_state == 'SUCCESS' → 更新 pay_order SET status=1
     c. 调用 _notify_merchant → POST https://dazi.openai2000.cn/api/pay/notify/recharge
  4. 返回 <xml><return_code>SUCCESS</return_code></xml>
```

## 注意事项

- 通知格式是 **JSON**（APIv3 使用 JSON 而非旧版 XML）
- 解密使用 APIv3 密钥（`WX_API_KEY_V3`）做 AES-256-GCM
- 需要 `cryptography` 库支持
- 签名验证使用 `wxpay.verify_notify()`，基于商户证书私钥
- 解密失败可能原因：APIv3 密钥不正确、ciphertext 被截断、associated_data 不匹配
- `_notify_merchant` 使用硬编码回调地址 `https://dazi.openai2000.cn/api/pay/notify/recharge`
