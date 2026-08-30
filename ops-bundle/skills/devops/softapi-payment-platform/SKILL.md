---
name: softapi-payment-platform
description: softapi 多软件支付授权平台（softapi.openai2000.cn）。用户/注册登录/微信自动充值/VIP自动开通/多软件接入/网页收银台。触发词：softapi、软件授权充值、多软件支付、app_id/app_key、收银台、SA2订单。
version: 1.0.0
author: hermes
license: MIT
platforms: [linux]
---

# softapi 多软件支付授权平台

## 定位
软件登录注册 + 微信自动充值 + 权限自动开通的服务端 API 平台，支持**多软件独立接入**（每软件独立 app_id/app_key + 独立用户体系）。对接文档（给软件开发者/Trae 用）：`/opt/software_auth/docs/对接文档.md`。

## 技术栈与部署
- FastAPI + SQLAlchemy + PyMySQL + Redis（限流）+ JWT + BCrypt
- 代码：`/opt/software_auth/`（venv 独立，端口 **5006**，仅绑 127.0.0.1）
- systemd：`software_auth.service`（重启：`sudo systemctl restart software_auth`）
- 数据库：`software_auth`（独立库，6表：user / recharge_order / vip_log / app / app_user / app_order）
- 域名：https://softapi.openai2000.cn → Caddy → 127.0.0.1:5006

## 架构：单软件版 vs 多软件版
| 体系 | 表 | 订单前缀 | 说明 |
|---|---|---|---|
| 单软件版（原）| user/recharge_order/vip_log | SA | 测试页 /test/ |
| **多软件版** | app/app_user/app_order | **SA2** | 软件自助注册，每软件独立用户体系 |

**回调路由（网关 /opt/ttdazi/payment_service/api.py）**：
- `SA` → softapi/api/recharge/callback（单软件版）
- `SA2` → softapi/api/app/recharge/callback（多软件版）
- ⚠️ **SA2 的 elif 必须写在 SA 之前**（前缀子串先匹配），否则 SA2 订单被 SA 分支误吃

## 多软件 API（/api/app/*，除 register/info/page/* 外全部需签名）
| 接口 | 说明 |
|---|---|
| POST /api/app/register | 软件自助注册 → app_id + app_key（app_key 只显示一次）|
| GET /api/app/info?app_id= | 软件信息（公开，收银台用）|
| POST /api/app/user/register | 软件用户注册（签名）|
| POST /api/app/user/login | 登录 → JWT（token 含 app_id）|
| GET /api/app/user/auth | 鉴权+权限校验（客户端启动调，过期自动降 vip_type=0）|
| POST /api/app/recharge/create | 下单 → SA2 订单 + 微信 code_url |
| GET /api/app/recharge/query / list | 订单查询 |
| POST /api/app/recharge/callback | 网关回调 → 开权 → 转发软件 notify_url |
| POST /api/app/page/login / page/register / page/recharge/create | **收银台免签名版**（官方页面专用，app_key 不能进浏览器）|

## 签名算法（核心）
```
sign = md5( app_id + 排序参数拼接 + app_key + timestamp )
```
- 排序参数 = 除 sign/timestamp 外所有参数按 ASCII 升序，拼成 key1value1key2value2...（**app_id 本身也参与排序拼接**）
- timestamp 与服务端相差 >300 秒失效
- Python/Node 示例代码见对接文档（`/opt/software_auth/docs/对接文档.md` 第四节）
- 软件侧 notify_url 回调同样带 sign（字段：app_id/order_sn/amount/goods_type/user_id/status/timestamp/sign）

## 网页收银台
- `https://softapi.openai2000.cn/pay/{app_id}/`（templates/app_pay.html）
- 展示软件名/logo（从 app 表读），用户注册/登录 → 选套餐 → 微信扫码 → 自动开权
- 页面调用 `/api/app/page/*` 免签名接口；**app_key 绝不入前端 JS**

## 陷阱
1. **前端 JS 变量名 bug**：页面里 `const p = password.value` 后请求写 `{username, password}`（变量名不匹配）→ JS 对象里 password 为 undefined → `JSON.stringify` **静默丢弃 undefined 字段** → 后端收不到密码 → 报"密码至少6位"。排查"前端点了没反应/后端报参数缺"时，先核对 JS 变量名与请求字段是否一致，undefined 字段会被 JSON 丢弃且**控制台无报错**。
2. **收银台登录流程**：先 login（401→未注册）→ register → 再 login；注册失败要展示 msg 而非静默。
3. 二维码：pay_url 是 `weixin://wxpay/bizpayurl?pr=...`，**直接用原值生成二维码**，勿替换 weixin:// 前缀（替换成 https 会导致扫码报错）。
4. 订单列表接口返回 ORM 对象会 500（`Object of type X is not JSON serializable`）——必须序列化为 dict 再返回，页面轮询才正常。
5. 每软件用户体系独立：app_user 唯一键是 (app_id, username)，跨软件不共享。
6. 多软件版套餐固定：1日9.9/2月29.9/3年199.9/4永久520（app 表自定义价格未开发）。

## 验证
- 软件注册 → 用户注册（签名）→ 登录 → 下单（SA2 + 真实 weixin:// 码）→ 模拟回调（X-Pay-Token: huizhiyun_gateway_2026）→ app_order.status=1 + app_user.vip_type 更新 + 过期时间正确
- 收银台浏览器实测：登录按钮启用 + 下单显示二维码 + 控制台 0 错误
- 全站回归：softapi/pay/api/www.ttdazi.xyz/ai 全部 200

## 关联
- 支付回调排障：wechat-pay-callback-troubleshooting（含全站点回调链路图）
- 支付商品备注统一「广告信息展示服务」（平台铁律）
