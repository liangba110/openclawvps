---
name: wechat-payment-gateway
description: 统一支付网关(pay.openai2000.cn)对接与微信官方支付集成。任何业务系统要接入支付/JSAPI/微信支付/扫码支付时触发。含网关架构、订单前缀路由、后台配置、全链路部署坑。铁律：所有支付必须对接此网关，不另起支付。
---

# 统一支付网关对接（pay.openai2000.cn）

## 适用场景
- 任何业务系统接入微信官方支付（JSAPI 公众号内支付 / Native 扫码 / H5）
- 新项目上线支付、现有站收款码模式正规化
- 排查"微信里支付不行/拉不起/报错"类问题

## 铁律（用户 2026-08 明确要求）
**所有支付必须对接 pay.openai2000.cn 统一支付网关**（Server A 5005 微服务，`/opt/ttdazi/payment_service/`，商户号 1114539763 + 公众号 APPID wxd274e174ddadd4cb）。严禁业务系统自己实现微信 API v3 签名/下单。改动网关必须向后兼容 + 回归 ttdazi 支付链路。

## 架构（统一支付网关模式）
```
业务系统下单 → 前端跳转 https://pay.openai2000.cn/pay/hz?order_no=xxx
  → 网关页：无 openid → 微信静默授权 snsapi_base（回调 pay.openai2000.cn/pay/hz/oauth，openid 存 pay 域 cookie）
  → 网关页 fetch 业务系统 status 接口校验真实金额（防篡改，业务系统 CORS 必须放行 pay.openai2000.cn）
  → 网关调本地 /api/v1/wxpay/jsapi → wx.chooseWXPay 拉起支付（无需 wx.config，只需引入 jweixin-1.6.0.js）
  → 网关页轮询 /api/v1/wxpay/query → trade_state=SUCCESS → 跳回业务系统 ?pay=order_no
  → 微信回调 → 网关 notify（验签+AES-GCM 解密）→ 按订单前缀路由到业务系统回调 → 更新订单 + 邮件
```
支付页（授权+拉起+轮询）全部收拢到 pay 域名；业务系统只负责下单、收回调、展示结果。**网页授权域名和 JSAPI 授权目录都配 pay.openai2000.cn，不用配业务域名**。

## 网关接口清单（/api/v1/）
- `POST wxpay/jsapi` {openid, out_trade_no, amount(元), subject} → prepay 参数 {appId,timeStamp,nonceStr,package,paySign}
- `POST wxpay/native` {out_trade_no, amount, subject} → code_url（PC 扫码）
- `GET  wxpay/query?out_trade_no=` → 微信侧 trade_state（SUCCESS/NOTPAY/USERPAYING/CLOSED...）
- `POST wxpay/close` {out_trade_no} → 关未支付单（重新下单前调，防 OUT_TRADE_NO_USED）
- `POST wxpay/notify` → 微信回调（验签+解密，更新 A 库 pay_order + 按前缀路由业务回调）
- 回调鉴权：`X-Pay-Token: huizhiyun_gateway_2026`（网关 _notify_merchant 转发时带，业务系统必须校验）

## 订单前缀路由表（网关 notify 按 out_trade_no 前缀分发）
| 前缀 | 业务 | 回调地址 |
|---|---|---|
| PAY / RCH | ttdazi | https://dazi.openai2000.cn/api/pay/notify/recharge |
| TMP / SO / HY | 官网 www.openai2000.cn | https://www.openai2000.cn/api/payment/notify |

网关改路由逻辑在 `api.py wx_notify()`：SO/HY/TMP 前缀无条件转发官网，PAY 需 pay_order 表 rowcount>0 才转发（原逻辑）。

## 微信后台配置（用户操作，我无权限）
1. 公众号后台 → 功能设置 → **网页授权域名**：添加 `pay.openai2000.cn`（追加，勿删 dazi.openai2000.cn——ttdazi 在用）
2. 商户平台 → 产品中心 → JSAPI支付 → **授权目录**：添加 `https://pay.openai2000.cn/`
未配置前支付无法拉起，其他功能照常。

