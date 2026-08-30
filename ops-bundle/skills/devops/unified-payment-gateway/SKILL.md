---
name: unified-payment-gateway
description: 对接公司统一支付网关 pay.openai2000.cn（Server A 5005 微服务）。用户铁律：所有支付（新项目/现有站）必须对接此网关，禁止另起支付实现。覆盖微信支付 API v3（JSAPI/Native）、订单前缀回调路由、X-Pay-Token 鉴权、双轨支付模式（微信内拉起+PC扫码）、业务系统对接要点与常见坑。当需要给任何网站/应用接入支付、排查支付失败、扩展网关能力时触发。
---

# 统一支付网关对接（pay.openai2000.cn）

## 铁律
所有支付必须对接统一支付网关 **pay.openai2000.cn**（Server A:5005，`/opt/ttdazi/payment_service`，商户号 1114539763 + 公众号 APPID wxd274e174ddadd4cb）。禁止另起支付实现。新增业务系统必须在该网关登记订单前缀路由。

## 网关架构
- systemd 服务 `ttdazi-pay`（gunicorn -w 2 app:app，绑 127.0.0.1:5005），重启 `sudo systemctl restart ttdazi-pay`，修改后必须回归（health + native 下单 + 伪造 notify 拒绝）
- 商户证书 `certs/`：apiclient_key.pem / apiclient_cert.pem / wx_platform_cert.pem；API v3 key 在 wxpay.py 常量；公众号 SECRET 在 app.py `WX_SECRET_MP`（env WX_SECRET）
- 入口：公网 `https://pay.openai2000.cn`（Caddy → 127.0.0.1:5005），B/E/D 走 443+SNI；微信回调 notify_url 固定 `https://pay.openai2000.cn/api/v1/wxpay/notify`
- 平台证书勿复制到业务服务器（复制=安全扩散），业务系统一律经网关下单/查询

## 网关接口（/api/v1/）
- `POST /wxpay/jsapi {openid, out_trade_no, amount(元), subject}` → `{appId,timeStamp,nonceStr,package,paySign}`（微信内拉起，需 openid）
- `POST /wxpay/native {out_trade_no, amount, subject}` → `{code_url}`（扫码支付，**无需 openid**）
- `GET /wxpay/query?out_trade_no=` → `{trade_state}`（SUCCESS/NOTPAY/USERPAYING/CLOSED/REVOKED/PAYERROR）
- `POST /wxpay/close {out_trade_no}`（关旧单，重新下单前调用，防 OUT_TRADE_NO_USED）
- `POST /wxpay/notify`（微信回调：验签 + AES-GCM 解密 + 更新本地 pay_order + 按前缀路由业务回调）
- 另有 refund / balance 等（ttdazi 内部用）

## 回调路由表（notify 按订单号前缀分发业务回调）⚠️ 新增业务系统必须在此登记
| 前缀 | 业务系统 | 回调 URL |
|---|---|---|
| PAY / RCH | 同途搭子 | `https://dazi.openai2000.cn/api/pay/notify/recharge` |
| TMP / SO / HY | 汇智云官网 | `https://www.openai2000.cn/api/payment/notify` |
| AE | AI电商站 ai.openai2000.cn（Next.js, Server B:3000, /opt/ai-ecom-site, SQLite） | `https://ai.openai2000.cn/api/pay/notify` |
| SA | 软件授权充值站 softapi.openai2000.cn（FastAPI, /opt/software_auth, 端口5006） | `https://softapi.openai2000.cn/api/recharge/callback` |

⚠️ 实际代码是 **if/elif 链 + else 兜底**：notify 里非 TMP/SO/HY/AE/SA 前缀 → 走 dazi（原逻辑）。新增前缀 = 在 api.py wx_notify 的 elif 链加一个分支（备份 api.py 后纯追加，勿动现有分支），改完 `python3 -c 'import ast; ast.parse(open("api.py").read())'` 验语法 + 重启 ttdazi-pay + 全量回归（现有前缀各下一单 + 6 站 HTTP 200）。

业务回调携带头 `X-Pay-Token: huizhiyun_gateway_2026`，**接收方必须校验该头**（防伪造回调把订单标记已支付）。回调 payload：`{order_no, amount, status:1, timestamp}`。网关侧改造 notify 时保持向后兼容：非本业务前缀且 pay_order 无记录 → 不回调（原逻辑）。

## 双轨支付模式（前端标准做法）
- **微信内**（UA 含 MicroMessenger）：跳 `pay.openai2000.cn/pay/hz?order_no=xxx` → 网关页 OAuth 静默授权（snsapi_base，redirect_uri 为 pay 域）→ JSAPI 拉起支付 → 轮询 query → 成功跳回业务站 `?pay=order_no`
- **PC / 手机浏览器**：业务后端调 `/api/payment/native` → 返回 code_url + **二维码 dataURL**（后端 qrcode npm 生成）→ 页面显示二维码 → 轮询业务后端 status 接口
- 微信后台要求：JSAPI 需「网页授权域名」+「JSAPI 支付授权目录」配置 **pay.openai2000.cn**（追加，勿删已有的 dazi.openai2000.cn）；**Native 扫码不需要任何后台配置**（商户已开通）

