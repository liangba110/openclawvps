---
name: software-auth-payment-platform
description: 多软件授权充值支付平台（softapi.openai2000.cn，软件登录注册+自动充值开通权限服务端API）。覆盖 FastAPI 分层架构、多软件接入(app/app_user/app_order 三表)、MD5接口签名、网页收银台免签名接口、SA2订单前缀与支付回调全链路。触发：softapi、软件授权、多软件支付、软件注册登录充值API、给客户端软件接支付、软件收银台。
version: 1.0.0
author: hermes
license: MIT
platforms: [linux]
---

# 多软件授权充值支付平台（softapi）

## 项目定位
`https://softapi.openai2000.cn` = 软件登录注册及自动充值开通服务端 API。任何付费软件注册后获得 app_id/app_key，用户在该软件体系内注册→登录→微信扫码充值→**全自动开通软件权限**（无人工审核）。每软件**独立用户体系**（A 软件用户不能登 B 软件）。

- 代码：`/opt/software_auth/`（FastAPI + SQLAlchemy + PyMySQL + Redis，venv）
- 服务：systemd `software_auth.service`，uvicorn 127.0.0.1:5006，Caddy 反代 softapi.openai2000.cn
- 数据库：MySQL `software_auth`（独立库，铁律：不碰 huizhiyun/aiweb）
- 支付：统一网关 pay.openai2000.cn（铁律：所有支付走此网关，不另起）→ SA2 前缀 → 本平台

## 数据库（6 表）
- `user` / `recharge_order` / `vip_log` — 平台自有用户体系（原 softapi）
- `app` — 软件表：app_id(唯一)、app_key(签名密钥)、app_name、logo_url、notify_url、status
- `app_user` — 软件用户表：app_id+username 联合唯一（每软件独立用户）
- `app_order` — 软件订单表：order_sn=**SA2** 前缀、user_id、goods_type、status、notify_status(0未通知/1已通知)

## API 全景（路由前缀 /api/app）
| 接口 | 签名 | 说明 |
|---|---|---|
| POST /register | 无 | 软件自助注册 → 返回 app_id + app_key（app_key 只返回一次，妥善保存）|
| GET /info | 无 | 软件公开信息（收银台品牌展示）|
| POST /user/register | ✅ | 软件用户注册 |
| POST /user/login | ✅ | 登录 → JWT Token（含 app_id）|
| GET /user/auth | 无(Token) | 鉴权+权限校验（客户端启动调），过期自动降级 |
| POST /recharge/create | ✅ | 下单 → 返回微信 code_url |
| GET /recharge/query / list | 无(Token) | 订单查询/列表 |
| POST /recharge/callback | 网关Token | 网关回调→开权→转发软件 notify_url |
| POST /page/login /register /recharge/create | 无 | **网页收银台免签名接口**（见下）|

## 签名机制（软件服务端调用核心接口）
```
sign = md5( app_id + 排序后参数拼接(k+value) + app_key + timestamp )
```
- 参数排序：排除 sign、timestamp 后按 key 排序；**app_id 也参与排序拼接**
- 时效：timestamp 与当前时间差 >300s 拒绝
- 验签失败返回 code=403"签名无效"

## 网页收银台（免签名设计）
- 页面：`https://softapi.openai2000.cn/pay/{app_id}/`（main.py 路由 + templates/app_pay.html）
- **app_key 绝不能出现在前端/浏览器**（否则泄露签名密钥）→ 收银台用专用 `/api/app/page/*` 免签名接口（官方页面自带信任），软件 API 保持签名
- 流程：页面读 /info 显示软件名/logo → page/login（未注册先 page/register）→ page/recharge/create → 微信扫码 → 前端轮询 query 检测支付成功
- 下单/回调复用同一套 service 逻辑，只是入口验签方式不同

