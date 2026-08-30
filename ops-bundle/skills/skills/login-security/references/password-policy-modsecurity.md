# Password Policy & ModSecurity WAF Deployment

## Password Strength Enforcement

### Validation Function (in utils.py)

```python
PWD_MIN_LEN = 16
PWD_EXPIRE_DAYS = 90

def validate_password_strength(password: str) -> tuple:
    """校验密码强度，返回 (是否通过, 错误消息)"""
    if len(password) < PWD_MIN_LEN:
        return False, f'密码长度不能少于{PWD_MIN_LEN}位'
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    if not has_upper:
        return False, '密码必须包含大写字母'
    if not has_lower:
        return False, '密码必须包含小写字母'
    if not has_digit:
        return False, '密码必须包含数字'
    if not has_special:
        return False, '密码必须包含特殊符号'
    return True, ''
```

Integrate into `hash_password()`:
```python
def hash_password(password: str) -> str:
    ok, msg = validate_password_strength(password)
    if not ok:
        raise ValueError(msg)
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
```

### Password Expiry Tracking (DB)

```sql
ALTER TABLE user ADD COLUMN pwd_changed_at DATETIME DEFAULT NULL;
ALTER TABLE user ADD COLUMN pwd_expire_days INT DEFAULT 90;
```

### Check Function

```python
def check_password_expired(user_id: int) -> tuple:
    from datetime import datetime
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pwd_changed_at, pwd_expire_days FROM user WHERE id=%s", (user_id,))
            u = cur.fetchone()
            if not u: return False, 999
            if u['pwd_changed_at']:
                days = (datetime.now() - u['pwd_changed_at']).days
                expire = u['pwd_expire_days'] or 90
                return (True, 0) if days >= expire else (False, expire - days)
            return False, 90  # never changed, give grace period
    finally:
        conn.close()
```

### Login Check

```python
# After password verification in login():
from app.utils import check_password_expired
pwd_expired, remain_days = check_password_expired(user['id'])
if pwd_expired and user['role'] == 'admin':
    return fail('密码已过期，请联系管理员重置')
```

### Deprecate Weak Admin Accounts

1. Create new admin with strong password: ≥16 chars, mixed case, digits, special chars
2. Disable old `admin` account: `UPDATE user SET status=0 WHERE username='admin'`
3. Clean test accounts: `UPDATE user SET status=0 WHERE nickname LIKE '%测试%'`
4. Note: bcrypt must be installed for the Python version gunicorn uses

## ModSecurity WAF + Nginx Hardening

### Installation (Ubuntu)

```bash
sudo apt-get install -y libnginx-mod-http-modsecurity
```

### ModSecurity Rules (`/etc/nginx/modsecurity.conf`)

```
SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess Off
SecDataDir /tmp/modsecurity
SecRequestBodyLimit 10485760
SecRequestBodyNoFilesLimit 1048576

# SQL Injection — catch both raw and URL-encoded patterns
SecRule ARGS "(?i:\\b(or\\b\\s*\\d+\\s*[=<>]|and\\b\\s*\\d+\\s*[=<>]|union\\s+(all\\s+)?select|\\bselect\\s+.*\\bfrom\\b|information_schema|sleep\\s*\\(|benchmark\\s*\\(|0x[0-9a-f]{8,}))" "id:10001,phase:2,deny,status:403,msg:SQL Injection blocked"

# XSS
SecRule ARGS|ARGS_NAMES|REQUEST_URI "(?i:(<script[^>]*>|javascript:|onload\\s*=|onerror\\s*=|onclick\\s*=|alert\\s*\\(|prompt\\s*\\(|confirm\\s*\())" "id:10002,phase:2,deny,status:403,msg:XSS blocked"

# Path Traversal
SecRule REQUEST_URI|ARGS "(?i:(\\.\\.\\/|/etc/passwd|/etc/shadow|/proc/self))" "id:10003,phase:1,deny,status:403"

# Command Injection
SecRule ARGS "(?i:\\b(cmd\\s*=|command\\s*=|exec\\s*=|system\\s*=|passthru|shell_exec|popen|proc_open|eval\\s*\\(|assert\\s*\\(|base64_decode|phpinfo)\\b)" "id:10004,phase:2,deny,status:403"

# Malicious Scanner User-Agent
SecRule REQUEST_HEADERS:User-Agent "(?i:(acunetix|netsparker|sqlmap|nmap|nikto|nessus|openvas|wpscan|burpsuite|appscan|zap|hydra|medusa|havij|pangolin|w3af|dirbuster|gobuster|masscan|aircrack))" "id:10005,phase:1,deny,status:403"

Large Body
SecRule REQUEST_BODY "@gt 5242880" "id:10006,phase:2,deny,status:413"
```

### Nginx WAF Config (server block)

```nginx
# Enable ModSecurity
modsecurity on;
modsecurity_rules_file /etc/nginx/modsecurity.conf;

# CC Attack Protection — login rate limit (5r/m, burst 1)
location ~ /api/(user/login|user/register|admin/login|captcha|send-code|register-by) {
    limit_req zone=login_limit burst=1 nodelay;
    proxy_pass http://backend:5002;
}

# Admin backend — IP whitelist
location ~ ^/(op-manage-7x2d9|admin)(/|$) {
    limit_req zone=login_limit burst=1 nodelay;
    allow 42.193.113.230;  # Server A only
    allow 127.0.0.1;
    deny all;
    proxy_pass http://backend:5002;
}

# API — general rate limit
location /api/ {
    limit_req zone=api_limit burst=5 nodelay;
    client_max_body_size 10m;
    proxy_pass http://backend:5002;
}
```