## 业务后端对接要点（官网 Node 后端为例）
1. native/jsapi 接口前置逻辑（防重复下单/已支付未同步）：校验订单存在 + status=0 + 金额>0 → 先查微信侧状态（query）→ `SUCCESS` 则本地同步已支付、返回 `{already_paid:true}` 不重复下单；`NOTPAY/USERPAYING/PAYERROR` 先 close 再下单
2. notify 回调：校验 X-Pay-Token → 按前缀更新对应订单表（TMP: template_orders 0→1；SO: package_orders 0→1；HY: payment_orders 0→2）→ **幂等**（`WHERE status=0`）→ 邮件通知
3. 前端轮询业务后端 status 接口（不是直接轮询微信）
4. CORS：业务后端必须放行 `https://pay.openai2000.cn`（pay 页 fetch 业务站校验真实金额防篡改）
5. 订单表差异：TMP 在 pay_system 用户库（pay_system_db）、SO/HY 在主库——查表用对应连接池；package_orders 无 paid_at 列（status 查询需按表动态取字段）

## FastAPI 业务系统对接要点（softapi 模式，2026-08 已验证）
1. **订单号必须带前缀**（如 `SA` + timestamp + 随机）：网关 notify 靠前缀路由回调，无前缀会被 else 兜底发到 dazi → 钱付了 VIP 不开。改 `gen_order_sn()` 即可
2. 下单时业务后端直接调网关 **本机** `http://127.0.0.1:5005/api/v1/wxpay/native`（走 127.0.0.1 不经 Caddy，payload `{out_trade_no, amount(元), subject}`），返回 `code_url`（`weixin://wxpay/bizpayurl?pr=...`）→ 作为 pay_url 给前端扫码
3. subject 固定「广告信息展示服务」（支付商品备注铁律，前端+网关+回调全链路统一）
4. 回调接口适配网关 JSON 格式：`Request` body `{order_no, amount, status:1, timestamp}` + 头 `X-Pay-Token: huizhiyun_gateway_2026`；**先校验头**（错误 token → 400 签名无效）再处理 `status==1`；处理用 `WHERE status=0` 幂等（已支付订单返回"已支付"不重复开 VIP）
5. 验证链路：注册→登录→下单（断言 pay_url 是 `weixin://` 真码而非 mock）→ 伪造回调（错 token 拒绝 + 对 token 开通）→ DB 查 order.status=1 + user.vip_type/expire + vip_log；测完删测试数据
6. 新站接入后：网关 +1 elif 分支 + 业务侧改 2 个文件（service 下单 + api 回调），不动网关其他逻辑

### 前端二维码渲染坑（浏览器 JS qrcode 库，2026-08-28 pay_test 页实测）
- 用 cdn `qrcode@1.5.1` 时 **`QRCode.toCanvas` 报 `o.getContext is not a function`**（库 API 与 canvas 元素不兼容）→ 改用 `QRCode.toDataURL(text, {width, margin}, cb)` 生成 dataURL 后 `img.src=url` 插入 DOM
- ⚠️ **`weixin://wxpay/bizpayurl?pr=...` 必须原样喂给二维码库，禁止替换 scheme**！曾按旧记录 `url.replace('weixin://','https://wxpay.qq.com/')` 生成二维码 → **用户微信扫码直接报错**（微信只认原生 weixin:// 链接）。`QRCode.toDataURL('weixin://wxpay/bizpayurl?pr=xxx')` 正常出码且扫码可支付——不要做任何转换
- 完整模式：下单接口返回 pay_url → **直接用原始 pay_url** → toDataURL 渲染 → `setInterval` 3s 轮询 `/api/recharge/list?token=` 找 `status==1` 即显示支付成功（业务侧轮询，不直连微信）
- **轮询接口必须返回序列化 dict 而非 ORM 对象**：FastAPI 若直接把 SQLAlchemy ORM 对象塞进 JSONResponse → `TypeError: Object of type RechargeOrder is not JSON serializable` → 接口 500 → 前端轮询永远失败 → **钱付了但页面不提示成功**。订单列表/查询接口需显式转 dict（order_sn/amount/status/pay_time 等字段）

