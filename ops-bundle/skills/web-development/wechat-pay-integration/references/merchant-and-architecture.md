# 商户配置与支付架构（2026-08 实测）

## 商户/公众号配置（用户公司，可跨站点复用）
| 项 | 值 |
|---|---|
| 公众号 APPID | `wxd274e174ddadd4cb`（服务号） |
| 公众号 Secret | `cfcb63c13fa5cfbb37316c83f51384a9` |
| 商户号 MCHID | `1114539763` |
| API v3 密钥 | 见 A 服务器 `/opt/ttdazi/payment_service/wxpay.py` 的 `WX_API_KEY_V3` |
| 商户证书 | A 服务器 `/opt/ttdazi/payment_service/certs/`（apiclient_key.pem / apiclient_cert.pem / wx_platform_cert.pem） |
| 公众号 Token | `huizhiyun_ttdazi_2026`，明文，URL `https://dazi.openai2000.cn/api/wechat/message` |

## ttdazi 支付微服务架构（生产参考，新站接入前先摸清）
```
Server A: /opt/ttdazi/payment_service/ (Flask, 127.0.0.1:5005, gunicorn 多 worker)
  wxpay.py           — API v3 全实现（签名/JSAPI/Native/H5/查询/关闭/退款/回调验签）
  jsapi_pay_endpoint.py — POST /api/v1/wxpay/jsapi（openid+out_trade_no+amount+subject → prepay 参数）
                        POST /api/v1/wxpay/native（扫码下单 → code_url）
  api.py             — /api/v1/wxpay/notify（验签→AES-GCM 解密→更新 pay_order→_notify_merchant 回调业务方）
  config.py          — 库连接（huizhiyun 库，root/huizhiyun2026）
  app.py /pay        — 微信内支付中转页（token+amount+order_no）
入口：微信回调 → pay.openai2000.cn:443 (Caddy) → 127.0.0.1:5005 回环（5005 不对外，防火墙只放 B/E 来源）
业务方回调：_notify_merchant → https://dazi.openai2000.cn/api/pay/notify/recharge（ttdazi 充值/订单更新）
```

## 回调通知的写法（wxpay.py 内实现，port 时注意）
- 验签 headers：`Wechatpay-Timestamp / Wechatpay-Nonce / Wechatpay-Signature / Wechatpay-Serial`
- 用本地缓存的平台证书 `certs/wx_platform_cert.pem` 公钥验签（生产要处理平台证书轮换，可用下载接口）
- 解密 resource：`key=API v3 密钥`，AES-256-GCM，nonce=resource.nonce，tag=密文末 16 字节，associated_data=resource.associated_data
- 成功更新订单后返回 `200 <xml><return_code>SUCCESS</return_code></xml>`；验签失败返回 400 FAIL

## 官网（www.openai2000.cn，huizhiyunma）现状（2026-08 调研）
- 后端 Node/Express：Server B `/data/web/huizhiyunma/backend/server.js`(:8081)，pm2 或直接 node 起
  - 前端源码在 `/data/web/huizhiyunma/frontend/src`（vite 构建，可重新 build），dist 在 frontend/dist
  - 库 `huizhiyunma_db`，应用账号 `huizhiyunma`（密码在 backend/.env，含特殊字符，shell 转义易踩坑——用 node -e + dotenv 读库最稳）
  - 表：`payment_orders`（HY 前缀，通用支付单：title/amount/customer_*/status/proof_image/pay_method/paid_at）、`package_orders`（SO 前缀，套餐业务单：package_id/package_name/price/name/phone/status）
  - `routes/payment.js`：POST / 建单 → POST /:orderNo/proof 上传凭证（status 0→1）→ 管理端人工确认（现状=非正规收款码模式）
  - 前端支付：付款弹层展示「微信收款码链接」（site_config payment_wechat_qr）+ 上传凭证，付款提示"扫码支付 ¥xx"
- 目标改造（JSAPI 正规化）：套餐下单 → OAuth 静默授权 → 后端 JSAPI 下单 → wx.chooseWXPay → 回调 `/api/payment/notify`（现 /api/ 反代已覆盖 8081，无需改 nginx）→ payment_orders.status=2 + package_orders.status=1

## 排查/踩坑记录
- 服务器上 node 不在 sudo PATH：用绝对路径 `/home/ubuntu/.nvm/versions/node/v22.23.0/bin/node`
- 读库用 `node -e` + 项目内 mysql2 + dotenv，避免 shell 引号转义密码（实测多次踩坑）
- 支付接口测试要先确认微信侧配置（网页授权域名/授权目录）就绪，否则下单/拉起必失败
