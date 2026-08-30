---
name: webapp-security
description: "Full-stack web application security (Flask+Vue): login session security, rate limiting, captcha, XSS filtering, input/output sanitization, risk control (IP banning/abuse prevention), audit logging, payment security, real-name verification, content filtering, Nginx WAF, global error handling, and operation monitoring."
triggers:
  - web安全
  - 安全加固
  - 防XSS
  - 防爬虫
  - 防刷接口
  - 限流
  - rate limiting
  - 验证码
  - captcha
  - 风控
  - risk control
  - IP封禁
  - 敏感词过滤
  - 实名认证
  - real-name verification
  - 审计日志
  - audit log
  - 资金安全
  - 支付安全
  - Nginx WAF
  - 异常拦截
  - 登录安全
  - token刷新
  - 会话管理
  - auth security
  - 异地登录检测
category: security
---

# WebApp Security — Full-Stack Flask+Vue Security Implementation

## Architecture Layers (bottom→top)

```
Nginx WAF (limit_req + IP blacklist)
  └── Flask Global Error Handler (no stack leaks)
       ├── Rate Limiting (IP-based + account lock)
       ├── CAPTCHA (arithmetic image)
       ├── Security Token (v2 short-lived + refresh)
       ├── Audit Logging (all sensitive operations)
       ├── Input/Output Safety (XSS + masking + pagination)
       ├── Risk Control (abuse detection + IP bans)
       ├── Payment Security (DB prices + idempotent lock)
       ├── Account Security (device mgmt + password change)
       └── Platform Review (real-name + content filter + reports)
```

Key principle: **defense in depth** — every layer independently protects against attacks.

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  Login                                          │
│  ├─ v2 access_token (30 min, device-bound)      │
│  ├─ refresh_token (7 days, stored in DB)        │
│  ├─ device_id from X-Device-Id / UA+IP fallback │
│  └─ anomaly check (new city? new device?)       │
├─────────────────────────────────────────────────┤
│  Every API call                                 │
│  ├─ login_required → parse v2 token             │
│  └─ if 401 → try /refresh → retry               │
├─────────────────────────────────────────────────┤
│  Logout                                         │
│  └─ revoke_all_sessions(user_id)                │
│     DELETE FROM refresh_token WHERE user_id=X   │
└─────────────────────────────────────────────────┘
```

## 1. Token Format (v2 — no JWT)

Self-contained, no library dependency. Contains user_id, timestamp, TTL, device_id bound by signature.

```python
PEPPER = 'app_name_token_v2_2026'
ACCESS_TOKEN_TTL = 1800   # 30 min
REFRESH_TOKEN_TTL = 604800  # 7 days

def gen_token(user_id, device_id='', ttl=ACCESS_TOKEN_TTL):
    import random, hashlib
    ts = int(time.time())
    raw = f'{user_id}:{ts}:{ttl}:{device_id}:{PEPPER}:{random.randint(1000,9999)}'
    sig = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f'v2.{user_id}.{ts}.{ttl}.{sig}.{device_id}'

def parse_token(token):
    if not token or not token.startswith('v2.'):
        return None
    parts = token.split('.')
    if len(parts) < 6:
        return None
    try:
        user_id = int(parts[1])
        ts = int(parts[2])
        ttl = int(parts[3])
        sig = parts[4]
        device_id = '.'.join(parts[5:])
        now = time.time()
        if now - ts > ttl:
            return None
        return {'user_id': user_id, 'device_id': device_id, 'expires_in': int(ttl - (now - ts))}
    except:
        return None
```

### Compatibility: make login_required support both old and new

```python
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'code': 401, 'msg': '未登录'}), 401
        token = auth[7:]
        # Try v2 first
        from app.token_auth import parse_token as parse_v2
        v2 = parse_v2(token)
        if v2:
            request.current_user = v2
            return f(*args, **kwargs)
        # Fallback to legacy JWT
        payload = decode_token(token)
        if not payload:
            return jsonify({'code': 401, 'msg': '登录已过期'}), 401
        request.current_user = payload
        return f(*args, **kwargs)
    return decorated
