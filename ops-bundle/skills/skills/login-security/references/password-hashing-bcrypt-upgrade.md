# Password Hashing Upgrade: SHA256 → bcrypt

## Why

SHA256 is a **fast hash** — an attacker can compute billions of SHA256 attempts per second with consumer hardware. bcrypt is a **slow hash** designed for passwords: it includes a salt (per-password random value) and a configurable work factor that makes brute-force attacks prohibitively expensive.

## Upgrade Pattern (Backward-Compatible)

Existing users have SHA256 hashes stored in the database. New users get bcrypt hashes. The `check_password` function must try bcrypt first, then fall back to SHA256 for old accounts. Over time, users who log in get their hash auto-upgraded to bcrypt.

### Implementation

```python
def make_password(password):
    """New registrations: bcrypt with salt"""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    """Check password — try bcrypt first, then legacy SHA256"""
    import bcrypt, hashlib
    try:
        # bcrypt check (new hashes)
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        # Legacy SHA256 check (old hashes)
        return hashlib.sha256(password.encode()).hexdigest() == hashed
```

### Auto-Upgrade on Login

When an old SHA256 user logs in successfully, upgrade their hash to bcrypt:

```python
def login():
    ...
    if check_password(password, user['password']):
        # Auto-upgrade legacy SHA256 hash to bcrypt
        if user['password'] and not user['password'].startswith('$2b$'):
            new_hash = make_password(password)
            cur.execute("UPDATE users SET password=%s WHERE id=%s", (new_hash, user['id']))
            conn.commit()
        ...
```

## Installation

```bash
pip3 install bcrypt
```

## Database Impact

- Column: `users.password VARCHAR(255)` (bcrypt hashes are up to 60 chars, SHA256 is 64 chars — either fits)
- No migration needed: new hashes coexist with old ones
- Test: verify login works for both old and new accounts
