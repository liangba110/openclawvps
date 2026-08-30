---
name: fastapi-admin-panel
description: "FastAPI 全栈管理后台开发模式。覆盖：管理员认证(JWT)、CRUD接口、HTML前端(单页)、列表/筛选/弹窗编辑、分页、权限调整、统计总览。触发词：管理后台、admin panel、后台管理、管理页面。"
version: 1.0.0
author: hermes
---

# FastAPI 管理后台开发模式

## 触发条件
- 需要给已有 FastAPI 项目加管理后台
- 需要网页版 CRUD 管理界面
- 用户说"管理后台"/"admin panel"/"后台管理页面"

## 架构

### 后端（FastAPI）
```
/api/admin/login      POST   管理员登录 → JWT Token
/api/admin/stats      GET    总览统计
/api/admin/{resource} GET/POST/PUT/DELETE  CRUD
```

- 独立 JWT secret（与业务用户 Token 分开，如 `settings.JWT_SECRET + '_admin'`）
- 所有管理接口需 `Authorization: Bearer <token>` 头
- 用 `Header(default="")` + 手动解析（不用 Depends，FastAPI 的 Depends 对 Header 处理有坑）

### 前端（单页 HTML）
- 一个 `templates/admin.html` 搞定登录+主界面+所有模块
- 侧边栏导航 + 内容区切换（`switchView()` + `display:none/block`）
- 用 `fetch` 调管理 API，不用 axios
- 表格用 `<table>` 纯 HTML，不用第三方表格库
- 弹窗用 `<div class="modal-mask">` + JS 控制显示

### 关键模式

**JWT 签发（管理员独立 secret）**：
```python
ADMIN_SECRET = settings.JWT_SECRET + '_admin'

def _admin_token(user_id: int) -> str:
    import jwt
    payload = {"admin_id": user_id, "exp": datetime.utcnow() + timedelta(hours=12)}
    return jwt.encode(payload, ADMIN_SECRET, algorithm="HS256")

def require_admin(authorization: str, db: Session):
    if not authorization.startswith("Bearer "): return None
    try:
        payload = jwt.decode(authorization[7:], ADMIN_SECRET, algorithms=["HS256"])
        return db.query(AdminUser).filter(AdminUser.id == payload.get("admin_id")).first()
    except: return None
```

**前端导航绑定（常见遗漏！）**：
```javascript
// 必须显式绑定 click 事件，<a data-view="xxx"> 不会自动切换
document.querySelectorAll('.sidebar nav a').forEach(a => {
  a.addEventListener('click', () => switchView(a.dataset.view));
});
```
⚠️ **陷阱**：写了 `switchView()` 函数但没挂 click 监听器 → 点导航没反应、无报错。这是最常见的前端 bug。

**分页组件**：
```javascript
function pageCtrl(page, total, pageSize, fn) {
  return `<div class="pager"><span>共${total}条</span>
    <button class="btn-sm gray" onclick="${fn}(${page-1})">上一页</button>
    <span>第${page}页</span>
    <button class="btn-sm gray" onclick="${fn}(${page+1})">下一页</button></div>`;
}
```

**弹窗编辑回显**（用 USERS_CACHE 之类缓存当前页数据）：
```javascript
let USERS_CACHE = {};
// loadUsers 时填充
d.data.list.forEach(u => USERS_CACHE[u.id] = u);
// 打开弹窗时回显
function showModal(uid) {
  const user = USERS_CACHE[uid] || {};
  // 填充表单字段默认值
  document.getElementById('m_vip').value = String(user.vip_type || 0);
}
```

**日期时间控件**：
```javascript
// datetime-local 的 value 格式是 "YYYY-MM-DDTHH:MM"，需要转换
const expVal = user.vip_expire_time.replace(' ', 'T');  // DB → input
exp = m_exp.value.replace('T', ' ') + ':00';  // input → DB
```

**安全**：
- 管理员密码 BCrypt 存储
- 未登录访问管理 API → 401
- 管理员独立 JWT secret（即使业务 JWT 泄露，管理接口不受影响）

## 数据库表（管理员）
```sql
CREATE TABLE admin_user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 路由注册
```python
from app.api.admin_api import router as admin_router
app.include_router(admin_router, prefix="/api/admin", tags=["管理后台"])
```

## 依赖关系
- 业务模型（查询/修改用）
- `common/security.py`（hash_password, verify_password）
- `config/settings.py`（JWT_SECRET）
- `common/response.py`（success, fail 统一返回格式）

## 常见陷阱
- **导航不生效**：忘了 `addEventListener('click', ...)` 绑定
- **弹窗回显空**：没缓存列表数据，打开弹窗时拿不到当前用户的值
- **日期格式错误**：DB 是 `YYYY-MM-DD HH:MM:SS`，input datetime-local 是 `YYYY-MM-DDTHH:MM`，需要互相转换
- **管理员密码没 hash**：直接存明文 → 安全风险
- **前后端 secret 不一致**：前端用 JWT_SECRET 签发，后端用 JWT_SECRET+'_admin' 验证 → 401 永远不过
