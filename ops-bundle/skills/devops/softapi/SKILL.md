---
name: softapi
description: softapi.openai2000.cn 多软件支付授权平台（FastAPI）。触发词：softapi、多软件支付、软件授权、收银台、app_id、app_key、软件接入、softapi管理后台。
version: 1.0.0
author: hermes
license: MIT
platforms: [linux]
---

# softapi 多软件支付授权平台

软件登录/注册/充值/自动开权的一站式服务端平台。任何软件注册后拿 app_id/app_key 接入，用户充值后自动开通 VIP 权限，支付结果回调软件自己的 notify_url。

## 部署拓扑
- 域名：https://softapi.openai2000.cn（Caddy → 127.0.0.1:5006）
- 代码：`/opt/software_auth`（git 管理；上游 GitHub 仓库 `liangba110/software_auth_api` 克隆，本地已扩展）
- 服务：systemd `software_auth`（uvicorn app.main:app --host 127.0.0.1 --port 5006，venv: /opt/software_auth/venv）
- 数据库：MySQL 库 `software_auth`（密码同 root: huizhiyun2026）
- 依赖：Redis 已装（限流用）

## 表结构
| 表 | 用途 |
|---|---|
| user / recharge_order / vip_log | 原单站体系（订单前缀 SA，回调 /api/recharge/callback）|
| app | 软件表：app_id/app_key/app_name/logo_url/notify_url/status + **price_1~4 每软件独立价格** |
| app_user | 软件用户（**每软件独立用户体系**，app_id+username 唯一）|
| app_order | 软件订单（订单前缀 **SA2**，回调 /api/app/recharge/callback）|
| admin_user | 管理员（BCrypt）|
| app_vip_log | 权限开通记录（自动充值 operator=system / 手动调整 operator=管理员名）|

## 页面入口
- 收银台：`/pay/{app_id}/`（用户自助注册/登录/选套餐/扫码/自动开权，品牌自定义）
- 管理后台：`/admin/`（登录→总览/软件管理/用户管理/充值账单/开通记录/修改密码）
- 测试页：`/test/`（原单站支付测试）
- API 文档：`/docs`（Swagger）
- 对接文档：`/opt/software_auth/docs/对接文档.md`（发给软件开发者/Trae 的完整接入说明）

## 接口签名机制（核心）
所有核心软件接口（除 register/info/page/*）必须带签名：
```
sign = md5( app_id + 排序参数拼接 + app_key + timestamp )
```
- 参数（不含 sign/timestamp）按 ASCII 升序，拼成 `key1value1key2value2...`，app_id 也参与
- timestamp 与服务器相差 >300s 失效
- **app_key 只在软件服务端用，绝不下发客户端**（否则签名可伪造）
- 签名示例代码（Python/Node）在对接文档

## 软件侧 API（前缀 /api/app，均带签名除注明）
- POST /register（免签名）→ 返回 app_id+app_key
- POST /user/register、/user/login（login 返回 JWT token，含 app_id 声明）
- GET /user/auth（客户端启动校验：vip_type>0 解锁；权限过期自动置 0 返回 403）
- POST /recharge/create（goods_type 1日/2月/3年/4永久，价格读 app.price_x，返回 weixin:// pay_url）
- GET /recharge/query、/recharge/list
- POST /recharge/callback（网关回调→开权→转发软件 notify_url，带软件签名）
- 免签名页面接口：GET /info、POST /page/login、/page/register、/page/recharge/create（收银台专用）

## 支付链路
```
用户扫码 → 微信官方 → 网关 pay.openai2000.cn（公钥验签）
  → 按前缀路由：SA2 → softapi /api/app/recharge/callback（SA2 分支必须在 SA 之前！）
  → 开权（vip_type + 过期时间，续费在原基础上叠加）→ 记 app_vip_log
  → 转发软件 notify_url（POST {app_id,order_sn,amount,goods_type,user_id,status,timestamp,sign}）
```
- 软件回调验签：`md5(app_id + amount{amount} + goods_type{goods_type} + order_sn{order_sn} + status{status} + timestamp{ts} + user_id{user_id} + app_key + ts)`
- 回调需幂等（微信会重试，最长 24h），按 order_sn 判重
- 微信回调排障详见 skill `wechat-pay-callback-troubleshooting`

## 管理后台（/admin/）
- 初始管理员：admin（首登立即改密；密码变更注意别丢）
- 全部 API 需 `Authorization: Bearer <token>`（独立 JWT secret = settings.JWT_SECRET + '_admin'）
- API：/api/admin/login、/stats、/apps(C/R/U/D)、/users(筛选+封禁+调权限)、/orders、/vip-logs、/password
- 每软件独立价格在「软件管理」编辑，收银台和下单自动读取（`_app_price()` 回退全局默认价）

## 陷阱（本次开发踩过的坑）
1. **vanilla JS 单页后台导航必须手动绑定点击**：写了 `switchView()` 函数但 HTML 里 `<a data-view="apps">` 没有 onclick → 点击无反应。修复：`document.querySelectorAll('.sidebar nav a').forEach(a => a.addEventListener('click', () => switchView(a.dataset.view)))`。任何手写 SPA 导航都要检查事件绑定。
2. **JS 对象简写引用未定义变量会静默丢字段**：`const p = ...value; fetch(..., {username, password})` —— `password` 未定义，JSON.stringify 时该属性被**丢弃**，后端收不到报"密码至少6位"。必须写 `{username, password: p}`。这类 bug 前端控制台 0 报错，只能在请求体里发现。
3. **JWT token 需带 app_id 声明**：多租户下 token 必须能区分租户。`create_token(user_id, username, app_id=None)` 扩展时保持向后兼容（默认 None 不影响旧调用）。
4. **前缀路由子串顺序**：`SA2` 会被 `SA` 分支吃掉（前2位匹配），新前缀的 elif 必须排在短前缀之前。
5. **收银台前端不能做真实验签**（app_key 暴露浏览器 = 泄露）→ 官方页面走免签名 /page/* 接口，签名仅软件服务端调用用。
6. **充值日志顺序**：先取 old_vip/old_expire 再 update_user_vip，否则日志记的是新值。
7. MySQL8 `ALTER TABLE ADD COLUMN IF NOT EXISTS` 语法报错，需手动执行。

## 验证流程
1. `cd /opt/software_auth && ./venv/bin/python -c 'from app.main import app'` 语法检查
2. `sudo systemctl restart software_auth && curl https://softapi.openai2000.cn/` 200
3. API 链路：软件注册→用户注册(带签名)→登录→下单(SA2 真二维码)→模拟网关回调(X-Pay-Token: huizhiyun_gateway_2026)→查 app_order status=1 + app_user vip 更新 + app_vip_log 记录
4. 管理后台：浏览器实测每个页面（导航切换/新增软件/调权限/筛选）
5. 全站回归：softapi/pay/api/www.ttdazi.xyz/ai 全部 200
6. 用户浏览器看到旧版时提示强刷（Ctrl+F5）

## 参考文件
- `references/softapi-admin-panel.md` — 管理后台实现细节与前端陷阱详录
- `references/softapi-api-contract.md` — 全部接口请求/响应示例与签名算法完整说明
