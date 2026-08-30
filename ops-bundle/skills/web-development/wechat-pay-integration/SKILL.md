---
name: wechat-pay-integration
description: 微信支付对接（统一支付网关 pay.openai2000.cn）。Native扫码(网站直接显示二维码,默认首选)/JSAPI(微信内拉起)/H5,回调按订单前缀路由,官网Node对接模式,微信后台配置,排查"支付不行"。当需要给站点接微信官方支付、用户说"网站上扫码支付/支付对接不对/支付不行"、排查下单/回调/验签失败、替换收款码人工确认模式时触发。
---

# 微信支付 API v3 接入

## 适用场景
- 新站点/官网接入微信官方支付（商户版），消除「收款码+上传凭证+人工确认」的非正规模式（资金风险+体验差）
- 排查微信支付下单 / 回调验签 / 解密失败
- 同一商户号给多个站点服务（本项目：ttdazi 已接入，官网/国际站后续复用）
- 用户说"网站上扫码支付 / 支付对接不对 / 支付还是不行"——先确认要的是哪种支付形态（见下节）

## 支付形态选择 — 先问清用户场景（2026-08 官网接入两次纠偏的教训）⚠️
- **Native 扫码（默认首选，本项目官网最终落地形态）**：网站页面直接显示二维码，用户手机微信扫一扫支付。PC/手机浏览器/微信内**全场景通用**，且**零微信后台配置**（商户号开通 Native 产品即可，无需网页授权域名/授权目录）。用户说"在网站上扫码支付/网站上直接显示二维码" = 就是这个
- **JSAPI（微信内拉起）**：微信内置浏览器 `wx.chooseWXPay` 弹支付面板。**必须**公众号网页授权域名 + 商户平台 JSAPI 授权目录（均无 API，需用户登录后台手动追加配置；且是**追加**勿覆盖已有 dazi.openai2000.cn）。仅适合确定用户都在微信内付款的场景
- 用户笼统说"对接微信支付"时**默认 Native**；不要先做 JSAPI（本会话先做 JSAPI 被用户两次纠正"不对，要网站上扫码支付"）

## 已验证可用的生产实现（优先复用，别重写）⚠️
- **ttdazi 支付微服务**：Server A `/opt/ttdazi/payment_service/`（Flask，绑 127.0.0.1:5005，Caddy 443→回环）
  - `wxpay.py`：完整 API v3 实现（认证签名/JSAPI/Native/H5/查询/关闭/退款/回调验签）— 见 `templates/wxpay_api_v3.py`
  - `jsapi_pay_endpoint.py`：JSAPI 下单端点（含前端 paySign 生成）
  - `app.py` `/pay`：微信内支付中转页（token+amount+order_no 参数）
  - `certs/`：apiclient_key.pem / apiclient_cert.pem / wx_platform_cert.pem
- 商户配置与架构细节见 📖 `references/merchant-and-architecture.md`

## JSAPI 支付完整流程（公众号内）
1. 用户微信内打开 → 选商品/套餐 → 后端建业务订单（状态=待支付）
2. **OAuth 静默授权拿 openid**（scope=snsapi_base，用户无感）：
   ```
   https://open.weixin.qq.com/connect/oauth2/authorize?appid=APPID&redirect_uri=<回调>&response_type=code&scope=snsapi_base&state=<订单号>#wechat_redirect
   ```
   回调拿 code 换 openid：`GET https://api.weixin.qq.com/sns/oauth2/access_token?appid=&secret=&code=&grant_type=authorization_code`
3. 后端调 `POST /v3/pay/transactions/jsapi`：
   ```json
   {"appid": "...", "mchid": "...", "description": "商品名(≤32字)", "out_trade_no": "...",
    "notify_url": "https://<本站域名>/api/payment/notify",
    "amount": {"total": <分>, "currency": "CNY"}, "payer": {"openid": "..."}}
   ```
4. 返回 `prepay_id` → 组装前端参数：`appId / timeStamp / nonceStr / package=prepay_id=xxx / signType=RSA / paySign`
   - paySign = 商户私钥 RSA-SHA256 签 `appId\n时间戳\nnonceStr\npackage\n`
5. 前端 `wx.chooseWXPay({...})` 拉起支付 → 微信异步回调 notify_url
6. 回调处理：**验签（平台证书）→ AES-256-GCM 解密 resource → trade_state==SUCCESS → 更新订单 → 返回 XML `SUCCESS`**（失败返回非 SUCCESS 让微信重试）

## API v3 签名与回调要点
- Authorization 头：`WECHATPAY2-SHA256-RSA2048 mchid="...",nonce_str="...",serial_no="商户证书序列号",signature="...",timestamp="..."`
- 签名串：`METHOD\nURL_PATH\nTIMESTAMP\nNONCE\nBODY\n`，商户私钥 PKCS1v15+SHA256
- 证书序列号：`openssl x509 -in apiclient_cert.pem -noout -serial`
- 回调验签：平台证书公钥验 `TIMESTAMP\nNONCE\nBODY\n`（生产应缓存平台证书并处理轮换）
- 回调解密：key=API v3 密钥，`AES-256-GCM`，nonce=resource.nonce，tag=密文最后 16 字节，associated_data=resource.associated_data
- 金额单位：**元→分**（`int(float(amount)*100)`）
- 回调必须幂等：按订单号+状态判断，重复通知不重复入账

