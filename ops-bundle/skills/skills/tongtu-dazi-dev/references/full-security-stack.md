# Full Security Stack — Integration Reference

## Layer 1: Network WAF (iptables + Nginx)

**Server B iptables:**
```bash
sudo iptables -A INPUT -p tcp --dport 80 -m connlimit --connlimit-above 100 -j REJECT
sudo iptables -A INPUT -p tcp --dport 80 -m recent --name badip --set
sudo iptables -A INPUT -p tcp --dport 80 -m recent --name badip --update --seconds 60 --hitcount 60 -j DROP
```

**Nginx rate limiting (main nginx.conf):**
```nginx
limit_req_zone $binary_remote_addr zone=waf:10m rate=30r/s;
limit_conn_zone $binary_remote_addr zone=addr:10m;
```

**Nginx server block rules:**
```nginx
server {
    listen 80;
    limit_req zone=waf burst=50 nodelay;
    limit_conn addr 50;
    if ($http_user_agent ~* (curl|wget|python-requests|scrapy|sqlmap)) { return 444; }
}
```

## Layer 2: Rate Limiting (ratelimit.py)

**Backend:** `backend/app/ratelimit.py` — in-memory sliding window + threading.Lock.

```python
# Decorator for login
@login_ip_limit
# Check before password validation
allowed, msg = check_pwd_lock(phone)
record_pwd_fail(phone) / reset_pwd_fails(phone)  # on failure/success
# SMS code rate limit
allowed, msg = check_code_limit(phone, ip)
```

**Limits:** 5 login/min per IP, 3 wrong password → 10min lock, 60s code interval, 20/day per IP.

## Layer 3: CAPTCHA (captcha.py)

**Backend:** `backend/app/captcha.py` — Pillow arithmetic image.
- `/api/captcha/get` → `{key, image: "data:image/png;base64,..."}`
- `require_captcha(key, answer)` — validates + expires (5min TTL)

**Frontend (ALL registration/login pages):**
```html
<div class="input-group captcha-row">
  <input v-model="captchaAnswer" placeholder="验证码" maxlength="5" />
  <img :src="captchaImage" class="captcha-img" @click="refreshCaptcha" />
</div>
```

**CRITICAL TDZ Bug (silent failure fix):**
```js
// ✅ Declare EVERYTHING before function call
const captchaImage = ref('')
const captchaKey = ref('')
const captchaAnswer = ref('')
async function refreshCaptcha() { ... }
refreshCaptcha()  // safe — refs declared above
```

**Pillow install:** `sudo apt install python3-pil`

## Layer 4: Token Auth (token_auth.py)

**Backend:** `backend/app/token_auth.py`

```python
# On login:
device_id = get_device_id()
token = gen_token(user_id, device_id)           # 30 min
refresh_tok = gen_refresh_token(user_id, device_id, ip)  # 7 days
sus, warn_msg = check_anomaly(user_id, device_id, ip)

# Response includes:
{'token': token, 'refresh_token': refresh_tok, 'anomaly_warn': warn_msg if sus else ''}

# On logout:
revoke_all_sessions(user_id)  # DELETE FROM refresh_token WHERE user_id=?
```

**Updated login_required in utils.py:**
```python
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = auth[7:]
        from app.token_auth import parse_token as parse_v2
        v2 = parse_v2(token)
        if v2:
            request.current_user = v2
            return f(*args, **kwargs)
        payload = decode_token(token)
        ...
```

**Frontend (api/index.js):**
```js
// 401 auto-refresh logic
if (res.data.code === 401) {
  const rt = localStorage.getItem('refresh_token')
  if (rt) {
    axios.post('/api/user/refresh', { refresh_token: rt }).then(r => {
      if (r.data?.code === 0 && r.data.data?.token) {
        localStorage.setItem('token', r.data.data.token)
        const origReq = res.config
        origReq.headers.Authorization = `Bearer ${r.data.data.token}`
        return api(origReq)
      }
    }).catch(() => {})
  }
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  localStorage.removeItem('refresh_token')
  ...
}
```

## Layer 5: Audit Log (audit_log.py)

**Backend:** `backend/app/audit_log.py`

Tables: `audit_log`, `refresh_token`, `login_log`.

```python
log(user_id, action, target_type='', target_id=0, detail=None)
# Example: log(user['id'], 'login_success', detail={'username': username})
```

