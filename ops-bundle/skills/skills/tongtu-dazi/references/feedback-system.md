# 意见反馈系统（本期新增）

## 数据库

```sql
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    reply TEXT,
    replied_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 后端 API

| 方法 | 路径 | 权限 | 功能 |
|------|------|------|------|
| POST | `/api/feedback/submit` | `@login_required` | 用户提交反馈 |
| GET | `/api/feedback/my` | `@login_required` | 用户查看自己的反馈+回复 |
| GET | `/api/feedback/admin/list` | `@admin_required` | 管理后台列表（分页） |
| POST | `/api/feedback/admin/reply` | `@admin_required` | 管理员回复 |

### 注册蓝图

```python
# main.py 三处检查：
from app.feedback import feedback_bp          # 1. import
app.register_blueprint(feedback_bp)            # 2. register
# 3. 不要误删相邻的 from app.coupon / from app.config 等
```

### admin_required 导入（易错）

```python
# ❌ 在 feedback.py 中错误导入
from app.utils import login_required, admin_required, success, fail
# ✅ 正确 — admin_required 在 app.admin 中
from app.utils import login_required, success, fail
from app.admin import admin_required
```

## 前端

### 用户端（Settings.vue → 帮助与支持）

- **意见反馈**：弹出 modal → textarea → `POST /api/feedback/submit`
- **我的反馈**：独立页面 `MyFeedback.vue` → 路由 `/my-feedback` → 3D卡片列表

### 管理端

- 页面：`AdminFeedback.vue` → 路由 `/op-ztHWaT-0706/feedback`
- 侧栏：`AdminSidebar.vue` 新增 `📝 意见反馈` 菜单项
- 功能：列表（昵称+手机号+内容+时间）+ 输入框回复

### 页面功能

- 每条反馈用 3D 立体卡片展示
- 顶部显示状态标签（✅ 已回复 / ⏳ 待回复）
- 中间显示用户提交的内容
- 管理员回复后用蓝色左边框区域显示回复内容+时间
- 空状态引导提交反馈

## 部署

```bash
bash /opt/ttdazi/deploy.sh
# 先创建表再重启，否则首次请求时表不存在
```
