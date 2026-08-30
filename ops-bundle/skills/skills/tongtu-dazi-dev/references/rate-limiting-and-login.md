# Rate Limiting + Login System Patterns

## Rate Limiting Architecture (`backend/app/ratelimit.py`)

In-memory sliding window — no Redis dependency, sufficient for single-server gunicorn.

### Login Rate Limit

**IP-based:** 5 requests per minute per IP (sliding window).
**Account lockout:** 3 wrong passwords → 10 minute lock.

```python
@user_bp.route('/login', methods=['POST'])
@login_ip_limit  # IP rate limit decorator
def login():
    ...
    # Password lock check
    allowed, msg = check_pwd_lock(username)
    if not allowed:
        return fail(msg, code=429)

    if not user:
        record_pwd_fail(username)  # count as fail
        return fail('用户不存在')
    if not check_password(...):
        record_pwd_fail(username)
        return fail('密码错误')

    reset_pwd_fails(username)  # clear on success
```

### Verification Code Rate Limit

```python
allowed, msg = check_code_limit(phone, ip)
if not allowed:
    return fail(msg, code=429)
```

Rules:
- Per account: 60-second interval between sends
- Per IP: 20 sends per day
- Uses `_code_buckets` and `_code_ip_buckets` dicts with timestamp lists

## Login Page Patterns

### Dual-Mode Login (Password + Email Verification Code)

```vue
<div class="login-tabs">
  <span :class="{active:mode==='pwd'}" @click="mode='pwd'">密码登录</span>
  <span :class="{active:mode==='code'}" @click="mode='code'">验证码登录</span>
</div>
```

**Password mode:** Accepts both phone and email via single `account` field:
```js
const loginData = { password: password.value }
if (account.value.includes('@')) {
  loginData.username = account.value  // email → backend username field
} else {
  loginData.phone = account.value      // phone → direct login
}
```

**Verification code mode:** Email only:
```js
await api.post('/user/send-email-code', { email: email.value })
// 60s countdown
await api.post('/user/register-by-email', { email: email.value, code: smsCode.value })
```

### Remember Me
```js
localStorage.setItem('remembered_login', JSON.stringify({
  account: account.value, password: password.value
}))
// Restore on mount:
const data = JSON.parse(localStorage.getItem('remembered_login'))
account.value = data.account || data.phone || ''  // backward compat
```
