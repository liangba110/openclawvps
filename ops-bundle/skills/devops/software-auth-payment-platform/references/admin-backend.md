# softapi 管理后台实现明细（2026-08-28）

## 数据表（software_auth 库）
```sql
-- 管理员
CREATE TABLE admin_user (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,          -- BCrypt
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);
-- 权限开通记录（自动充值+手动调整都会写）
CREATE TABLE app_vip_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  app_id VARCHAR(32) NOT NULL,
  user_id INT NOT NULL,
  username VARCHAR(50),
  order_sn VARCHAR(64),
  old_vip_type TINYINT DEFAULT 0,
  new_vip_type TINYINT DEFAULT 0,
  old_expire_time DATETIME,
  new_expire_time DATETIME,
  operate_type VARCHAR(50),                -- '微信充值' / '手动调整' / '封禁账号' / '解封账号'
  operator VARCHAR(50),                    -- 'system'=自动 / 管理员名
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_app_user (app_id, user_id)
);
-- 每软件独立价格（app 表加列）
ALTER TABLE app ADD COLUMN price_1 DECIMAL(10,2) DEFAULT 9.90;
ALTER TABLE app ADD COLUMN price_2 DECIMAL(10,2) DEFAULT 29.90;
ALTER TABLE app ADD COLUMN price_3 DECIMAL(10,2) DEFAULT 199.90;
ALTER TABLE app ADD COLUMN price_4 DECIMAL(10,2) DEFAULT 520.00;
```
⚠️ MySQL8 不支持 `ADD COLUMN IF NOT EXISTS`（1064），必须分条执行；MariaDB 才支持。

## 管理员初始创建（BCrypt）
```python
# 用项目 venv 生成 hash 后插入（不要手写明文）
from app.common.security import hash_password
# INSERT INTO admin_user(username,password) VALUES('admin', hash_password(密码))
```

## 管理 API（/api/admin/*）
- 鉴权：`Authorization: Bearer <jwt>`；ADMIN_SECRET = settings.JWT_SECRET + '_admin'（与管理/用户 token 隔离）
- token 12h：`jwt.encode({"admin_id":id,"exp":now+12h}, ADMIN_SECRET, "HS256")`
- 未登录统一返回 `{code:401, msg:"未登录"}`
- 前端 `localStorage.setItem('sa_token')` 持久化，401 自动跳登录页

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /login | {username,password} → {token,username} |
| GET | /stats | apps/users/orders/paid_orders/today_amount/today_orders |
| GET | /apps | 全量软件列表（含 price_1~4、status）|
| POST | /apps | 新增软件 {app_name,notify_url,logo_url,price_1~4} → 返回 app_id+app_key |
| PUT | /apps/{app_id} | 编辑名称/回调/logo/价格/status(0禁用1启用) |
| DELETE | /apps/{app_id} | 有用户或订单时报"不能删除可禁用" |
| GET | /users | ?app_id=&keyword=&page=&page_size= |
| PUT | /users/{user_id} | {status?/vip_type?/vip_expire_time?('Y-m-d H:M:S')/log(备注)} → 自动写 app_vip_log |
| GET | /orders | ?app_id=&status=&order_sn=&page= |
| GET | /vip-logs | ?app_id=&keyword=&page= |
| PUT | /password | {old_password,new_password} |

## 前端页面结构（templates/admin.html）
- 单文件：login 视图 + layout（侧边栏 6 模块：总览/软件/用户/账单/开通记录/改密）
- 无前端框架，原生 fetch + innerHTML；`api(path,{method,body})` 统一带 Bearer 头
- 分页统一 `pageCtrl(page,total,pageSize,fn)`
- 导航切换：`switchView(v)` 内按需 `loadUsers()/loadOrders()/loadVipLogs()` 懒加载
- 编辑弹窗：`.modal-mask.show` + innerHTML 填充（含价格输入、用户 VIP 调整 datetime-local）

## 与业务侧联动（关键）
1. **价格**：下单接口（app_api 的 recharge/create 与 page/recharge/create）用 `_app_price(app, goods_type)` 读 app.price_x，为 0/None 回退全局 GOODS_PRICE
2. **开通记录**：微信回调开权时写 app_vip_log（old_vip 需在 update 前取，operator='system'）；手动调整用管理员名
3. **删除软件**：先查 app_user/app_order 计数，>0 拒绝
4. 收银台 HTML 的 JS：`const p=...` 变量必须用 `password: p` 传参——对象简写 `{password}` 引用未定义变量会被 JSON.stringify 静默丢弃（本次踩坑：报"密码至少6位"实际是前端丢字段）
5. **管理后台导航点击事件必须手动绑定**：HTML 导航 `<a data-view="apps">` 写了 switchView 函数但没挂 click 事件 → 点击无反应、页面不切换。原生 `<a>` 不是 `<button>`，不会有默认 JS 行为。修复：`document.querySelectorAll('.sidebar nav a').forEach(a => a.addEventListener('click', () => switchView(a.dataset.view)));` 必须写在 init 里
6. **用户管理"调整权限"弹窗必须回显当前值**：空弹窗填权限但不显示当前 VIP/过期时间 → 用户不知道原来是什么，容易误清空。打开弹窗时从 USERS_CACHE[id] 读取当前值回填 select 和 datetime-local。留空过期时间时**自动计算**（日卡+1/月卡+30/年卡+365天/永久=清空），不要存 NULL