## 常见坑
- **Next.js(15.5.x) 对接坑**：tsconfig `paths` 若**没有 `baseUrl`**，`next build` 会报 `Module not found: Can't resolve '@/lib/xxx'`（所有 @/ 别名系统性失效，连未改动的文件也失败，且清 .next 缓存无效）。修复：tsconfig 加 `"baseUrl": "."`。⚠️ 备份文件（.bak/.bak_directwx）不能放 `app/`、`lib/` 目录内（tsconfig include `**/*.ts` 会当 TS 文件编译，引用已删除的函数报错），放 backups/ 目录
- **Next.js AI 站对接模式**（ai.openai2000.cn，B 服务器 `/data/disk/ai-ecom/`，Next.js standalone + PM2 用户 aiecom + 端口3000 + SQLite `/data/disk/ai-ecom/data/site.db`；旧路径 /opt/ai-ecom-site 已废弃）：`lib/wechatpay.ts` 的 `createNativeOrder` **若进程 env 有 `PAY_GATEWAY` 则 fetch 网关 native**（amount=分/100，subject 固定「广告信息展示服务」），否则才直连微信 API（需 WXPAY_PRIVATE_KEY 等 env）；`.env` 里 WXPAY_* 可能被注释，实际配置看 PM2 进程 environ（`sudo cat /proc/<pid>/environ | tr '\0' '\n' | grep PAY_GATEWAY`）
  - ⚠️ **AI 站 notify 格式不匹配坑（2026-08-28 实测）**：`app/api/pay/notify/route.ts` 解析的是**微信原生回调格式**（`payload.resource.out_trade_no / trade_state`），但走 PAY_GATEWAY 时收到的是**网关转发格式**（`{order_no, amount, status, timestamp}` + X-Pay-Token 头）→ `data.out_trade_no` 为空 → 订单找不到 → **AE 站回调永远对不上**。若要让 AE 站经网关收回调，notify 需同时兼容两种格式：有 `resource` 字段走微信原生分支，有 `order_no` 字段走网关分支（校验 X-Pay-Token）
  - ⚠️ **AI 站"已支付"记录不可信**：72 单中 62 单 status=paid 但 `paid_at` 全是整点 `:02` 秒（16:00:02/22:00:02 等）→ 是**脚本/定时任务批量标记**的，不是微信回调真实到账——排查时别被"已支付"统计误导，要看 paid_at 是否与真实支付时间吻合
- JSAPI 需要 openid（OAuth 授权），Native 不需要——选错模式会白配授权域名/目录
- openid cookie 存各自域：pay 页存 `pay_openid`（pay 域，HttpOnly）；业务站自己的 OAuth 存自己域
- 微信回调 body 必须返回 XML SUCCESS（200），否则微信持续重试
- 修改网关（api.py/app.py）必须向后兼容 + 重启后回归：health 200、native 下单返回 code_url、伪造 notify 返回 400
- `qrcode` npm 包生成二维码 dataURL 需后端安装（`npm install qrcode`），避免前端引外部 CDN 被 CSP 拦截
- 支付页跳回业务站用 `?pay=order_no` 参数，业务站 onMounted 解析后：status>=1 显示成功，否则重新拉起/展示二维码——**不要自动重复拉起已发起的支付**
- **微信侧已 SUCCESS 但业务订单 status=0（回调不到）**：先 `wxpay/query` 确认微信侧成功 → 查网关 journalctl 有无 notify 记录 → tcpdump 抓 443 看微信回调 IP(220.196.160.x) 是否在重试 → `openssl s_client` 看 pay 域名证书类型。⚠️ **Caddy 默认不开 access log**（journalctl -u caddy 只有证书/TLS 事件，正常请求不落日志）——**grep Caddy 日志"没有回调记录"不能证明回调没到**，判断到达与否必须靠 tcpdump 抓包或网关 access 日志，别在 Caddy 日志上浪费时间。**pay 域名是 ECDSA 证书 = 微信支付服务器回调 TLS 握手失败 = 钱付了不开通**（微信支付服务器同 X5 不认 ECDSA，非"仅浏览器提示不安全"）。修复：pay 域名必须 RSA 证书；Caddy 不支持 `key_type rsa`（只 ed25519/ecdsa），需 certbot 单独签 RSA + Caddy `tls 证书路径` 指令指定手动证书。完整修复流程（云镜链临时摘除 + certbot 速率限制 + caddy 证书权限 + 自动续期钩子）见 wechat-pay-gateway skill「微信证书 X5 兼容」节与 linux-server-ops「腾讯云云镜防火墙」节
- **证书已 RSA + 回调仍不到（最后一坑）**：见 wechat-pay-gateway skill——商户平台「Native支付回调链接」需配置且可能要求**完整 URL（含 `/api/v1/wxpay/notify` 路径）**；商户平台订单详情页有「通知状态」+「重新发送通知」是权威依据（比抓包更直接判断微信发没发）。判定"微信没来连"前用 `-i any` 复验 tcpdump（eth0 曾异常抓不到 In 流量）

## 验证清单
1. `curl https://pay.openai2000.cn/health` → 200
2. Native 下单返回 `weixin://wxpay/bizpayurl?pr=...` code_url
3. 伪造 notify（无 token）→ 业务站 403
4. 真实 0.01 元端到端（需用户微信配合）：下单 → 授权/扫码 → 支付 → 回调 → 订单已支付 + 邮件通知

📖 模板：`templates/pay-test-page.html` — 可复制的支付测试页（注册/登录/下单/二维码/轮询完整模式，含 weixin:// 直生成与轮询接口序列化两个已踩坑的注释），新站接支付后改 API 路径即可部署。