## 统一支付网关回调路由（网关 notify 按订单前缀分发业务回调）⚠️
- 网关（A:5005，systemd `ttdazi-pay`）微信回调验签+解密后，按 `out_trade_no` 前缀路由 `_notify_merchant`（异步 POST JSON `{order_no,amount,status,timestamp}`，带 `X-Pay-Token: huizhiyun_gateway_2026` 头）：
  - `TMP`(官网模板商城, pay_system_db.template_orders) / `SO`(官网套餐, huizhiyunma_db.package_orders) / `HY`(官网通用, huizhiyunma_db.payment_orders) → `https://www.openai2000.cn/api/payment/notify`
  - `PAY`/`RCH`(ttdazi) → `https://dazi.openai2000.cn/api/pay/notify/recharge`
- 改网关 notify 必须向后兼容：`PAY` 分支保持原逻辑（pay_order 表 rowcount>0 才通知），`TMP/SO/HY` 分支无条件通知官网
- 网关还有 `/wxpay/close`（关单，业务系统重新下单前调用防 out_trade_no 重复）、`/wxpay/query`

## 官网 Native 扫码对接模式（已落地，2026-08）✅
1. **下单接口** `POST /api/payment/native {order_no}`（Node/Express，B:8081）：
   - resolveOrder 按前缀选库表 → 校验 status=0、金额>0
   - 先 `GET /api/v1/wxpay/query` 查微信侧：SUCCESS→本地同步已支付返回 `{already_paid:true}`（防重复下单/已支付未同步）；NOTPAY/USERPAYING→先 `POST /api/v1/wxpay/close` 再下单
   - 调网关 native（amount 传元，网关内 *100 转分）→ 后端 `qrcode` npm 包生成 `qr_data_url`(dataURL) → 前端 `<img :src>` 显示（零外部依赖，不受 CSP 限制）
2. **回调接口** `POST /api/payment/notify`：校验 X-Pay-Token → 按前缀更新对应表（template_orders 0→1+paid_at / package_orders 0→1 / payment_orders 0→2，WHERE status=0 幂等）→ mailer.sendNotify 邮件
3. **前端**：下单成功弹窗显示二维码 + 2s 轮询 `/api/payment/status/:orderNo`（status>=1 跳成功页）+ 刷新二维码按钮
4. **CORS**：官网 allowedOrigins 需含 `https://pay.openai2000.cn`
5. jsapi 接口（如保留）同样先 query 幂等再下单

## 商户配置（无开放 API，必须用户后台手动操作）⚠️
1. **网页授权域名**：mp.weixin.qq.com → 设置与开发 → 公众号设置 → 功能设置（拿 openid 必需；**每个要接支付的站点域名都要加**）
2. **JSAPI 支付授权目录**：pay.weixin.qq.com → 产品中心 → JSAPI支付（发起支付的页面 URL 必须在授权目录下；**每站点加自己的目录**）
3. APPID 与商户号绑定、JSAPI 产品开通：首次配置一次；已在用的 APPID/商户对可直接复用
4. 这两步配好前支付拉不起来（其余功能照常）——接入时提前告知用户并行操作

## 接入纪律（本项目铁律，2026-08 官网接入时确立）
- **同一商户号可服务多个站点**：`notify_url` 是下单参数，每个站点用**自己的回调域名** → 各站点订单独立闭环
- **新站点接入严禁改动现有支付链路**（ttdazi 的 5005/回调/订单表）：商户证书复制副本、独立回调、独立订单表，零影响
- 回调 URL 若走现成 `/api/` 反代则不用改 nginx（官网 Node 8081 就是 `/api/` 通配反代）
- 商户私钥权限 600、绝不落日志；新接入前先复述方案给用户确认（涉及真实资金）
- **支付形态先问清**：用户要"网站扫码"就是 Native（页面显示二维码），不是 JSAPI 拉起

## 现有支付模块调研速查（接新站前先摸清）
- 官网（www.openai2000.cn，huizhiyunma）：Node/Express，B 服务器 `backend/server.js`(:8081)，库 `huizhiyunma_db`，表 `payment_orders`(HY 前缀通用支付单) + `package_orders`(SO 前缀业务单) + 模板订单在独立库 pay_system_db（`pay_system` 用户访问，主库用户无权）；`routes/payment.js` 已落地 Native 扫码（`/native` + `/notify` + `/status/:orderNo`），**原收款码+凭证人工确认已废弃**（后端保留 `/proof` 作管理员兜底）
- 官网支付 CORS 已放行 `https://pay.openai2000.cn`；index.html 已配 no-cache（防微信 WebView 缓存旧版支付逻辑）
- ttdazi：Python/Flask 5005（见 references）
- 支付商品备注统一「广告信息展示服务」（合规口径，见 memory）

## 验证纪律（官网 Native 链路）
- 接口级：建 0.01 元 HY 测试订单 → native 下单返回 `weixin://wxpay/bizpayurl?pr=...` + qr_data_url(PNG) → 伪造 notify 无 token 应 403 → 带 token 订单更新 → **测试订单必须清理**（模板订单在 pay_system_db 用 pay_system 用户删；主库用应用账号）
- 页面级：浏览器实测完整走 下单→二维码显示（browser 工具；购买弹窗 Teleport 在快照底部，卡片点击用 `document.querySelector('.tpl-card').click()`，表单用 browser_type）
- 真实支付：需用户微信扫码；验证 支付→网关回调→官网订单更新→邮件
- 用户报"还是不行"排查顺序：①线上 dist 是否含新逻辑（`grep 新关键字 dist/assets/*.js`）②微信 WebView 缓存旧 index.html（nginx 必须 no-cache）③JSAPI 场景授权域名/目录是否配置且为追加
