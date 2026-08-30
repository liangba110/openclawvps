# Gunicorn Multi-Worker Captcha Fix

## Problem

Captcha answers stored in a Python in-memory dict (`_store = {}`) are NOT shared across gunicorn workers. With 2+ workers:

1. User requests captcha → Worker A stores answer in `_store_A`
2. User submits login → Request goes to Worker B → checks `_store_B` → answer not found → "验证码已过期"

This applies to ANY in-memory state: verification codes, rate limit counters, OTP stores.

## Fix: Store captcha in MySQL

Instead of `_store = {}`, use a `captcha_log` table with `key`, `answer`, `expires_at`, `used` columns.

### Schema

```sql
CREATE TABLE IF NOT EXISTS captcha_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(32) NOT NULL,
    answer VARCHAR(10) NOT NULL,
    expires_at BIGINT NOT NULL,
    used TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_key (`key`),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Key differences from in-memory version

| Aspect | In-memory dict | Database |
|--------|---------------|----------|
| Storage | `_store[key] = (answer, expire_ts)` | `captcha_log` row |
| Shared across workers? | ❌ No | ✅ Yes |
| Cleanup | `_clean()` iterates dict keys | SQL `DELETE WHERE expires_at < NOW() OR used=1` |
| One-time use | `_store.pop(key)` | `UPDATE SET used=1` |
| Expiry | configurable (e.g. 300s) | store as Unix timestamp, check in WHERE |

### Implementation pattern

```python
def get_captcha():
    # Generate random arithmetic problem
    answer = compute_answer()
    key = hashlib.md5(str(random.random()).encode()).hexdigest()[:12]
    expires = int(time.time()) + 600  # 10 minutes

    # Store in DB
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO captcha_log (`key`, answer, expires_at) VALUES (%s, %s, %s)",
            (key, str(answer), expires)
        )
        conn.commit()

    return {'key': key, 'image': base64_image}


def verify_captcha(key, answer):
    conn = get_connection()
    with conn.cursor() as cur:
        now = int(time.time())
        cur.execute(
            "SELECT id, answer FROM captcha_log WHERE `key`=%s AND used=0 AND expires_at > %s LIMIT 1",
            (key, now)
        )
        row = cur.fetchone()
        if not row:
            return False, '验证码已过期，请刷新'
        # Mark used (one-time)
        cur.execute("UPDATE captcha_log SET used=1 WHERE id=%s", (row['id'],))
        conn.commit()
        return row['answer'] == str(answer), ''
```

### Which files need this fix

- `app/captcha.py` — captcha `_store` → DB
- `app/verify_code.py` (if exists) — verification code `_codes` → DB
- Any module using a module-level dict for cross-request state

### Prevention (new code)

Before writing `_some_dict = {}` or `_cache = {}` at module level, ask: "Will this be called across different gunicorn workers?" If yes, use the database.
