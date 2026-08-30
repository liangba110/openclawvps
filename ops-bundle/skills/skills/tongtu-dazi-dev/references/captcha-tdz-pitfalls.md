# CAPTCHA + Rate Limiting Pitfalls

## CRITICAL: `const` TDZ Bug — Captcha Image Never Shows, No Console Error

**Symptom:** `captchaImage` data URI is never set. Page loads with no 4xx/5xx, catch block fires silently with `{}`. Affected pages: Login (both modes), Register, EmailRegister, FollowRegister.

**Cause:** `<script setup>` `const` declarations are NOT hoisted. When `refreshCaptcha()` runs, `captchaImage` is in TDZ (Temporal Dead Zone):

```js
// ❌ FAILS — `const captchaImage` not yet declared when refreshCaptcha() runs
refreshCaptcha()
const captchaImage = ref('')

// ✅ CORRECT — declare ALL captcha refs before function and call
const captchaImage = ref('')
const captchaKey = ref('')
const captchaAnswer = ref('')
async function refreshCaptcha() { ... }
refreshCaptcha()
```

**Fix:** Search for `refreshCaptcha()` calls and ensure ALL three `const captcha*` refs appear ABOVE both the function definition AND the function call.

## Multi-Step Form Captcha — Template Coverage

FollowRegister is a 3-step wizard (`v-if="step===1/2/3"`). Adding captcha to "注册按钮" only hit step 1. Step 3 (actual registration) had no captcha. **Always check ALL template branches when adding UI to multi-step forms.**

## Pillow Install

```bash
sudo apt install python3-pil -y
# NOT pip install Pillow — PEP 668 blocks it
```

## Rate Limiting — Idempotent Decorator Imports

The `@idempotent` decorator in `payment_secure.py` uses `request.current_user` — must be placed AFTER `@login_required` (which sets `current_user`):

```python
@order_bp.route('/create', methods=['POST'])
@login_required     # ← must come first
@idempotent('order') # ← then this
def create():
```

## Email Login — `email` Column Required

The user table needs an `email VARCHAR(100)` column. Login SQL must check it:

```sql
WHERE phone=%s OR username=%s OR email=%s
```

Also: `register-by-email` must handle existing users (verify → login directly, not "该邮箱已注册").