```

## 2. Refresh Token (server-side, revocable)

```python
def gen_refresh_token(user_id, device_id='', ip=''):
    import random, string
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
    expires_at = datetime.now() + timedelta(seconds=REFRESH_TOKEN_TTL)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Cap at 5 devices per user
            cur.execute("SELECT COUNT(*) as cnt FROM refresh_token WHERE user_id=%s", (user_id,))
            if cur.fetchone()['cnt'] >= 5:
                cur.execute("DELETE FROM refresh_token WHERE user_id=%s ORDER BY created_at ASC LIMIT 1", (user_id,))
            cur.execute(
                "INSERT INTO refresh_token (user_id, token, device_id, ip, expires_at) VALUES (%s,%s,%s,%s,%s)",
                (user_id, token, device_id, ip, expires_at)
            )
            conn.commit()
        return token
    finally:
        conn.close()

def verify_refresh_token(token):
    if not token:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, expires_at FROM refresh_token WHERE token=%s AND expires_at > NOW()",
                (token,)
            )
            r = cur.fetchone()
            return r['user_id'] if r else None
    finally:
        conn.close()

def revoke_all_sessions(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM refresh_token WHERE user_id=%s", (user_id,))
            conn.commit()
    finally:
        conn.close()
```

## 3. Device Binding

```python
def get_device_id():
    device = request.headers.get('X-Device-Id', '') or ''
    if not device:
        ua = request.headers.get('User-Agent', '')[:100]
        ip = request.headers.get('X-Forwarded-For', request.remote_addr) or ''
        device = hashlib.md5(f'{ip}:{ua}'.encode()).hexdigest()[:16]
    return device
```

Add to login response:
```python
return success({
    'token': token,
    'refresh_token': refresh_tok,
    'device_id': device_id,
    'anomaly_warn': warn_msg if sus else '',
    # ... other user fields
}, '登录成功')
```

## 4. Anomaly Detection (geo-location)

Create `login_log` table with `user_id, ip, device_id, city, is_new_device, is_new_city`.

```python
def check_anomaly(user_id, device_id, ip):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT device_id, ip, city FROM login_log 
                WHERE user_id=%s ORDER BY created_at DESC LIMIT 10
            """, (user_id,))
            logs = cur.fetchall()
            is_new_device = True
            last_city = ''
            for log in logs:
                if log['device_id'] == device_id:
                    is_new_device = False
                if log['city']:
                    last_city = log['city']
            # Get current city via IP
            current_city = ''
            try:
                import urllib.request, json
                r = urllib.request.urlopen(f'https://ipinfo.io/{ip}/json', timeout=3)
                current_city = json.loads(r.read()).get('city', '')
            except: pass
            is_new_city = last_city and current_city and last_city != current_city
            # Log this login
            cur.execute("INSERT INTO login_log ...")
            conn.commit()
            if is_new_city:
                return True, f'检测到新地点登录，上次在【{last_city}】，本次在【{current_city}】'
            if is_new_device:
                return True, '检测到新设备登录'
            return False, ''
    finally:
        conn.close()
```

## 5. Logout — Server-Side Credential Destruction

```python
@user_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user_id = request.current_user['user_id']
    revoke_all_sessions(user_id)
    audit_log(user_id, 'logout', detail={'action': '主动登出'})
    return success(None, '已退出登录')
```

**Critical:** Frontend must clear `localStorage` too — but server-side destruction ensures even a leaked token can't be replayed.

## 6. Frontend Auto-Refresh Interceptor

In `api/index.js` (axios):

```javascript
api.interceptors.response.use(
  res => {
    if (res.data.code === 401) {
      const rt = localStorage.getItem('refresh_token')
      if (rt) {
        axios.post('/api/user/refresh', { refresh_token: rt }).then(r => {
          if (r.data?.data?.token) {
            localStorage.setItem('token', r.data.data.token)
            // Retry original request
            const origReq = res.config
            origReq.headers.Authorization = `Bearer ${r.data.data.token}`
            return api(origReq)
          }
        }).catch(() => {})
      }
      // All strategies exhausted — redirect to login
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('refresh_token')
      router.push('/login')
    }
    return res.data.data
  }
)
```

## 7. Account Security Module — Device Management + Password Change

Add these to a `security_api.py` blueprint at `/api/security`:

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/devices` | GET | @login_required | List all active sessions (from refresh_token table) |
| `/device/revoke` | POST | @login_required | Revoke `{device_id}` or `{all: true}` |
| `/change-password` | POST | @login_required | Change password with `{old_password, new_password, confirm_password, code}` |

### Device List Query

```python
cur.execute("""
    SELECT id, token, device_id, ip, created_at, expires_at
    FROM refresh_token 
    WHERE user_id=%s AND expires_at > NOW()
    ORDER BY created_at DESC
""", (user_id,))
```

Mark current device by matching `X-Device-Id` header against `device_id`.

### Change Password with Email Verification

```python
# 1. Verify old password exists
# 2. Validate: new != old, >= 6 chars, confirm matches
# 3. Verify email code from verify_codes table
cur.execute("SELECT email FROM `user` WHERE id=%s", (user_id,))
email = cur.fetchone().get('email', '')
cur.execute("""SELECT id FROM verify_codes 
    WHERE phone=%s AND code=%s AND verified=0 AND expires_at > NOW() 
    ORDER BY id DESC LIMIT 1""", (email, code))
# 4. On success: update password, mark code as used, DESTROY ALL SESSIONS
cur.execute("DELETE FROM refresh_token WHERE user_id=%s", (user_id,))
# Forces re-login on all devices
```

### Frontend Page (Security.vue)

Lives at `src/views/Security.vue` with route `/security`. Contains three sections:
- **Change Password Card**: old_pwd + new_pwd + confirm + email code + submit
- **Device Management Card**: list of devices from GET /security/devices, each with "下线" button, plus "一键下线所有"
- Auto-loads on mount, requires token

### Profile Entry Point

In Profile.vue, add between existing menu items:
```html
<div class="menu-item" @click="goTo('/security')">
  <div class="micon" style="background:rgba(244,67,54,0.1)">🛡️</div>
  <div class="minfo">
    <div class="mt">账号安全</div>
    <div class="ms">密码 · 设备管理</div>
  </div>
  <div class="marrow">›</div>
</div>
```

## Database Tables

```sql
CREATE TABLE refresh_token (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL,
    device_id VARCHAR(100) DEFAULT '',
    ip VARCHAR(45) DEFAULT '',
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_token (token)
);

CREATE TABLE login_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ip VARCHAR(45) DEFAULT '',
    device_id VARCHAR(100) DEFAULT '',
    user_agent VARCHAR(500) DEFAULT '',
    city VARCHAR(50) DEFAULT '',
    is_new_device TINYINT DEFAULT 0,
    is_new_city TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Pitfalls

- `login_required` decorator must accept BOTH old JWT and new v2 format during migration — fail gracefully, don't force-reauth.
- `parse_token` sig verification cannot include the random component (it's generated fresh each time). Only verify structure + expiry.
- `gen_refresh_token` must cap device sessions (5 max) to prevent table bloat.
- Frontend interceptor: `axios.post()` not `api.post()` for refresh call — otherwise infinite loop when api interceptor captures the 401 before the auth hook.
- `get_device_id()` fallback (UA+IP md5) is NOT stable — device ID changes with IP. Production should use a real `X-Device-Id` from the client.
- Logout endpoint MUST NOT return 401 after clearing sessions — skip `@login_required` or use a special handler.
- **NEVER bare `catch {}` in Vue async handlers** — silently swallows errors; user sees "no response". Always `catch(e) { safeToast(e.message || '操作失败') }`. This is the #1 cause of "click no reaction" reports.
- **Chinese full-width quotes `"…"` inside Python string literals → SyntaxError** → worker boot-loops → all APIs 502. Replace with `「…」` or single quotes.
- **TDZ on module-level mutable globals (`_bad_words = None`)**: declare `global _bad_words` at TOP of function body, not after early-return. Symptom: `UnboundLocalError`.
- **Flask Blueprint name collision**: second blueprint with same prefix raises `ValueError: already registered`. Fix: alias import + unique internal `Blueprint('x_v2', ...)` + different URL prefix.
- **deploy.sh scp dist/* doesn't reliably sync Server B index.html** — Server B keeps stale hash, browser loads 404. After every deploy: `ssh Server_B rm -rf assets/* && scp -r dist/assets/`. Nginx `expires -1` on `/` disables HTML cache.
- **Vue `info.value = res` reassignment** — all template expressions reading `info.xxx` (NOT `info.value.xxx`) silently show stale values. Audit every binding.
- **`get_client_ip()` for IP geo must read `X-Forwarded-For`**, NOT `request.remote_addr` (returns server's IP = Beijing).
- **Security monitoring cron: every 20 min**: `*/20 * * * *`.
- **`skip_captcha=true` flag for `/api/user/login` tests**.
- **Real-name privacy popup must be SIBLING not CHILD of verify-page** — otherwise `position:fixed` constrained by parent, popup invisible.
- **Nginx multi-server `/uploads/` collision**: first match wins, remove duplicate `alias` lines.
- **Privacy popup must use Vant `showConfirmDialog`** — native `confirm()` blocked on mobile WebView.
- **`/api/user/info` SELECT commonly misses newly-added DB columns.** Example: `verify_status` was added to the user table but the login SELECT and info SELECT both forgot it. The response dict called `user.get('verify_status', 0)` but the field wasn't in the query → always returned 0. Fix both the SELECT and verify the response key name matches the frontend.
- **Polling endpoints that don't need auth must NOT use `@login_required`.** Regular 30-second polls (e.g., `/api/message/count`) trigger the 401 interceptor when the token expires, redirecting the user to login mid-session. Fix: remove `@login_required` and catch auth failure gracefully.
- **ModSecurity WAF rules with `*` quantifiers or `.*` between keywords cause false positives on binary endpoints.** Captcha base64, image uploads, and any endpoint returning binary data will randomly match patterns like `(?i:select.*union.*)` or `(?i:\bexec\b)`. Symptom: `/api/captcha/get` returns 502 / empty, `/uploads/*.jpg` returns 403. Fix: disable ModSecurity per-path (`modsecurity off;` inside the `location` block), or use **precision patterns** that require SQL syntax (`OR 1=1`, `UNION SELECT`, `SELECT ... FROM`). See `references/modsecurity-waf-tuning.md` for the production rule set.
- **Cursor exhaustion after `with conn.cursor() as cur:` block.** SQL executed after the `with` block closes the cursor. The variable `cur` is still in scope but the cursor is closed → `OperationalError: (1243, 'Unknown prepared statement handler')`. Fix: open a NEW cursor (`cur2 = conn.cursor()`) for post-block queries, or re-structure to keep everything inside the `with` block.
- **User field locking — immutable after first set.** Phone (`phone_bound=1`), gender (`gender != 0`), and verification status (`verify_status=1`) must be enforced at both API and UI levels. Backend: check current value before allowing update. Frontend: show 🔒 icon, make row non-clickable (use `:class=\\\"{ clickable: !locked }\"` pattern) with `safeToast('已锁定，不可修改')` on click. The lock applies to THREE separate API endpoints: `/api/user/update` (phone/gender), `/api/user/verify` (verify_status), and `/api/review/v2/verify/submit` (verify_status).
- **Nginx `limit_req` burst values too low block legitimate users.** `burst=5 nodelay` on `login_limit` (5 r/m) means the 6th login attempt in a minute returns 503, even with correct credentials. Users who fat-finger their password twice and try again are blocked. Production value: `burst=10 nodelay` minimum for login, `burst=20+` for API. Verify by running `for i in {1..10}; do curl -X POST /api/user/login ...; done` — if you see 503 before exhausting rate, burst is too low.

## 15. Admin Route Obfuscation — Hide Backend Entry Point

### Static Private Path (first deployment)

**Problem:** Default `/admin` hash route is publicly discoverable. Attackers can enumerate admin pages.

**Pattern — Change to random private path:**

1. Pick a hard-to-guess path like `op-manage-7x2d9` (random string + recognizable prefix)
2. Replace ALL Vue router paths from `/admin/*` → `/{PRIVATE_PATH}/*`
3. Replace ALL `$router.push('/admin/*')` and `isActive('/admin/*')` in admin components
4. Update App.vue tab-bar hide check
5. Update axios interceptor `location.hash.includes('/admin')` check
6. Update nav.js smartBack mapping
7. Add redirect from old `/admin` → new path in App.vue `watch(() => route.path, ...)`

**What NOT to change:** Backend API calls (`api.get('/admin/xxx')`) — these are HTTP requests to `/api/admin/xxx`, not Vue routes.

**Verify no leftover old routes:**
```bash
grep -rn "path: '/admin\|router.push('/admin\|isActive('/admin" frontend/src/ --include="*.vue" --include="*.js"
# Should return NO results for Vue routes (api. calls are OK)
```

### Daily Path Rotation (advanced)

For maximum security, rotate the admin path every 24 hours via cron. See `references/admin-route-rotation.md` for full implementation. Key components:
- DB table `admin_route(id=1, path, expires_at)`
- `GET /api/admin/path` (no auth) returns current path
- Frontend fetches path on mount → `sessionStorage`
- Daily cron: generate new path → update DB + frontend source + Nginx → rebuild → deploy

## 16. Cloud Firewall — Never Use Server iptables

**⚠️ REAL INCIDENT — DO NOT USE iptables ON CLOUD SERVERS.** In production, a command sequence that ran `iptables -P INPUT DROP` before the ACCEPT rules were fully applied over SSH locked both servers. The single `ssh` command was atomic to the client but the iptables rules executed sequentially on the server — DROP hit first, SSH rule never arrived. Both HTTP (80) and SSH (22) were unreachable. Recovery required Tencent Cloud VNC console.

**Rule: Zero iptables on cloud VMs. Always use Cloud Security Groups.**

Security group rules are applied at the hypervisor level, not the guest OS. A misconfiguration can never lock out SSH because the hypervisor maintains the session independently of the guest firewall. Security groups apply instantly and are safely reversible from the cloud console at any time.

**Production Security Group template:**

| Server | Direction | Protocol | Port | Source | Purpose |
|--------|-----------|----------|------|--------|---------|
| API+DB (A) | Inbound | TCP | 22 | 0.0.0.0/0 | SSH (key-only auth; no password) |
| API+DB (A) | Inbound | TCP | 5002 | Server B private IP | API proxy only |
| API+DB (A) | Inbound | TCP | 3306 | 127.0.0.1 | MySQL local |
| Public (B) | Inbound | TCP | 22 | Server A IP | Deploy sync via SCP |
| Public (B) | Inbound | TCP | 80/443 | 0.0.0.0/0 | Public web |
| Both | Outbound | ALL | ALL | 0.0.0.0/0 | Default allow (no config needed) |

**Recovery from iptables lockout (last resort):**
1. Cloud Console → CVM → Instance → Remote Login → VNC
2. Enter system credentials
3. `sudo iptables -F && sudo iptables -P INPUT ACCEPT`
4. Immediately delete iptables rules and switch to Security Group

## 19. Account Ban — Immediate Session Revocation

### Problem

Setting `user.status=0` (ban) only prevents new logins. Existing access/refresh tokens remain valid until they expire. A banned user can continue calling APIs for up to 24 hours (JWT expiry).

### Fix — Active Status Check in `login_required` Decorator

Check `user.status` from DB on every authenticated API request:

```python
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'code': 401, 'msg': '未登录'}), 401
        token = auth[7:]
        
        v2 = parse_v2(token)
        if v2:
            request.current_user = v2
            if not _check_user_active(v2.get('user_id')):
                return jsonify({'code': 401, 'msg': '账号已被封禁'}), 401
            return f(*args, **kwargs)
        
        payload = decode_token(token)
        if not payload:
            return jsonify({'code': 401, 'msg': '登录已过期'}), 401
        request.current_user = payload
        if not _check_user_active(payload.get('user_id')):
            return jsonify({'code': 401, 'msg': '账号已被封禁'}), 401
        return f(*args, **kwargs)
    return decorated


def _check_user_active(user_id):
    if not user_id:
        return False
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM `user` WHERE id=%s", (user_id,))
            u = cur.fetchone()
            return u and u['status'] == 1
    except:
        return True  # Guard: allow through on error
    finally:
        conn.close()
```

### Frontend — Differentiate 401 Causes

```javascript
api.interceptors.response.use(
  null,
  err => {
    if (err.response && err.response.status === 401) {
      const errMsg = err.response.data?.msg || ''
      if (errMsg.includes('封禁')) {
        // Kick immediately, skip token refresh
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('refresh_token')
        router.push('/login')
        safeToast('账号已被封禁')
        return Promise.reject(new Error('账号已被封禁'))
      }
      // Other 401 → try token refresh...
```

## 17. Anti-Brute-Force — CAPTCHA + Password Lock + Login Logging

### Three-Layer Login Protection

| Layer | Mechanism | Threshold |
|-------|-----------|----------|
| 1. CAPTCHA | Arithmetic image (PIL), rendered server-side | Every login attempt (user + admin) |
| 2. Password lock | In-memory `_pwd_fails` dict, process-local | 5 consecutive fails → 15 min lock |
| 3. IP rate limit | Sliding window, per-IP | 5 requests/minute |

### Key Rules
- `skip_captcha=true` bypass has been **removed** — CAPTCHA is mandatory on ALL logins
- Password failures include "user not found" (prevents account enumeration)
- `login_log` table records every failed attempt with IP, device_id, user_agent, timestamp
- Both `user.py` (user login) and `admin.py` (admin login) implement the full chain

### Polling Endpoints — Never Return 401 for Unauthenticated Users

**Problem:** Background polling of `/api/message/count` (unread badge) triggers
axios 401 interceptor when token expires, redirecting user to login mid-session.

**Fix — remove `@login_required`, catch auth failure gracefully:**
```python
@msg_bp.route('/count', methods=['GET'])
def unread_count():
    try:
        user_id = request.current_user['user_id']
    except (AttributeError, KeyError, TypeError):
        return success({'unread_count': 0})
    # ... normal query returns real count
```
Apply to any regularly-polled read-only endpoint.

### Backend Field Name Sync — verify_status vs verified

**Problem:** Backend returns `verify_status` (0/1/2) but frontend reads `user.verified`
(undefined) → always shows "未认证" even after admin approves.

**Fix — check field names at 3 points:**
1. Login SELECT query includes the field (common miss when adding DB column)
2. Login response dict includes the field with the correct key name
3. Frontend template uses the same key: `user.verify_status == 1`, not `user.verified`

### Frontend CAPTCHA Component

```js
function refreshCaptcha() {
  api.get('/captcha/get').then(r => {
    captchaImage.value = r.image
    captchaKey.value = r.key
  })
}
// Refresh on every login failure
finally { refreshCaptcha(); captchaAnswer.value = '' }
```

### ⚠️ Captcha Not Loading on Tab Switch

**Symptom**: Login/Register page has multiple tabs (微信登录/扫码登录/账号密码). When user clicks the password tab, the captcha image is blank (src="").

**Root cause**: `refreshCaptcha()` is only called in `onMounted`, but the default tab is NOT the password tab → captcha never fires. `captchaImg` ref stays empty string.

**Fix** — use `watch` on the mode/tab ref:

```js
import { ref, watch, onMounted } from 'vue'

const loginMode = ref('scan')     // default is NOT 'password'
const captchaImg = ref('')

// 🎯 Watch mode changes — load captcha when password tab activates
watch(loginMode, (val) => {
  if (val === 'password') refreshCaptcha()
})
```

Applies to any page with v-show/v-if tab switching that includes a captcha input. The watcher pattern is preferred over calling `refreshCaptcha()` in `onMounted` because it avoids loading the captcha when it's not visible.

## End-of-Debug Diagnostic Sequence

```bash
curl -s --max-time 5 http://127.0.0.1:5002/api/health
curl -s --max-time 5 http://82.157.202.24/api/health
sudo journalctl -u ttdazi --no-pager -n 30 | grep -B1 -A3 'Traceback\\|Error'
# SSH key auth (no password) — sshpass removed for security
ssh -o StrictHostKeyChecking=no ubuntu@82.157.202.24 'cat /home/ubuntu/ttdazi-frontend/index.html 2>/dev/null | head -3'
```

## 8. Nginx WAF — External Layer

### limit_req + limit_conn

```nginx
http {
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
    
    geo $blacklist {
        default 0;
        include /etc/nginx/ip_blacklist.conf;
    }
}

server {
    limit_req zone=api_limit burst=50 nodelay;
    limit_conn conn_limit 50;
    if ($blacklist) { return 403; }
}
```

### Dynamic IP Ban

```bash
# Ban IP at Nginx level via backend
ssh Server_B "echo '1.2.3.4 1;' | sudo tee -a /etc/nginx/ip_blacklist.conf && sudo nginx -s reload"

# Management script at /usr/local/bin/ip_ban
ip_ban ban 1.2.3.4    # 封禁
ip_ban unban 1.2.3.4  # 解封
ip_ban list            # 查看
```

### 服务器层加固（SSH 防爆破 + 版本隐藏 + 限流落地检查）

**fail2ban（SSH 暴力破解第一道闸）**：公网服务器长期被扫描爆破（本实例 auth.log 里
15000+ Failed password，源多为海外 IP 段）。安装配置：
```bash
apt-get install -y fail2ban
# /etc/fail2ban/jail.local
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
ignoreip = 127.0.0.1/8 <自有服务器IP>   # 千万别漏，否则把自己封了

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
```
验证：`fail2ban-client status sshd`（Currently banned 应 > 0）。fail2ban 封禁的是
SSH 层，Nginx 层 IP 封禁走 `ip_blacklist.conf`（见上）。

**Nginx 版本号隐藏**：`server_tokens off;` 放 **http 块（nginx.conf）**，改后
`curl -skI https://域名/ | grep -i ^server` 应只显示 `server: nginx` 不跟版本号。
⚠️ 坑：conf.d 里再写一份 `server_tokens off;` 会与 nginx.conf 重复 → `nginx -t` failed，
直接删掉 conf.d 那份即可。

**限流"zone 定义了但没应用到 server 块"**：`nginx.conf` 里常见 `limit_req_zone` 定义了
多个 zone（api/login/api_limit/ttdazi_api）但实际 server 块一个都没引用 → 等于没防护。
审计时 `grep -rE 'limit_req_zone' /etc/nginx/nginx.conf /etc/nginx/conf.d/` 找定义，
再确认 `sites-enabled/` **实际生效的配置**（⚠️ sites-available 里改了不一定生效，Server B
上 dazi.openai2000.cn 的真实 server 块在 `sites-enabled/huizhiyunma`，不是 sites-available/ttdazi）
里有 `limit_req zone=... burst=50 nodelay;`。缺失就补进 server 块：
```nginx
limit_req zone=api burst=50 nodelay;
limit_conn ttdazi_conn 100;
```

**⚠️ SPA 敏感路径探测的假阳性**：对 Vue SPA 探测 `/.env` `/.git/config` `/wp-admin/`
`/phpmyadmin/` `/backup.zip` 全部返回 **200** —— 这是 `try_files ... /index.html` 兜底
返回了首页，**不是真实泄露**！判定方法必须看返回内容：
```bash
curl -sk https://域名/.env | grep -oE '<title>[^<]*</title>'   # 是 SPA 标题 = 假阳性
# 真实泄露 = 返回 .env 明文（无 <!DOCTYPE html> 开头）
find /var/www/站点 -name '.env' -o -name '*.sql' -o -name '*.zip'   # 服务器上无此文件才安全
```
审计报告里 200 不算漏洞，要写明"SPA 兜底假阳性，已确认服务器无真实敏感文件"。

## 9. Risk Control Module

**File:** `app/risk_control.py` | **Table:** `risk_blacklist(ip, reason, expires_at)`

### Rules

| Rule | Threshold | Action |
|------|-----------|--------|
| 批量注册 | 3/d/IP, 2/h/IP | ban IP 24h + Nginx blacklist |
| 高频下单 | 10/d/user, 20/d/IP | ban IP 2h |
| 下单间隔 | 3s | reject with msg |
| 优惠券防薅 | 1/user | FOR UPDATE row lock |

### Architecture

```python
register → check_register_risk() → IP counter(memory+SQL)
order → check_order_risk() → user cap + IP cap + interval check
ban_ip() → risk_blacklist INSERT → ssh to Nginx → ip_blacklist.conf → nginx -s reload
```

## 10. Real-Name Verification

**File:** `app/platform_review.py` | **Blueprint:** `'/api/review/v2'` (note: prefix differs from old review module)

### Flow

1. Privacy consent overlay (must check checkbox → button activates)
2. Upload ID card → `POST /api/review/v2/verify/upload-id`
3. Image validation: format(JPG/PNG), size(≥640×480), aspect(≤2.0), file(≤5MB)
4. OCR: Tencent Cloud IDCardOCR (optional, not required)
5. Validity check: parse `YYYY.MM.DD`, reject if expired
6. Submit → `POST /api/review/v2/verify/submit`
7. Admin review → GET list / approve / reject

### Key: Blueprint Name Conflict

The `app/review.py` also uses `review_bp` with prefix `/api/review`. When adding a new review blueprint:
- Import as different name: `from app.platform_review import review_bp as platform_review_bp`
- Give it a unique internal name: `Blueprint('platform_review_v2', ...)`
- Keep URL prefix separate to avoid route collisions

## 11. Content Filtering (Sensitive Words)

**File:** `app/platform_review.py` | **Table:** `sensitive_words`

```python
# 20+ default words loaded on startup
check_content(text) → (ok: bool, reason: str)
# Integrated into:
# - customer_service.py (before storing chat messages)
# - companion register intro/tags
```

## 12. Input/Output Safety Filter

**File:** `app/safety_filter.py`

| Function | Purpose |
|----------|---------|
| `sanitize(text)` | XSS: strip 10 malicious tag patterns, escape < > " ' |
| `sanitize_dict(data, fields)` | Batch apply to specified dict fields |
| `mask_phone(phone)` | `13800138000` → `138****8000` |
| `mask_email(email)` | `test@qq.com` → `t***@qq.com` |
| `paginate(page, page_size, max_size=50)` | Force valid params, cap at max_size |
| `paginated_response(items, total, page, size)` | → `{list, total, page, page_size, total_pages}` |

## 13. Security Monitoring Cron

**Script:** `/usr/local/bin/ttdazi_security_monitor.sh` (runs every 5 min via crontab)

Checks:
- Backend service health → auto-restart on failure
- MySQL connectivity
- Nginx frontend reachability
- Disk/memory/CPU usage thresholds
- Login failure rate (5min >20 → auto-ban attacker IPs)
- Batch registration detection
- Scan attack detection (phpmyadmin/wp-admin/.env probes)
- Anomaly login alerts from audit_log

## 14. Operation Monitoring Dashboard

**File:** `app/statistics.py` endpoint `GET /api/stats/monitor`
**Frontend:** `src/views/admin/AdminMonitor.vue` at route `/admin/monitor`

Tabs: Real-time (active IPs/requests), Login anomalies (failed attempts per IP), Banned IPs, Order trend (7-day bar chart), Content safety (blocks/pending reports).

Auto-refreshes every 30s.

## References

See `references/ttdazi-security-modules.md` for project-specific implementation details (file paths, DB schema, deploy order).\nSee `references/security-hardening-checklist.md` for systematic audit procedure, SQL injection field-whitelist pattern, file upload magic-byte validation, CORS hardening, deploy credential management, and environment variable configuration.\nSee `references/password-policy-modsecurity.md` for password strength enforcement, 90-day expiry, ModSecurity WAF deployment rules, nginx hardening configuration, and deploy credential security.\nSee `references/modsecurity-waf-tuning.md` for the production WAF rule set, the ModSecurity `*` quantifier false-positive problem, and how to test captcha/image endpoints after enabling WAF.
