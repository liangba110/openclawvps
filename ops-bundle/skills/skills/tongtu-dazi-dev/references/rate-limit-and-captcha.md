# Rate Limiting + CAPTCHA — Common Pitfalls

## Rate Limiting Architecture

**Module:** `backend/app/ratelimit.py` — in-memory sliding window + lock, no DB.

```python
LIMITS = {
    'login_ip_max': 5,        # 1 minute
    'login_ip_window': 60,
    'pwd_max_fails': 3,
    'pwd_lock_minutes': 10,
    'code_interval': 60,      # captcha interval
    'code_ip_daily': 20,     # captcha daily
}
```

**Three decorators:**
- `@login_ip_limit` — IP sliding window. 6th rapid request → 429 "请求过于频繁，请52秒后再试"
- `check_pwd_lock(phone)` / `record_pwd_fail(phone)` / `reset_pwd_fails(phone)` — counter → lock 10min
- `check_code_limit(phone, ip)` — 60s interval + 20/day/IP

**Apply to login endpoint:**
```python
@user_bp.route('/login', methods=['POST'])
@login_ip_limit
def login():
    ...
    allowed, msg = check_pwd_lock(username)
    if not allowed:
        return fail(msg, code=429)
    ...
    if not check_password(password, user['password']):
        record_pwd_fail(username)
        return fail('密码错误')
    reset_pwd_fails(username)  # success!
```

⚠️ **In-memory state limitation:** Each gunicorn worker has its own state. Multiple workers = inconsistent limits. For real production use Redis SET NX EX.

## CAPTCHA (Graphical) — All Entry Points

**Backend (`app/captcha.py`):** Generates arithmetic image captcha with Pillow:
- `/api/captcha/get` → `{key, image: "data:image/png;base64,..."}`
- 5-minute TTL, simple addition/subtraction/multiplication
- Memory store `_store[key] = (answer, expire_time)`

**Pillow install:** `sudo apt install python3-pil` (PEP 668 blocks `pip install Pillow`).

**Apply to login AND register:**
```python
from app.captcha import require_captcha

ok, msg = require_captcha(data.get('captcha_key'), data.get('captcha_answer'))
if not ok:
    return fail(msg)
```

**ALL entry points need captcha:**
- Login (both password and code modes)
- Register (phone)
- EmailRegister (email)
- FollowRegister (multi-step — captcha in step 2, not step 1 or 3)

## CRITICAL: Captcha `const` TDZ Bug — Silent Failure

**Symptom:** Captcha image never appears, no console error, login/register still works (or fails without captcha error).

**Root cause:** `<script setup>` `const` declarations are NOT hoisted. When `refreshCaptcha()` runs BEFORE `const captchaImage = ref('')`, the variable is in Temporal Dead Zone → `captchaImage.value = r.image` throws → caught by empty `catch{}` → silent failure.

```js
// ❌ FAILS — captchaImage is TDZ when refreshCaptcha() runs
refreshCaptcha()                          // called here
const captchaImage = ref('')              // declared here — TOO LATE!
async function refreshCaptcha() { ... }
```

**Fix:** Declare ALL captcha refs BEFORE function definition and call:
```js
// ✅ Declare all 3 refs first, then function, then call
const captchaImage = ref('')
const captchaKey = ref('')
const captchaAnswer = ref('')
async function refreshCaptcha() {
  try {
    const r = await api.get('/captcha/get')
    captchaImage.value = r.image
    captchaKey.value = r.key
    captchaAnswer.value = ''
  } catch {}
}
refreshCaptcha()  // safe now
```

**Debug command:**
```bash
grep -n 'const captcha\|refreshCaptcha()' Login.vue
# If refreshCaptcha() appears BEFORE the const declarations → TDZ bug
```

## Multi-Step Form Captcha — Template Branch Coverage

FollowRegister is a 3-step wizard (`v-if="step === 1/2/3"`). When adding captcha, the template match only found step 1's "注册按钮", missing step 3's actual registration form. Result: captcha JS was loaded but never rendered.

**Always check ALL template branches in multi-step forms.** When the captcha appears in code but not visually:
1. grep the template for `v-if=` branches
2. Verify the captcha `<input>` and `<img>` are inside the correct branch
3. Add captcha to EVERY branch that submits data

## Login Rate Limit Test

```bash
# Rapid-fire 6 login attempts (limit is 5/min)
for i in $(seq 1 6); do
  echo -n "$i: "
  curl -s -X POST http://127.0.0.1:5002/api/user/login \
    -H 'Content-Type: application/json' \
    -d '{"phone":"test","password":"wrong"}' \
    | python3.12 -c "import json,sys; d=json.load(sys.stdin); print(f'code={d[\"code\"]} {d.get(\"msg\",\"\")[:30]}')"
done
# Expected output: 1-5 should fail with "密码错误" / "用户不存在", 6th should be 429
```

```bash
# Password lock test (3 wrong → 10min lock)
for i in 1 2 3 4; do
  curl -X POST http://127.0.0.1:5002/api/user/login \
    -H 'Content-Type: application/json' \
    -d '{"phone":"13800138000","password":"WRONG"}' | head -1
done
# 4th response: "密码错误次数过多，请599秒后再试"
```