### Reserved Zones (`http` block in nginx.conf)

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
```

**Warning:** Do NOT redefine `limit_req_zone` in both `nginx.conf` and `conf.d/*.conf` — causes "already bound" error. Define once in `nginx.conf`, use in server/location blocks.

### Admin IP Whitelist (Nginx level)

Restrict admin backend access to specific IPs:

```nginx
location ~ ^/(PRIVATE_PATH|admin)(/|$) {
    limit_req zone=login_limit burst=5 nodelay;
    allow 42.193.113.230;    # API server
    allow 127.0.0.1;         # localhost
    allow YOUR_STATIC_IP;    # operator's fixed IP
    deny all;
    proxy_pass http://backend:5002;
}
```

**Maintenance:**
- Add new IP: `ssh server "sudo sed -i '/allow 127.0.0.1;/a\        allow NEW_IP;' /etc/nginx/conf.d/ttdazi.conf && sudo nginx -s reload"`
- The rotation script (`rotate_admin_path.sh`) must also update the Nginx location pattern to match the new path

### Real‑World Rate‑Limit Tuning

**Symptom:** Normal users hitting 503 during login.

**Root cause:** Three stacked rate limiters with additive burst exhaustion — CAPTCHA errors count toward the Nginx `login_limit` count.

**Tuning outcome:**

```
Nginx login_limit:  10r/m, burst=5, nodelay   (was 5r/m, burst=1)
Backend IP limit:   5/min                      (unchanged)
Password lock:      5 fails → 15 min lock      (was 3 fails → 10 min)
```

With burst=5, a normal user can mistype up to ~6 times before Nginx rate‑limits (the first 3 get CAPTCHA errors, the next 3 get backend 429, the 7th+ gets Nginx 503). The password lock at 5 failures is the last resort.

### Login CAPTCHA — Now Mandatory for Admin Too

The `skip_captcha=true` bypass has been removed from both `user.py` and `admin.py`. All login endpoints now require a valid CAPTCHA.

**Admin login CAPTCHA integration:**

```python
# admin.py — admin_login()
from app.captcha import require_captcha
ok, msg = require_captcha(data.get('captcha_key'), data.get('captcha_answer'))
if not ok:
    return fail(msg)

from app.ratelimit import check_pwd_lock, record_pwd_fail, reset_pwd_fails
allowed, lock_msg = check_pwd_lock(username)
if not allowed:
    return fail(lock_msg, code=429)
```

```javascript
// AdminLogin.vue
const captchaImage = ref('')
const captchaKey = ref('')
const captchaAnswer = ref('')

function refreshCaptcha() {
  api.get('/captcha/get').then(r => {
    captchaImage.value = r.image
    captchaKey.value = r.key
  })
}
refreshCaptcha()

// Refresh and clear on every attempt (success or failure)
finally { refreshCaptcha(); captchaAnswer.value = '' }
```

### Login Failure Logging

Every login failure is now recorded in the existing `login_log` table:

```python
# user.py
def _record_login_log(user_id, ip, device_id, status, reason=''):
    """记录登录日志到数据库"""
    if not user_id: return
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO login_log (user_id, ip, device_id, user_agent, city, is_new_device, is_new_city) "
                "VALUES (%s, %s, %s, %s, '', 0, 0)",
                (user_id, ip, device_id, request.headers.get('User-Agent','')[:200])
            )
            conn.commit()
    finally:
        conn.close()

# Call on every failed login path
_record_login_log(user['id'], get_client_ip(), '', 'fail', '密码错误')
_record_login_log(0, get_client_ip(), '', 'fail', '用户不存在')  # 0 = unknown user
```

### Verification

```bash
# Security headers
curl -sI http://example.com/ | grep -i "x-frame\|x-content\|x-xss\|referrer\|permissions"
# SQL injection
curl -s -o /dev/null -w "%{http_code}" "http://example.com/api/list?id=1%20OR%201=1"
# Scanner
curl -s -o /dev/null -w "%{http_code}" -A "sqlmap/1.7" http://example.com/
# Path traversal
curl -s -o /dev/null -w "%{http_code}" "http://example.com/../../../etc/passwd"
# Admin IP whitelist
curl -s -o /dev/null -w "%{http_code}" http://example.com/api/admin/users
# CAPTCHA required
curl -s -o /dev/null -w "%{http_code}" -X POST http://example.com/api/user/login \
  -H 'Content-Type: application/json' \
  -d '{"phone":"138xxx","password":"wrong","captcha_key":"","captcha_answer":""}'
```

## Deploy Credential Security

**Never** store server passwords in deploy scripts. Migrate to SSH key authentication:

```bash
# Generate key (one-time)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
ssh-copy-id user@target-server

# Then deploy with plain scp/ssh (no password variable, no sshpass)
scp -r dist/* user@server:/path/
ssh user@server "sudo nginx -s reload"
```

Check deploy scripts for:
```bash
grep -n "PASS=\|password\|sshpass" deploy.sh
# Remove: SERVER_B_PASS variable, sshpass commands, plaintext credentials
```
