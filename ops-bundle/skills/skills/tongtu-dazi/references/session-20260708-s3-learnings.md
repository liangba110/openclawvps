# Session 2026-07-08 S3 — 实名认证 + 陪玩师通知 + 在线状态 审计修复

## 新增知识点

### 1. 双表同步模式（verify_application ↔ user）

**场景：** 用户提交易到 app/user.py，管理员审核读 app/admin.py。用户表和申请表必须同步。

**写入：** 一次事务同时 INSERT verify_application + UPDATE user
**读取：** 主查询读 verify_application，backfill 补充 user 表中无对应记录的历史数据
**审批（vid=0）：** backfill 记录无 verify_application.id → 从请求体取 user_id 直接更新 user 表

### 2. 真实在线状态（login_log）

companion.is_online 默认 1，从未更新 → 不可信。
用 login_log 表 5 分钟内登录判断。

### 3. 陪玩师通知全链路

apply → 通知用户 + 通知管理员
approve/reject → 通知用户

### 4. 管理后台快捷操作路径修复

AdminDashboard 快捷操作路径不能在模板中调 sessionStorage（Vue 3 不可访问）。

### 5. 陪玩师审核 500 错误

两个 Bug：cur 在 with 块外使用 + companion 表无 nickname 列。

### 6. 文件上传

- form.append('image', file) 后端需兼容 'image' 和 'file' 字段名
- 文件保存路径 vs Flask 静态服务路径要一致