## 支付回调全链路（SA2 前缀）
```
微信扫码支付 → 回调 pay.openai2000.cn 网关(公钥验签)
  → 网关按前缀路由: SA2 → https://softapi.openai2000.cn/api/app/recharge/callback
  → 本平台: X-Pay-Token 校验 → 订单置已支付 → 用户 VIP 开通(计算过期时间)
  → 转发软件 notify_url（POST 网关格式 + 同款 MD5 签名，app_order.notify_status=1）
```
- 套餐价：GOODS_PRICE {1:9.9日, 2:29.9月, 3:199.9年, 4:520永久}；GOODS_DAYS {1:1, 2:30, 3:365, 4:None永久}
- VIP 续费按「原过期时间或当前时间取较晚者 + 天数」（老用户续费顺延）
- 软件 notify_url 收到回调后应验签并确认幂等（重复回调不重复开权）

## 客户端接入步骤（给软件开发者）
1. 调 `/api/app/register` 注册 → 保存 app_id/app_key
2. 后台配置 notify_url（支付成功接收）
3. 软件内：用户注册/登录（带签名）→ 存 Token → 启动时调 auth 校验
4. 充值：recharge/create → 展示 code_url 二维码 → 轮询 query
5. 收到 notify_url 回调 = 到账，可解锁功能

## 管理后台（/admin/）
- 页面：`https://softapi.openai2000.cn/admin/`（main.py 路由 + templates/admin.html 单页应用，蓝紫风格）
- 默认管理员：admin / 初始随机密码（创建时生成，首登改密）
- 表：`admin_user`（BCrypt 密码）、`app_vip_log`（权限开通记录，自动充值 operator=system / 手动调整=管理员名）
- **每软件独立价格**：app 表 `price_1~4` 列（默认 9.9/29.9/199.9/520），`_app_price(app, goods_type)` 读取（为 0/空则回退全局 GOODS_PRICE）；收银台与下单接口都必须用 `_app_price` 而非写死全局价
- API（/api/admin/*，Bearer Token，独立 ADMIN_SECRET = JWT_SECRET+'_admin'，12h）：
  - POST /login / GET /stats / GET|POST /apps / PUT|DELETE /apps/{app_id}（有用户/订单的软件不能删，提示禁用）
  - GET /users（app_id/keyword/page 筛选）/ PUT /users/{user_id}（封禁/解封/手动调 VIP+过期时间，自动写 app_vip_log）
  - GET /orders（app_id/status/order_sn 筛选）/ GET /vip-logs / PUT /password
- 详细接口与页面结构见 `references/admin-backend.md`

## 陷阱（都踩过）
- **JS 对象简写变量未定义 → JSON.stringify 静默丢弃该字段**：`const p = ...` 但写 `{username, password}`（password 未定义）→ 请求里密码丢失 → 后端报"密码至少6位"但用户明明输了密码。症状是页面点击无反应+状态栏提示注册失败。排查：curl 直接测 API 正常 → 定位前端变量名。修复 `{username, password: p}`。**对象简写里用的变量必须已定义，否则静默变 undefined**
- **MySQL8 不支持 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`**（MariaDB 语法，报 1064）→ 用两条独立 `ALTER TABLE ADD COLUMN`，或先查 information_schema
- **浏览器 console 的 fetch 被沙箱拦截**（`Blocked: sensitive browser JavaScript primitive`）→ 接口验证用 curl/terminal，浏览器 console 只做 DOM 检查（getElementById/querySelector）
- **网关前缀顺序**：SA2 分支必须写在 SA 分支**之前**（elif 顺序匹配，`[:2] in ('SA',)` 会先吃掉 SA2 订单）→ 改网关 api.py 时先看顺序
- **create_token 扩展**：原函数只收 (user_id, username)，多软件需加 `app_id=None` 参数写入 JWT，否则 auth 无法区分软件
- **模型注册**：新增模型后必须加到 `models/__init__.py` 显式导入，否则 SQLAlchemy 不建表/查不到
- **crud 文件覆盖**：write_file 会整文件覆盖——多个 CRUD 写进同一文件时一次写完，别分多次（会丢函数）
- **验证签名用 Python 脚本算**：shell 拼接签名易漏参数（app_id 也在排序里），用 ./venv/bin/python3 走 urllib 完整请求
- 收银台 HTML 里不要写 PHP/模板语法（`$(date...)` 等），是静态文件直接读

## 相关
- 支付回调排障、双格式兼容、Next.js 站点改码：见 `wechat-pay-callback-troubleshooting`
- 参考：`references/softapi-api-notes.md`（详细接口字段与签名示例）
