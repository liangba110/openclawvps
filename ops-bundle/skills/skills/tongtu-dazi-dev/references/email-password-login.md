# 邮箱/手机号 + 密码登录模式

## 登录模式切换

平台支持两种登录模式之间的切换：

| 模式 | 说明 | 后端开关 |
|------|------|---------|
| **仅微信登录** | 只显示微信一键登录按钮 | `user.py login()` 首行 `return fail('仅支持微信登录')` |
| **多方式登录** | 同时支持微信 + 邮箱/手机号+密码 | 移除上述 `return fail` 即可恢复 |

## 当前状态

当前使用**多方式登录模式**。用户可在登录页通过 Tab 切换：
- Tab 1️⃣ 微信一键登录
- Tab 2️⃣ 账号密码（邮箱/手机号 + 密码 + 验证码）

## 后端 API

### `POST /api/user/login`

```python
# /opt/ttdazi/backend/app/user.py
data = request.get_json() or {}
username = data.get('phone', data.get('username', '')).strip()
password = data.get('password', '').strip()

# captcha 验证
ok, msg = require_captcha(data.get('captcha_key'), data.get('captcha_answer'))

# SQL 查询，同时支持 phone/username/email
cur.execute(
    "SELECT ... FROM `user` WHERE phone=%s OR username=%s OR email=%s",
    (username, username, username)
)
```

**关键**：`phone` 字段同时承载手机号、用户名、邮箱地址。后端 SQL 已在第一次实现时就支持三种登录方式。

### `POST /api/user/register-by-email`

邮箱注册流程（验证码 + 密码）：
1. 前端调用 `POST /api/user/send-email-code` 发送邮箱验证码
2. 用户填验证码 + 设置密码
3. 前端调用 `POST /api/user/register-by-email` 完成注册

## 前端 Login.vue

### 组件结构

```vue
<template>
  <!-- Tab 切换 -->
  <div class="login-tabs">
    <span @click="loginMode = 'wechat'">微信登录</span>
    <span @click="loginMode = 'password'">账号密码</span>
  </div>

  <!-- 微信登录 -->
  <div v-show="loginMode === 'wechat'">
    <button @click="wxLogin">微信一键登录</button>
  </div>

  <!-- 账号密码登录 -->
  <div v-show="loginMode === 'password'">
    <input v-model="account" placeholder="邮箱 / 手机号" />
    <input v-model="password" type="password" placeholder="密码" />
    <input v-model="captchaAnswer" placeholder="验证码" />
    <img :src="captchaImg" @click="refreshCaptcha" />
    <button @click="doLogin">登录</button>
    <span @click="goRegister">邮箱注册</span>
  </div>
</template>
```

### doLogin 函数

```js
async function doLogin() {
  const r = await api.post('/user/login', {
    phone: account.value.trim(),
    password: password.value,
    captcha_key: captchaKey.value,
    captcha_answer: captchaAnswer.value
  })
  localStorage.setItem('token', r.token)
  localStorage.setItem('user', JSON.stringify(r))
  router.push('/')
}
```

### 验证码

- 从 `api.get('/captcha/get')` 获取，响应格式 `{image: "...base64...", key: "..."}`
- 后端存储答案，API 不返回答案（用户看图输入）
- 验证码是数学题：`a + b = ?` / `max-min = ?` / `a × b = ?`
- 图像用 PIL 生成，白色背景，DejaVuSans 粗体

## 切换回「仅微信登录」模式

如果需要恢复仅微信登录：

### 后端
```python
# /opt/ttdazi/backend/app/user.py

# login() 开头加：
@user_bp.route('/login', methods=['POST'])
def login():
    return fail('仅支持微信登录')
    # 下面所有代码保留，return 后不会执行

# register_by_email() 同样：
@user_bp.route('/register-by-email', methods=['POST'])
def register_by_email():
    return fail('仅支持微信登录')
```

### 前端 Login.vue
- 删除 Tab 切换组件
- 删除账号密码输入框
- 只保留微信登录按钮
- 删除 doLogin 函数
- 删除 `safeToast`、`api`、`onMounted` 等不再需要的导入

### 路由
如果 `/email-register` 路由也不再需要，从 `router/index.js` 移除。

## 数据库

`user` 表字段：
- `email` VARCHAR(100) — 已存在
- `password` VARCHAR(255) — 已存在（bcrypt 哈希）
- `phone` VARCHAR(20) — 已存在

**已知 Bug**：邮箱注册时 `phone` 字段被填入邮箱地址（而非空字符串）。参见 SKILL.md 中「邮箱注册 phone 字段被填入邮箱地址」章节。
