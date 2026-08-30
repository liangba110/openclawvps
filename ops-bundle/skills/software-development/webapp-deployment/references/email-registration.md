# Email Registration Flow

## Overview

A registration flow using email verification code instead of phone SMS or WeChat.
The frontend calls `send-email-code`, then `verify-email-code`, then `register-by-email`.

## Architecture (with QR Dialog)

```
User enters email → clicks "获取验证码"
                           │
                           ▼
              ┌──────────────────────────┐
              │ QR Dialog: 关注公众号      │
              │  [QR code image]         │
              │  "已关注，发送验证码"       │
              │  "稍后再说"               │
              └──────────────────────────┘
                           │ (after confirm)
                           ▼
              SMTP sends code → User checks email
              User enters code → Verify → Register
```

## Backend API Endpoints

Under `/api/user/`:

### 1. `POST /send-email-code`
- Input: `{"email": "user@example.com"}`
- Validates email format with regex
- Generates 6-digit code, stores in `verify_codes` table (same table as phone codes)
- **Uses `email` column** in `verify_codes` table (not `phone`)
- Rate-limited: 60-second cooldown per email
- Expiry: 10 minutes (600 seconds — longer than phone's 5 min)
- **Real SMTP sending**: When configured, sends HTML email via `smtplib.SMTP_SSL`

### 2. `POST /verify-email-code`
- Input: `{"email": "...", "code": "..."}`
- Looks up by `email` column (not `phone`)
- Marks `verified=1`

### 3. `POST /register-by-email`
- Input: `{"email": "...", "code": "...", "password": "...", "nickname": "..."}`
- Username = email address (stored in `username` column)
- Phone column = email address (reused as secondary identifier)
- Default nickname = email username part (`email.split('@')[0]`)
- Avatar: `'📧'` (distinguishes email users from phone users)
- Re-validates code, checks for existing email, creates user
- **Must return both `id` AND `user_id`** in the response for frontend consistency

## SMTP Configuration (QQ Mail Example)

```python
import smtplib
from email.mime.text import MIMEText
from email.header import Header

smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
smtp.login('your-email@qq.com', 'your-smtp-auth-code')  # auth code, NOT password

msg = MIMEText(f'<div>验证码：<strong>{code}</strong></div>', 'html', 'utf-8')
msg['Subject'] = Header(f'验证码：{code}', 'utf-8')  # Always use Header() for Chinese
msg['From'] = 'your-email@qq.com'
msg['To'] = recipient

smtp.sendmail('your-email@qq.com', [recipient], msg.as_string())
smtp.quit()
```

## Database

Reuses `verify_codes` table with `email` column. Both `phone` and `email` may be NULL:
```sql
ALTER TABLE verify_codes ADD COLUMN email VARCHAR(100) DEFAULT NULL AFTER phone, MODIFY phone VARCHAR(11) DEFAULT NULL;
CREATE TABLE verify_codes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  phone VARCHAR(11) DEFAULT NULL,
  email VARCHAR(100) DEFAULT NULL,
  code VARCHAR(6) NOT NULL,
  verified TINYINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_phone (phone), INDEX idx_email (email)
);
```

## Frontend: Email Input Split

```html
<div class="email-split">
  <div class="input-group email-name">
    <input type="text" v-model="emailName" placeholder="邮箱名" />
  </div>
  <span class="email-at">@</span>
  <div class="email-domain-wrap">
    <select v-model="emailDomain" class="email-domain">
      <option v-for="d in domains" :key="d" :value="d">{{ d }}</option>
    </select>
  </div>
</div>
```

```css
.email-name input { border-radius: 10px 0 0 10px; }
.email-domain { border-radius: 0 10px 10px 0; border-left: none; }
```

```js
const domains = ['@qq.com','@163.com','@gmail.com','@outlook.com','@sina.com',
  '@aliyun.com','@foxmail.com','@hotmail.com','@yeah.net','@126.com','@139.com']
const email = computed(() => emailName.value + emailDomain.value)
```

## Frontend: QR Dialog

Before sending code, show a modal:
```js
const showQrDialog = ref(false)
async function sendCode() {
  if (!emailName.value) { safeToast('请输入邮箱名'); return }
  showQrDialog.value = true
}
async function confirmFollow() {
  showQrDialog.value = false
  sending.value = true
  // call /api/user/send-email-code with email.value
}
```

## Login Page Links

```html
<span class="link" @click="$router.push('/email-register')">邮箱注册</span>
<span class="sep">|</span>
<span class="link" @click="$router.push('/follow-register')">公众号注册</span>
```

## Pitfalls

- **SMTP Subject encoding**: Always `Header('中文', 'utf-8')`. Plain assignment fails.
- **Return `id` AND `user_id`**: Profile avatar upload guard checks `u.id`.
- **safeToast**: Use `@/utils/toast` wrapper, not raw `showToast` from vant.
- **SMTP blocks**: Wrapping in try/except is essential; consider background queue in production.
- **QR dialog z-index**: Set `z-index: 1000` on the overlay.
