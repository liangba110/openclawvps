# 同途搭子全栈审计与修复模式

## 并行多代理审计（本期验证有效）

上线前用 **3个子代理并行** 进行全量审计：

```python
from hermes_tools import delegate_task

# 并行派发3个审计任务
delegate_task(goal="用户端25页逐页检查", context="...")
delegate_task(goal="管理端19页逐页检查", context="...")
delegate_task(goal="后端27API文件逐文件检查", context="...")
```

### 检查维度

| 审计项 | 子代理数 | 检查文件数 | 发现🔴问题 |
|--------|---------|-----------|-----------|
| 用户端 | 1 | 25 .vue | 31 |
| 管理端 | 1 | 19 .vue | 6 |
| 后端API | 1 | 27 .py | 9 |

### 审计后修复优先级

1. **🔴 安全漏洞** — 认证装饰器缺失、字段白名单溢出、SQL注入
2. **🔴 功能崩溃** — 未定义变量、404端点、字段不匹配
3. **🟡 一致性** — 管理端布局 margin-left、全局样式类
4. **🟡 UX** — 空catch吞错误、rating=0显示5星

## catch 替换规则

### 规则1: 页面加载的 catch 保持静默

```javascript
// ✅ 正确 — captcha/onMounted等初始加载，错误应静默
async function refreshCaptcha() {
  try {
    const r = await api.get('/captcha/get')
    captchaImage.value = r.image
  } catch {}  // ✅ 初始加载，用户可点图重试
}

// ❌ 错误 — 批量替换时误改，导致每页加载都弹"操作失败" toast
async function refreshCaptcha() {
  try {
    ...
  } catch(e) { safeToast(e?.message || "操作失败") }  // ❌ 烦人的 toast
}
```

### 规则2: 用户操作的 catch 必须 toast

```javascript
// ✅ 正确 — 用户主动点击操作的错误应告知
async function submitForm() {
  try {
    await api.post('/submit', data)
  } catch(e) { safeToast(e?.message || '提交失败') }
}
```

### 规则3: 三类常见的"故意静默"catch

| 场景 | 原因 | 替代方案 |
|------|------|---------|
| 初始加载 `onMounted` | 页面可无数据显示 | 空v-if处理 |
| 验证码刷新 `refreshCaptcha` | 用户可点图重试 | 保持静默 |
| 辅助数据加载 `loadXxx()` | 非关键数据 | 默认值兜底 |

## 邮箱注册域名 @ 前缀陷阱

**症状：** 页面显示 `user@@qq.com`

**根因：** `EMAIL_DOMAINS` 数组值带 `@` + 模板 `<span>@</span>`

```javascript
// ❌ 错误
const EMAIL_DOMAINS = ['@qq.com', '@163.com']
// 模板: <span>名字</span> <span>@</span> <select>@qq.com</select>
// 结果: 名字 @ @qq.com

// ✅ 正确
const EMAIL_DOMAINS = ['qq.com', '163.com']
```

## admin_required 导入路径

`admin_required` 装饰器始终在 `app.admin` 中定义，**不**在 `app.utils` 中。

```python
# ❌ 错误 — 会在 gunicorn 启动时报 NameError
from app.utils import admin_required

# ✅ 正确
from app.admin import admin_required
```

创建新的管理端API文件时，如果用到 `@admin_required`，必须从 `app.admin` 导入。

## 管理端页面布局检查

所有 admin 页面的模板结构：

```vue
<div class="admin-layout">
  <AdminSidebar />       <!-- 固定定位，z-index高 -->
  <div class="admin-main"> <!-- CSS必备: margin-left: 220px -->
    ...
  </div>
</div>
```

`.admin-main { margin-left: 220px }` 是**必需**的——sidebar 是 `position: fixed`，不设置 margin-left 会导致内容被 sidebar 遮挡。

容易遗漏的 8 个页面：AdminDashboard, AdminPlaymates, AdminOrders, AdminContent, AdminWithdrawals, AdminMonitor, AdminConfig, AdminFeedback。

## 公共API vs 管理端API 区分

管理端页面绝不能调公共API，否则绕过权限校验：

| 公共API | 管理端应该用的API |
|---------|-----------------|
| `GET /review/list` | `GET /admin/reviews` |
| `POST /review/submit` | 不用（用户端提交） |
| `POST /review/reply` | `POST /admin/review/status` |
