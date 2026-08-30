# softapi 管理后台实现细节与前端陷阱

## 页面结构（templates/admin.html，单页应用）
- 登录视图 `#loginView` + 主视图 `#mainView`（侧边栏导航 + 6 个 view 容器）
- 视图容器：viewStats / viewApps / viewUsers / viewOrders / viewVip / viewPwd
- 模态框 `#modalMask` + `#modalBox`（新增/编辑软件、调整用户权限共用）

## 管理 API（/api/admin/*，Bearer Token）
| 端点 | 功能 |
|---|---|
| POST /login | {username, password} → {token} |
| GET /stats | apps/users/orders/paid_orders/today_amount/today_orders |
| GET /apps | 全部软件（含 price_1~4 转 float）|
| POST /apps | 新增（生成 APP+时间戳 app_id，md5 前32位 app_key）|
| PUT /apps/{app_id} | 改名称/notify/logo/status/price_x |
| DELETE /apps/{app_id} | 有用户/订单则拒绝删除（提示可禁用）|
| GET /users?app_id=&keyword=&page= | 用户分页 |
| PUT /users/{id} | {status / vip_type / vip_expire_time / log}，记录 app_vip_log |
| GET /orders?app_id=&status=&order_sn= | 订单分页 |
| GET /vip-logs?app_id=&keyword= | 开通记录分页 |
| PUT /password | 原密码+新密码 |

## 关键实现
- 管理员 JWT：`ADMIN_SECRET = settings.JWT_SECRET + '_admin'`，12h 有效期
- require_admin：Header `Authorization: Bearer xxx`，401 时前端 `api()` 自动跳回登录页
- 前端 token 存 localStorage（key: sa_token）
- app_vip_log 双来源：微信充值（operator=system）+ 管理员手动调整（operator=admin用户名）
- 每软件价格：app 表 price_1~4，`_app_price(app, goods_type)` 取自定义价，0/未设置回退全局默认

## 踩坑实录（按出现顺序）
1. **导航点击无反应**：写了 `switchView(v)` 函数但导航 `<a>` 没绑事件。
   症状：点侧边栏链接页面纹丝不动（active 类不切换、视图不换）。
   修复：脚本末尾统一绑定。这是手写 SPA 最常见遗漏。
2. **注册报"密码至少6位"**：JS `const p = ...value` 后请求体写 `{username, password}`，
   `password` 变量不存在 → JSON.stringify 静默丢弃该键 → 后端收不到密码。
   前端控制台 0 报错（非严格模式未定义变量不抛错，shorthand 变 undefined）。
   修复：`{username, password: p}`。**检查前端请求体的变量名与后端字段名逐一对应**。
3. **页面服务重启后浏览器仍旧版**：模板文件改动后必须 `systemctl restart software_auth`
   （uvicorn 不热载模板），且用户端需强刷（导航加 ?v= 参数绕过缓存）。

## 验证要点
- 每个 view 切换后检查对应容器 innerHTML 非空（空 = 加载函数没被调用，多半是导航绑定问题）
- 未登录访问管理 API 必须 401
- 手动调整用户权限后，用软件侧 /api/app/user/auth 验证即时生效
