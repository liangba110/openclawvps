# 官网(www.openai2000.cn)对接统一支付网关实录（2026-08-07）

## 背景
官网原为"收款码+上传凭证+人工确认"模式（payment_orders/proof 接口），非正规。改造为微信官方 JSAPI 支付，全程走 pay.openai2000.cn 网关。

## 网关侧改动（/opt/ttdazi/payment_service/）
1. `api.py wx_notify()`：微信回调解包后按订单前缀路由业务回调——
   ```python
   if out_trade_no[:3] in ('TMP',) or out_trade_no[:2] in ('SO', 'HY'):
       _notify_merchant(out_trade_no, {'callback_url': 'https://www.openai2000.cn/api/payment/notify'}, amount_yuan)
   elif updated > 0:  # 原逻辑：pay_order 表更新成功才通知 ttdazi
       _notify_merchant(out_trade_no, {'callback_url': 'https://dazi.openai2000.cn/api/pay/notify/recharge'}, amount_yuan)
   ```
2. `_notify_merchant()` 加鉴权头：`headers={'X-Pay-Token': 'huizhiyun_gateway_2026'}`
3. 新增 `POST /api/v1/wxpay/close`（api.py wx_close，调 wxpay.close_order）
4. `app.py` 新增支付中转页：
   - `GET /pay/hz?order_no=xxx`：无 pay_openid cookie → 302 微信授权（redirect_uri=`https://pay.openai2000.cn/pay/hz/oauth`，snsapi_base）；有 → 渲染 PAY_HZ_HTML（注入 ORDER_NO/OPENID/SUBJECT_PREFIX/RETURN_URL）
   - `GET /pay/hz/oauth?code&state`：code 换 openid → Set-Cookie pay_openid (HttpOnly, 2h, secure) → 302 回 /pay/hz
   - 订单前缀决定描述与回跳：SO→`AI建站服务：`+跳 /packages?pay=；TMP/HY→`模板购买：`+跳 /templates?pay=
   - 页面 JS：fetch 官网 status 校验金额（防篡改）→ POST 本地 /api/v1/wxpay/jsapi → wx.chooseWXPay → 轮询 query → SUCCESS 跳 RETURN_URL
   - 微信 JS-SDK 用 `https://res.wx.qq.com/open/js/jweixin-1.6.0.js`，chooseWXPay **不需要 wx.config**

## 官网侧改动（Server B /data/web/huizhiyunma/）
- `backend/routes/payment.js`（重写，保留原收款码接口作管理员兜底）：
  - `resolveOrder(order_no)` 按前缀映射表/库/状态字段：TMP→payPool.template_orders(paid_at有)，SO→pool.package_orders(**无 paid_at 列**，SELECT 要动态拼)，HY→pool.payment_orders(status 0→2)
  - `POST /jsapi`：cookie hz_openid 无→`{code:-1, oauth:true}`；先 query 微信侧 → SUCCESS 则本地同步已支付返回 `{already_paid:true}`；NOTPAY/USERPAYING 先 close 再下单
  - `POST /notify`：校验 `x-pay-token` → 幂等更新（WHERE status=0）→ sendNotify 邮件
  - `GET /status/:orderNo`：轮询用（前端 + 支付页金额校验共用）
  - `GET /oauth/url` + `/oauth/callback`：官网自拉起时代残留（前端已不再用，保留兼容）
- `backend/server.js`：CORS allowedOrigins 加 `https://pay.openai2000.cn`；CSP script-src 加 `https://res.wx.qq.com`
- `frontend/src/pages/TemplateShop.vue` / `Packages.vue`：下单成功 → 微信内 `location.href = 'https://pay.openai2000.cn/pay/hz?order_no=' + order_no`；非微信 → payState='needWechat' 提示；onMounted 处理 `?pay=order_no`（轮询 status>=1 → 成功页）

## 前端支付状态机（TemplateShop 步骤3）
payState: idle/creating/oauth/paying/success/needWechat/fail/closed
- 下单成功 → startPay → 跳 pay 页（不在官网拉起）
- 从 pay 页跳回 ?pay= → 查 status → >=1 成功页；否则重新跳 pay 页
- "重新支付"按钮 → 重新跳 pay 页（网关侧已关旧单，不会重复支付）

## 验证清单（实测通过）
1. `curl -sk 'https://pay.openai2000.cn/pay/hz?order_no=SO_TEST'` 无 cookie → 302 open.weixin.qq.com 授权 URL（redirect_uri 编码正确）
2. 带 `Cookie: pay_openid=o_test` → 渲染页含 ORDER_NO/SUBJECT_PREFIX/RETURN_URL 正确
3. 伪造回调 `POST /api/payment/notify` 无 token → 403
4. 真实订单 notify（带 token）→ 订单 status 0→1(2)、paid_at 填充、重复通知幂等
5. 无效 openid 调网关 jsapi → 微信 400 被网关正确捕获返回 fail（链路通）
6. CORS：`OPTIONS -H 'Origin: https://pay.openai2000.cn'` → 204

## 测试订单清理
- package_orders 在 huizhiyunma_db（DB_USER=huizhiyunma）
- template_orders 在 pay_system_db（**用户 pay_system / PaySystem@2026，huizhiyunma 用户无权限**）
- 用 node + mysql2 直连删（sudo node 需要绝对路径 + require 相对 backend 目录）

## 踩坑时间线（重要）
1. `resolveOrder` 状态查询 SELECT 硬编码 paid_at → package_orders 无此列报 ER_BAD_FIELD_ERROR → 改为 paidAtCol 动态拼接
2. 用户改授权域名为 pay.openai2000.cn 后，**线上 dist 仍是官网自拉起旧版**（本地 patch 后 scp 漏步，B 上 /tmp 是旧文件）→ 用户报"支付还是不行" → grep dist 无 pay.openai2000.cn/pay/hz 定位 → 重新 scp + 构建 + grep 验证
3. nginx heredoc 内嵌双引号被 ssh 外层吃掉 → add_header 语法错 → 改本地编辑 scp 回传
4. location 级 add_header 覆盖 server 级 → HSTS 等安全头丢失 → location 内补全全部安全头
5. vite build 后 SEO 页被清空 → 重跑 `node ../backend/seo/generate.js`
