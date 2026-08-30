# 统一支付网关 pay.openai2000.cn — 官网(Node.js)对接配方

> 2026-08-07 汇智云官网 www.openai2000.cn 首个网关对接案例（用户指令：所有支付必须走此网关）

## 网关事实
- 入口: `https://pay.openai2000.cn`（公网）→ Caddy → `127.0.0.1:5005`（A 本机，公网 socket 不可达）
- systemd: `ttdazi-pay.service`（改代码后 `sudo systemctl restart ttdazi-pay`；回归: `curl 127.0.0.1:5005/health` + Native 0.01 下单出 code_url）
- 代码: `/opt/ttdazi/payment_service/`（api.py 路由 `/api/v1/`；jsapi_pay_endpoint.py 挂 `/wxpay/jsapi` `/wxpay/native`）
- 商户: 1114539763 / APPID wxd274e174ddadd4cb / APIv3 key 与证书在 `certs/`
- 网关下单接口收**元**(float) 内部转分；JSAPI 需 openid（业务侧自己 OAuth snsapi_base 拿，网关不代做）

## 回调路由（api.py wx_notify）与鉴权
- 前缀路由: `PAY/RCH`→dazi 充值回调; `TMP/SO/HY`→www.openai2000.cn/api/payment/notify
- 网关 `_notify_merchant` 已带 `X-Pay-Token: huizhiyun_gateway_2026` 请求头 → 业务 notify 必须校验（伪造回调 403）
- 网关转发给业务的 payload: `{order_no, amount(元), status:1, timestamp}`
- 网关只对 `pay_order` 表有记录的单据记 callback_status；官网订单不在该表（rowcount=0 无害）

## 官网后端（B:8081 Node/Express）对接实现
路由（routes/payment.js，全部挂在 /api/payment 下）：
- `GET /oauth/url?order_no=` → 返回 open.weixin.qq.com 授权 URL（snsapi_base 静默）
- `GET /oauth/callback?code&state=order_no` → code 换 openid → Set-Cookie `hz_openid`(HttpOnly, 2h) → 302 回 `/{templates|packages}?pay=order_no`
- `POST /jsapi {order_no}` → cookie 取 openid（无则 401 `NEED_OAUTH`）→ 校验订单 status=0 → 转发网关 `/api/v1/wxpay/jsapi`（amount=分/100，subject≤60字）→ 原样返回 prepay 参数
- `POST /notify` → 校验 X-Pay-Token → 按前缀更新对应订单表 → `sendNotify` 邮件 → `{code:0}`（200 让网关记 callback_status=1）
- `GET /status/:orderNo` → 前端轮询（2s）→ status>=1 即成功

订单前缀→表/库映射（resolveOrder 模式，动态 SELECT）:
| 前缀 | 表 | 库 | 支付成功动作 |
|---|---|---|---|
| TMP | template_orders | pay_system_db (payPool) | status 0→1 + paid_at |
| SO | package_orders | huizhiyunma_db (pool) | status 0→1（**无 paid_at 列**） |
| HY | payment_orders | huizhiyunma_db (pool) | status 0→2 + paid_at |

## 前端（Vue3）要点
- index.html 加 `<script src="https://res.wx.qq.com/open/js/jweixin-1.6.0.js">`（body 末尾）
- 后端全局 CSP `script-src` 必须放行 `https://res.wx.qq.com`（否则微信 SDK 加载失败）
- `wx.chooseWXPay({appId,timeStamp,nonceStr,package,signType:'RSA',paySign,...})` **不需要 wx.config**（与分享等 JS-SDK 接口不同）
- 流程: 下单成功 → 微信内自动 startPay → jsapi 返回 401 则跳 oauth/url → 微信回跳 `?pay=order_no` 自动继续 → chooseWXPay → 轮询 status
- 非微信 UA（`/MicroMessenger/i.test(navigator.userAgent)`）: 提示"请用手机微信打开"，展示订单号
- OAuth 回来后页面 onMounted 需解析 `?pay=` 参数：查状态 → 已付则成功页，未付则自动继续支付

## 坑清单（本次实战）
1. **vite build 清空 dist 含 SEO 静态页**：`vite build` 后 `dist/*.seo.html` 与 `dist/seo/` 全没 → 必须补跑 `node ../backend/seo/generate.js`（读库生成，无需外部 API；构建命令本就是 `vite build && node ../backend/seo/generate.js`，只跑 vite 会丢 SEO）→ 构建后 `ls dist/*.seo.html` 非空确认
2. **package_orders 无 paid_at 列**：动态 SELECT 字段（resolveOrder 配 `paidAtCol`，SO 为 null），否则 `Unknown column 'paid_at'`
3. **pm2 重启需 nvm PATH**：`sudo -u ubuntu bash -c 'export PATH=/home/ubuntu/.nvm/versions/node/v22.23.0/bin:$PATH; pm2 restart huizhiyunma-api --update-env'`（sudo 下 `which pm2` 找不到）
4. **sudo node 跑 DB 脚本**：node 绝对路径 `/home/ubuntu/.nvm/versions/node/v22.23.0/bin/node`；require 模块用绝对路径（`/data/web/huizhiyunma/backend/node_modules/...`）；dotenv 需 cwd 在 backend
5. **notify 幂等**：UPDATE 带 `AND status=0`，重复回调不重复处理/不重复发邮件
6. **接口测试会真实改库**：建测试订单后测完删除（DELETE FROM package_orders WHERE order_no=...）
7. **CSP**：官网 server.js 全局 CSP `connect-src 'self' https://openai2000.cn`——前端不直连网关（走自身后端转发），无需放行 pay.openai2000.cn；只有 `script-src` 需加 res.wx.qq.com
8. **jsapi 接口 401 与 502 语义**：401 `{code:-1, message:'NEED_OAUTH', oauth:true}` 引导前端走授权；网关下单失败 502 展示错误，不进入支付

## 回归要点（改网关后必做）
- `systemctl is-active ttdazi-pay` + `/health` 200
- Native 下单 0.01 元返回 code_url（ttdazi 链路无损）
- 伪造 notify（无 X-Pay-Token）→ 403
- 正确 token + 存在订单 → `{code:0}` 且订单表 status 变更、重复调用幂等