Called on: login success/fail, order create, password change, logout, device revoke.

## Layer 6: Input Sanitization (safety_filter.py)

**Backend:** `backend/app/safety_filter.py`

```python
sanitize(text, max_len=500)       # XSS strip + char replacement
sanitize_dict(data, fields=...)   # Batch on form submissions
mask_phone(phone)                 # 138****8000
mask_email(email)                 # t***@domain.com
paginate(page, page_size, 50)     # Force valid pagination
paginated_response(items, total, page, page_size)  # {list, total, page, ...}
```

## Layer 7: Funds Security (payment_secure.py)

**Backend:** `backend/app/payment_secure.py`

```python
db_price, err = get_db_price(companion_id, service_type)
amount = db_price['price']

@idempotent('order')
def create_order(): ...

@require_sign
def pay(): ...
```

**Frontend:** Generate `idempotent_key: 'order_...'`.

## Layer 8: Account Security (security_api.py)

**Backend:** `backend/app/security_api.py` — `/api/security/*`

Three endpoints:
- `GET /devices` — list active login sessions
- `POST /device/revoke` — `{device_id}` or `{all: true}`
- `POST /change-password` — `{old_password, new_password, confirm_password, code}` — email OTP gated

**Frontend:** `frontend/src/views/Security.vue` at route `/security`

## Layer 9: Global Error Handler (main.py)

```python
@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    return fail('服务器内部错误，请稍后重试')

@app.errorhandler(404)
def not_found(e):
    return jsonify({'code': 404, 'msg': '接口不存在', 'data': None}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'code': 405, 'msg': '请求方法不允许', 'data': None}), 405
```

## Layer 10: Risk Control (risk_control.py)

**Backend:** `backend/app/risk_control.py`

Three detection axes, using in-memory counters + DB `risk_blacklist` table:

| Rule | Threshold | Action |
|------|-----------|--------|
| Batch registration | ≥3/day or ≥2/hour per IP | 24h auto-ban |
| High-freq orders | ≥10/user/day or ≥20/IP/day | 2h auto-ban |
| Order interval | <3s between same user | Reject (no ban) |
| Coupon abuse | FOR UPDATE row lock | Prevents concurrent over-claim |

```python
# Before register:
ok, msg = check_register_risk()
if not ok: return fail(msg)

# Before order create:
ok, msg = check_order_risk(user_id)
if not ok: return fail(msg)

# Manual ban:
ban_ip(ip, reason='reason', minutes=1440)
```

**Tables:** `risk_blacklist(ip VARCHAR(45) UNIQUE, reason, expires_at)`

## Layer 11: Platform Review (platform_review.py)

**Backend:** `backend/app/platform_review.py`

### Real-Name Verification
- Table: `verify_application(user_id, real_name, id_card, ...)`
- Submit: `POST /api/review/verify/submit`
- Admin: `POST .../verify/approve`, `POST .../verify/reject`
- Post-approval: `UPDATE user SET verify_status=1` → companion badges show ✅

### Content Filter (Sensitive Words)
- Table: `sensitive_words(word VARCHAR UNIQUE)`
- 20+ default words (色情/赌博/诈骗/微信/QQ/二维码/外挂/代练...)
- Phone block: `re.findall(r'\b1[3-9]\d{9}\b', text)`
- `check_content(text)` → `(ok, reason)` called on every chat message

### Report/Complaint System
- Table: `reports(reporter_id, target_type, target_id, reason, status)`
- Submit: `POST /api/review/report`
- Admin: `GET /api/review/reports`, `POST /api/review/report/handle`

## File Added Notes

New files added in this session:
- `backend/app/token_auth.py` — v2 token, refresh token, device binding, anomaly detection
- `backend/app/captcha.py` — Math CAPTCHA with Pillow
- `backend/app/ratelimit.py` — IP sliding window + password lockout + code interval
- `backend/app/payment_secure.py` — DB price trust + idempotent lock + HMAC sign
- `backend/app/audit_log.py` — Audit log tables + logging functions
- `backend/app/safety_filter.py` — XSS sanitize + phone mask + paginate
- `backend/app/security_api.py` — Device management + password change with OTP
- `backend/app/risk_control.py` — IP ban + batch reg detection + high-freq order + coupon anti-abuse
- `backend/app/platform_review.py` — Real-name verif + content filter + report system
- `frontend/src/views/Security.vue` — Account security page