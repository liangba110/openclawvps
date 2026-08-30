# 微信唯一登录方式转换

## 场景

用户要求移除所有其他登录/注册方式，只保留微信OAuth一键登录。

## 改动清单

### 1. 前端 — Login.vue

重写为仅保留微信登录按钮，移除密码登录、验证码登录、邮箱注册、公众号注册。

```vue
<template>
  <div class="login-page">
    <div class="login-card card-3d" style="text-align:center">
      <div class="login-logo">...</div>
      <button class="wechat-btn" @click="wxLogin">
        <span class="wx">💚</span> 微信一键登录
      </button>
      <div class="login-agreement">
        <label>登录即表示同意《用户协议》和《隐私政策》</label>
      </div>
    </div>
  </div>
</template>
<script setup>
function wxLogin() { window.location.href = '/api/wechat/login' }
</script>
```

**关键点**：
- 移除 `mode`（'pwd'/'code'）、`account`、`password`、`smsCode`、`codeAccount` 等变量
- 移除 `doLogin()`、`doCodeLogin()`、`sendCode()`、`saveLogin()` 函数
- 移除请求验证码相关逻辑（`captchaImage`、`captchaKey`、`refreshCaptcha`）
- 样式：`.wechat-btn` 用微信绿 `#07c160`，移除旧按钮样式

### 2. 前端 — 路由

从 `router/index.js` 移除注册相关路由：

```js
// ❌ 移除
{ path: '/register', name: 'Register', ... },
{ path: '/follow-register', name: 'FollowRegister', ... },
{ path: '/email-register', name: 'EmailRegister', ... },
```

### 3. 后端 — user.py

在 `login()`, `register()`, `register_by_code()`, `register_by_email()` 函数第一行添加：

```python
def login():
    return fail('仅支持微信登录')
    # 原有代码被 return 跳过
```

同样修改 `register()`、`register_by_code()`、`register_by_email()`。

不要删除原函数体，仅添加 return 语句，方便后续恢复。

### 4. 新增加路由

```js
// 微信登录后手机号绑定页
{ path: '/bind-phone', name: 'BindPhone', component: () => import('@/views/BindPhone.vue') },
```

### 5. 新增文件

- `frontend/src/views/BindPhone.vue` — 手机号绑定页面（输入手机号 + 验证码绑定，路由 `/bind-phone`）
- 后端 `POST /api/wechat/send-code` — 发送验证码（60s限流）
- 后端 `POST /api/wechat/bind-phone` — 绑定手机号（校验 token + 验证码）

### 6. 删除文件

```bash
rm /opt/ttdazi/frontend/src/views/CreateDemand.vue  # 如已删除需求发布
rm /opt/ttdazi/frontend/src/views/Register.vue
rm /opt/ttdazi/frontend/src/views/FollowRegister.vue
rm /opt/ttdazi/frontend/src/views/EmailRegister.vue
```

### 5. 构建部署

```bash
find /opt/ttdazi/backend -name "__pycache__" -type d -exec rm -rf {} +
sudo systemctl restart ttdazi
cd /opt/ttdazi/frontend && npm run build && bash /opt/ttdazi/deploy.sh
```

## 验证

```bash
# 旧登录接口应返回「仅支持微信登录」
curl -sk -X POST https://dazi.openai2000.cn/api/user/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","password":"123456"}'
# → {"code":1,"msg":"仅支持微信登录"}

# 登录页应包含微信按钮
grep -c '微信一键登录' /opt/ttdazi/frontend/dist/assets/Login-*.js
# → 输出应 > 0
```

## 恢复

如需恢复，git revert 对应 commit 即可。
