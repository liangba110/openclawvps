# 独立支付微服务

## 架构

```
pay.openai2000.cn (HTTPS 443)
      ↓
  Caddy（自动 Let's Encrypt 证书）
      ↓
  Flask 支付服务 (127.0.0.1:5005, gunicorn 2 workers)
      ↓
  MySQL（huizhiyun 数据库 pay_* 表）
```

## 部署位置

- **代码路径**: `/opt/ttdazi/payment_service/`
- **系统服务**: `ttdazi-pay.service` (systemd, 开机自启)
- **域名**: `pay.openai2000.cn` → Caddy 反向代理到 `127.0.0.1:5005`
- **Caddyfile**: `/etc/caddy/Caddyfile` — 添加 `pay.openai2000.cn { reverse_proxy 127.0.0.1:5005 }`
- **Python 依赖**: flask, flask-REDACTED, pymysql, gunicorn

## 数据库表

### pay_merchant（商户表）
支持多商户。每站独立 api_key/api_secret/余额。

### pay_order（支付订单表）
订单号: `PAY+YYYYMMDDHHmmss+6位随机`。status: 0待付 1已付 2已退 3关闭。

### pay_transaction（资金流水表）
type: pay/refund/recharge/transfer，记余额变动前后。

## API 接口

| 端点 | 方法 | 签名 | 说明 |
|------|------|------|------|
| /api/v1/pay | POST | ✅ | 创建订单（幂等防重） |
| /api/v1/confirm | POST | ✅ | 确认扣款（行锁+回调） |
| /api/v1/query | GET | ❌ | 查询订单 |
| /api/v1/refund | POST | ✅ | 退款（仅退已支付订单） |
| /api/v1/balance | GET | ❌ | 商户余额 |
| /api/v1/recharge | POST | ❌ | 充值（需 admin_key） |

### 签名算法
```python
items = sorted((k,v) for k,v in data.items() if k not in ('sign','api_key'))
s = '&'.join(f'{k}={v}' for k,v in items)
return hashlib.md5((s + secret).encode()).hexdigest()
```
排除 `sign` 和 `api_key`，按 key 排序后拼 secret 做 MD5。

## 前端测试页面

地址: `https://pay.openai2000.cn/test`
6 个测试模块（创建/查询/确认/退款/充值/余额）。
POST 端点通过 `/api/v1/test/<action>` 代理自动签名。

## 默认商户

| api_key | api_secret | admin_key |
|---------|-----------|-----------|
| ttdazi_pay_key_2026 | ttdazi_pay_secret_2026 | pay_admin_2026 |

## 集成 (pay_client.py)

`/opt/ttdazi/backend/app/pay_client.py` — 封装所有调用。
所有调用 try/except pass，支付服务不可用不影响主流程。

| 文件 | 触发 | 同步 |
|------|------|------|
| order.py pay() | 用户支付 | create + confirm |
| wallet_api.py recharge() | 充值 | create + confirm |
| playmate_api.py withdraw() | 提现申请 | create only |

## 运维

```bash
sudo systemctl restart|status ttdazi-pay
sudo journalctl -u ttdazi-pay -n 50
sudo systemctl reload caddy
curl -sk https://pay.openai2000.cn/health
```

## 微信支付集成

### 配置参数

| 参数 | 值 | 来源 |
|------|-----|------|
| 商户号 (MCH_ID) | 1114539763 | 微信商户平台 |
| 公众号 APPID | wxd274e174ddadd4cb | 微信公众平台 |
| APIv3 密钥 | 32位，商户平台设置 | 商户平台→API安全 |
| 商户证书 | apiclient_key.pem + apiclient_cert.pem | 商户平台下载 |
| PUB_KEY_ID | 公钥模式标识 | 上传公钥后返回 |

### 证书路径

```
/opt/ttdazi/payment_service/certs/
├── apiclient_cert.p12       # PKCS12证书包
├── apiclient_cert.pem       # 商户证书（公钥）
├── apiclient_key.pem        # 商户私钥（签名请求）
├── private_key.pem          # 备用私钥
├── public_key.pem           # 备用公钥（上传到微信平台）
└── wx_platform_cert.pem     # 微信平台证书（验证回调）
```

### 用户侧配置

1. **微信商户平台 → 账户中心 → API安全**
   - APIv3密钥：设置32位密钥
   - 公钥管理：上传服务器生成的公钥 → 获取 PUB_KEY_ID
   - 证书管理：下载商户证书

2. **微信商户平台 → 产品中心**
   - 开通 JSAPI支付 / Native支付 / H5支付

3. **微信商户平台 → 产品中心 → 开发配置**
   - JSAPI支付授权目录：`https://pay.openai2000.cn/`
   - Native支付回调链接：`https://pay.openai2000.cn/`

### API 接口

| 端点 | 功能 | 说明 |
|------|------|------|
| POST /api/v1/wxpay/native | Native扫码支付 | 返回 code_url，生成二维码 |
| POST /api/v1/wxpay/jsapi | JSAPI公众号支付 | 需用户openid |
| POST /api/v1/wxpay/refund | 退款 | 金额单位分 |
| GET /api/v1/wxpay/query | 查询订单 | 返回微信侧状态 |

### WeChat Pay APIv3 签名

```python
# 认证 Token 格式
WECHATPAY2-SHA256-RSA2048 mchid="1114539763",nonce_str="...",
serial_no="证书序列号",signature="base64(sha256rsa签名)",timestamp="..."
```

- 使用 `apiclient_key.pem` 对请求体做 RSA-SHA256 签名
- serial_no 从 `apiclient_cert.pem` 中 `openssl x509 -noout -serial` 读取
- Python 依赖: `cryptography` 包

### IP 白名单

微信商户平台 → 账户中心 → API安全 → **IP白名单**
必须添加服务器 IP: `42.193.113.230`，否则返回 403。

### 错误排查

- `HTTP Error 403: Forbidden` → 检查IP白名单、APIv3密钥、证书有效期
- `HTTP Error 400: Bad Request` → 订单不存在或参数错误
- `trade_state: NOTPAY` → 正常，等待用户扫码支付

## 🔴 注意

**iptables 规则重启丢失** — 本机默认 DROP 策略：
```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5005 -j ACCEPT
# 持久化:
sudo apt install -y iptables-persistent && sudo netfilter-persistent save
```

**MySQL DECIMAL + float 不兼容** — 读取后立即 `float()`:
```python
old_balance = float(m['balance'])
new_balance = old_balance - float(order['amount'])
```
