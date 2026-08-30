# 全栈功能创建模式

## 意见反馈系统（本期完整示例）

新增一个完整功能的流程，以本期「意见反馈」功能为例：

### 1. 数据库

CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    reply TEXT,
    replied_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

### 2. 后端 API（app/feedback.py）

- 用户提交: POST /api/feedback/submit @login_required
- 用户查看历史: GET /api/feedback/my @login_required
- 管理后台列表: GET /api/feedback/admin/list @admin_required（JOIN user 表）
- 管理员回复: POST /api/feedback/admin/reply @admin_required

⚠️ admin_required 在 app.admin 里，不在 app.utils！

### 3. 注册蓝图（main.py 三处检查）

① 文件顶部 import from app.feedback import feedback_bp
② create_app() 中 app.register_blueprint(feedback_bp)
③ 不要误删现有行（coupon_bp 曾因 patach 丢失！）

每次改完 main.py 后 grep 'from app\\.' main.py | sort 检查所有 bp 导入是否完整。

### 4. 管理端页面（AdminFeedback.vue）

标准 admin-layout + AdminSidebar 布局，列表含用户名/脱敏手机/内容/时间/回复状态，每条底部有输入框可回复，分页支持。

### 5. 用户端页面（MyFeedback.vue）

.page + .header-bar 标准布局，3D 立体卡片展示每条反馈：状态标签（已回复/待回复）、内容正文、回复蓝边区域。空状态引导提交。

### 6. 路由 & 入口

- router/index.js 加两条路由（/my-feedback 和 /op-ztHWaT-0706/feedback）
- AdminSidebar.vue 加菜单项
- Settings.vue 加两个入口：「意见反馈」弹窗提交 + 「我的反馈」独立页面

### 新增功能 checklist

1. 数据库建表（CREATE TABLE IF NOT EXISTS）
2. 后端 API 文件 + routes + blueprint
3. main.py 三处检查（import + register + 不误删）
4. 管理端页面 + 侧栏 + 路由
5. 用户端页面 + 路由 + 入口
6. 构建部署验证（npm run build && deploy）
7. 端到端测试（curl 模拟完整链路）
