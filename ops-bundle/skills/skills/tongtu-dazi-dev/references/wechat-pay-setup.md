# 微信支付配置指南

## 需要的资料

| 参数 | 来源 | 本例值 |
|------|------|--------|
| MCH_ID (商户号) | 微信商户平台 → 账户中心 | 1114539763 |
| APPID | 公众号/小程序 → 开发 → 基本配置 | wxd274e174ddadd4cb |
| APIv3 密钥 | 微信商户平台 → API安全 → APIv3密钥 | 32位字母数字 |
| 商户证书 | 微信商户平台 → API安全 → API证书 → 下载 | apiclient_cert.pem + apiclient_key.pem |

## 证书获取

1. 登录 [pay.weixin.qq.com](https://pay.weixin.qq.com/)
2. 账户中心 → API安全 → API证书 → 下载证书
3. 解压得到：`apiclient_cert.pem`（证书）、`apiclient_key.pem`（私钥）、`apiclient_cert.p12`

## 公钥模式（替代证书）

如果不能下载证书，可用公钥模式：

```bash
# 1. 在服务器生成 RSA 密钥对
mkdir -p /opt/ttdazi/payment_service/certs
cd /opt/ttdazi/payment_service/certs
openssl genrsa -out private_key.pem 2048
openssl rsa -in private_key.pem -pubout -out public_key.pem

# 2. 把 public_key.pem 内容上传到微信商户平台
#    账户中心 → API安全 → 公钥管理
cat public_key.pem

# 3. 上传后微信返回 PUB_KEY_ID_xxxxxxxxxxxx
#    配置到支付服务
```

## 文件位置

```
/opt/ttdazi/payment_service/
├── wxpay.py              # 微信支付 SDK（APIv3 签名+请求）
├── certs/
│   ├── apiclient_cert.pem  # 商户证书
│   ├── apiclient_key.pem   # 商户私钥
│   ├── private_key.pem     # RSA 私钥（公钥模式用）
│   ├── public_key.pem      # RSA 公钥（公钥模式用）
│   └── wx_platform_cert.pem # 微信平台证书（验证回调用）
```

## API 端点

| 端点 | 说明 |
|------|------|
| `/api/v1/wxpay/jsapi` | JSAPI（公众号内支付）需 openid |
| `/api/v1/wxpay/native` | Native（扫码支付）返回 code_url |
| `/api/v1/wxpay/h5` | H5（手机浏览器）返回 h5_url |
| `/api/v1/wxpay/query` | 查询订单 |
| `/api/v1/wxpay/refund` | 退款 |

## APIv3 签名机制

```python
# 核心：使用商户私钥做 SHA256-RSA 签名
message = f'{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n'

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

private_key = serialization.load_pem_private_key(key_pem, password=None)
signature = private_key.sign(
    message.encode(), padding.PKCS1v15(), hashes.SHA256())

# Token 格式
token = (
    f'WECHATPAY2-SHA256-RSA2048 '
    f'mchid="{mchid}",nonce_str="{nonce}",'
    f'serial_no="{serial}",signature="{b64_sig}",'
    f'timestamp="{ts}"'
)
```

## 常见问题

### 🔴 403 Forbidden

**可能原因**：
1. IP 白名单未添加 — 微信商户平台 → API安全 → 添加 `42.193.113.230`
2. 商户号未开通支付产品 — 产品中心 → JSAPI/Native/H5 支付
3. APIv3 密钥不匹配 — 检查密钥是否正确设置
4. 证书序列号不匹配 — 确认使用的 apiclient_cert.pem 是最新下载的

**排查**：
```bash
# 验证证书和私钥匹配
openssl x509 -in apiclient_cert.pem -noout -modulus | md5sum
openssl rsa -in apiclient_key.pem -noout -modulus | md5sum

# 查看证书序列号
openssl x509 -in apiclient_cert.pem -noout -serial
```

### 🔴 证书过期

证书有效期 5 年，到期前需在微信商户平台重新下载并更新。
