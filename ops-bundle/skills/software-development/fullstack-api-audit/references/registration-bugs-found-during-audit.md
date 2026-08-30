# Registration & Auth Bugs Found During Audit

## 1. Password Validation Too Strict → 500 Error

**Bug**: `utils.py` required passwords ≥16 chars with uppercase + lowercase + digit + special char. Frontend validated ≥6 chars. The mismatch caused `hash_password()` to raise `ValueError` which became a 500 error with no useful message.

**Fix**: 
```python
PWD_MIN_LEN = 6  # was 16
# Remove uppercase/lowercase/special requirements
# Keep only: len >= 6 and contains digit
```

**Scan for**: `validate_password_strength` — check `PWD_MIN_LEN` and the specific requirements.

## 2. Email Address Missing `@` Separator

**Bug**: Frontend composed email as `emailName.value + emailDomain.value` where `emailDomain` was `'qq.com'` (no `@`). Result: `usernameqq.com` instead of `username@qq.com`. The backend regex expected `@` in the address.

**Fix**:
```js
// Before: broken
const email = computed(() => emailName.value + emailDomain.value)
// After: fixed  
const email = computed(() => emailName.value + '@' + emailDomain.value)
```

**Scan for**: Look for `emailName.value + emailDomain.value` in Vue files — must include `'@'` between them.

## 3. SMTP 550 Error for Non-Existent Recipients

**Bug**: QQ Mail SMTP returns `(550, b'The recipient may contain a non-existent account')` when sending to email addresses that don't exist on QQ's domain. The send-email-code endpoint catches this generically as "验证码发送失败".

**Fix**: The SMTP error is caught — no code fix needed, but inform users that the email must be a real, active mailbox.

**Context**: QQ Mail SMTP validates recipient existence before accepting the message. This is different from Gmail/SendGrid which accept and deliver-or-bounce.

## 4. Gunicorn Bytecode Cache → Old Code Persists

**Bug**: After editing `.py` files and `systemctl restart ttdazi`, the old code still ran. Gunicorn loaded cached `.pyc` files from `__pycache__/`.

**Fix**:
```bash
# Must clear bytecode cache before restart
find /opt/ttdazi/backend -name "__pycache__" -type d -exec rm -rf {} +
sudo systemctl restart ttdazi
```

## 5. `register_by_code` Undefined Variable

**Bug**: `user.py` line 568 used `(email,)` as the parameter in `register_by_code()` function, but the function uses variable `phone`, not `email`. The `email` variable is undefined → NameError → 500 error.

```python
# Before (broken - email is undefined in register_by_code)
cur.execute("UPDATE verify_codes SET verified=1 WHERE email=%s", (email,))

# After (correct - phone is the variable in this function)
cur.execute("UPDATE verify_codes SET verified=1 WHERE phone=%s", (phone,))
```

**Scan for**: Check each function's variable names match the SQL parameters. `register_by_code` uses `phone`, `register_by_email` uses `email`.

## 6. `companion/complete-order` Double order_count Update

**Bug**: `playmate_api.py` updated `user.order_count` twice in the same function:
1. First incorrectly for the companion's user_id (who completes the order)
2. Then correctly for the ordering customer's user_id

**Fix**: Remove the first incorrect update, keep only the second one that queries the order's actual customer.

## 7. Pre-Flight Checklist for Registration Flow

Before marking registration as working, verify:

- [ ] `hash_password()` accepts ≥6 char passwords
- [ ] `emailName + '@' + emailDomain` correct composition  
- [ ] `register_by_code` uses variable `phone`, not `email`
- [ ] `register_by_email` uses variable `email`, not `phone`
- [ ] SMTP credentials are valid (test with `smtplib.SMTP_SSL`)
- [ ] Verify code cooldown (60s) doesn't block testing
- [ ] Clear `__pycache__` before restarting gunicorn
- [ ] Test with `curl` all 4 steps: send-code → verify → register → login
