# Email Verification Code with SMTP

## QQ Email SMTP Configuration

| Setting | Value |
|---------|-------|
| SMTP Server | `smtp.qq.com` |
| SSL Port | `465` |
| TLS Port | `587` |
| Auth | Email address + **SMTP Authorization Code** (NOT the email password) |

## How to Get the Authorization Code

1. Log into QQ Mail → Settings → Account → POP3/SMTP Service
2. Click "Enable" → Generate authorization code
3. Save the code — it's only shown once

## Flask/Python Implementation

### 1. Send code endpoint

```python
@user_bp.route('/send-email-code', methods=['POST'])
def send_email_code():
    email = request.get_json().get('email', '').strip().lower()

    # Validate email format
    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return fail('请输入正确的邮箱地址')

    # Rate limit: 60s between sends
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT code, created_at FROM verify_codes WHERE email=%s ORDER BY created_at DESC LIMIT 1", (email,))
            row = cur.fetchone()
            if row:
                elapsed = (datetime.now() - row['created_at']).total_seconds()
                if elapsed < 60:
                    return fail(f'请{int(60-elapsed)}秒后再试')

            # Generate 6-digit code and store in DB
            code = f'{random.randint(100000, 999999)}'
            cur.execute("DELETE FROM verify_codes WHERE email=%s", (email,))
            cur.execute("INSERT INTO verify_codes (email, code, created_at) VALUES (%s, %s, %s)",
                        (email, code, datetime.now()))
            conn.commit()
    finally:
        conn.close()

    # Send via SMTP
    try:
        import smtplib
        from email.mime.text import MIMEText

        smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
        smtp.login('your-email@qq.com', 'your-authorization-code')

        msg = MIMEText(f'您的验证码是：{code}，有效期10分钟。', 'plain', 'utf-8')
        msg['Subject'] = f'验证码：{code}'
        msg['From'] = 'your-email@qq.com'
        msg['To'] = email

        smtp.sendmail('your-email@qq.com', [email], msg.as_string())
        smtp.quit()
    except Exception as e:
        print(f'SMTP failed: {e}')
        return fail('验证码发送失败，请稍后再试')

    # In development, return the code for testing
    return success({'_dev_code': code}, '验证码已发送')
```

### 2. Verify code endpoint

```python
@user_bp.route('/verify-email-code', methods=['POST'])
def verify_email_code():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT code, created_at FROM verify_codes WHERE email=%s ORDER BY created_at DESC LIMIT 1", (email,))
            row = cur.fetchone()
            if not row:
                return fail('请先获取验证码')

            elapsed = (datetime.now() - row['created_at']).total_seconds()
            if elapsed > 600:  # 10 minutes
                cur.execute("DELETE FROM verify_codes WHERE email=%s", (email,))
                conn.commit()
                return fail('验证码已过期')

            if row['code'] != code:
                return fail('验证码错误')

            cur.execute("UPDATE verify_codes SET verified=1 WHERE email=%s AND code=%s", (email, code))
            conn.commit()
    finally:
        conn.close()

    return success(None, '验证通过')
```

### 3. Register with verified code

```python
@user_bp.route('/register-by-email', methods=['POST'])
def register_by_email():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    password = data.get('password', '').strip()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT code, verified, created_at FROM verify_codes WHERE email=%s ORDER BY created_at DESC LIMIT 1", (email,))
            row = cur.fetchone()
            if not row:
                return fail('请先获取验证码')
            if not row['verified']:
                return fail('请先验证验证码')
            if row['code'] != code:
                return fail('验证码错误')

            # Check existing user
            cur.execute("SELECT id FROM `user` WHERE username=%s", (email,))
            if cur.fetchone():
                return fail('该邮箱已注册')

            # Create user
            hashed = hash_password(password)
            cur.execute("INSERT INTO `user` (username, password, nickname, role, status) VALUES (%s, %s, %s, 'user', 1)",
                        (email, hashed, email.split('@')[0]))
            conn.commit()
            user_id = cur.lastrowid
            cur.execute("DELETE FROM verify_codes WHERE email=%s", (email,))
            conn.commit()

        token = create_token(user_id, email)
        return success({'token': token, 'id': user_id, 'nickname': email.split('@')[0]}, '注册成功')
    finally:
        conn.close()
```

## Database Table

```sql
CREATE TABLE IF NOT EXISTS verify_codes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  phone VARCHAR(11) DEFAULT NULL,
  email VARCHAR(100) DEFAULT NULL,
  code VARCHAR(6) NOT NULL,
  verified TINYINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_phone (phone),
  INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Pitfalls

- **Gunicorn multi-worker**: Always store codes in the database, NOT in-memory dicts. Gunicorn workers are separate processes — in-memory state is NOT shared.
- **SMTP credentials**: Use the SMTP authorization code, NOT the email login password. Store in environment variables or config file, never hardcoded in committed code.
- **Rate limiting**: Always implement time-based rate limiting (60s between sends) to prevent abuse.
- **Expiration**: Set a reasonable TTL (5-10 minutes). Clean up expired codes on read.
- **Dev mode**: Return `_dev_code` in the response for development/testing. Remove in production.