## 业务系统对接 checklist
1. 下单接口建订单（订单号前缀必须匹配路由表）
2. 前端：下单成功 → 微信内跳 `https://pay.openai2000.cn/pay/hz?order_no=xxx`；非微信 → 提示"请用手机微信打开"
3. 回调接口 `POST /api/payment/notify`：校验 X-Pay-Token → 按订单号更新订单表（幂等：WHERE status=0）→ 邮件通知 → 返回 200
4. 状态接口 `GET /api/payment/status/:orderNo`：前端轮询 + 支付页金额校验（CORS 放行 pay.openai2000.cn）
5. 后端 jsapi 幂等：下单前先 query 微信侧状态，SUCCESS → 本地同步已支付不重复下单；NOTPAY/USERPAYING 旧单先 close 再下单
6. 前端"已支付"判定：支付成功跳回 `?pay=order_no` → 轮询 status >= 1 → 成功页；避免重复拉起（sessionStorage 标记或直接跳网关页由网关兜底）

## 部署与验证坑（本次会话实测，条条踩过）
1. **本地改文件后 scp 漏步 = 线上旧代码**：本地 patch 了 /tmp 文件但上传时直接 ssh cp 服务器上旧的 /tmp 文件 → 线上跑旧逻辑，用户报"还是不行"。**必须闭环：改 → scp 本地最新文件到 B:/tmp → cp 到 src → 构建 → grep dist 验证新逻辑字符串存在**。
2. **SSH 嵌套引号被本地 shell 吃掉**：`ssh host "cmd && python3 - <<'EOF' ... \"no-cache\" ... EOF"` 内嵌双引号会终止外层字符串，远程收到引号丢失（nginx add_header 语法错、python 脚本 SyntaxError）。**涉及引号的远程文件修改：本地编辑 → scp 回传 → nginx -t/reload**，别用嵌套 heredoc。
3. **vite build 清空 dist → SEO 静态页全删**：构建后必须重跑 `node ../backend/seo/generate.js`（只读 DB 生成 index.seo.html/seo/*.html/sitemap）。
4. **dist 属主**：vite 需写 dist → 构建前 `chown -R ubuntu:ubuntu dist`，构建完 `chown -R www-data:www-data dist && chmod -R 755`（否则 www-data 读不了 403）。
5. **微信 WebView 缓存旧 index.html**：部署新版必须给 index.html `no-cache`（nginx `location = /index.html { add_header Cache-Control "no-cache, max-age=0"; expires 0; }`），否则微信里永远加载旧 JS，支付逻辑不变。
6. **nginx add_header 继承陷阱**：location 级有 add_header 时不继承 server 级 → HSTS/X-Frame-Options 等安全头全丢。location 内要补全安全头（Strict-Transport-Security/X-Frame-Options/X-Content-Type-Options/Referrer-Policy）。
7. **pm2 重启**：node 装在 nvm，`sudo -u ubuntu bash -c 'export PATH=/home/ubuntu/.nvm/versions/node/v22.23.0/bin:$PATH; pm2 restart huizhiyunma-api --update-env'`。
8. **CSP 放行微信 SDK**：页面引入 jweixin-1.6.0.js，CSP `script-src` 需加 `https://res.wx.qq.com`。
9. 验证纪律：全站逐页 200 + 百度 UA SEO 版 200 + 支付页无 cookie 302 微信授权（redirect_uri 指向 pay 域名）+ 带 cookie 渲染 + 伪造回调 403 + 真实订单 notify 后状态更新。

## 参考
- 📖 `references/gateway-integration-2026-08.md` — 官网(www.openai2000.cn)对接实录：代码要点、测试脚本、踩坑时间线
- 微信 API v3 签名/验签/AES-GCM 实现见网关 `/opt/ttdazi/payment_service/wxpay.py`（JSAPI/Native/H5/查询/关闭/退款/验签全套，Python urllib 实现，可作移植参考）
