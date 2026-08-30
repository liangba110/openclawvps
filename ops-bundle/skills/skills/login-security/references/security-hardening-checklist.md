# Security Hardening Checklist

## Systematic Audit Procedure

When asked to audit or harden security, follow this checklist:

### 1. Admin Page Render Test
```bash
for p in /admin/ /admin/users /admin/playmates /admin/orders /admin/content /admin/reviews /admin/withdrawals /admin/finance /admin/verify /admin/messages /admin/monitor /admin/config /admin/service /admin/faq /admin/code /admin/coupons /admin/agreements; do
  curl -s -o /dev/null -w "%{http_code} $p\n" http://$HOST$p
done
```

### 2. Frontend-Backend Mapping Audit
Every frontend feature must have a corresponding admin management, modification, or review page. See `admin-mirror-rule` skill for the master mapping table.

### 3. Security Test Points

| Check | Tool/Command | Pass/Fail |
|-------|-------------|-----------|
| Security headers | `curl -sI http://host/ \| grep -i 'x-frame\|x-content\|x-xss\|referrer\|permissions'` | Must return 6 headers |
| Sensitive file blocking | `curl -s -o /dev/null -w "%{http_code}" http://host/.env` → 403 | Must be 403/404 |
| Upload dir protection | `curl -s -o /dev/null -w "%{http_code}" http://host/uploads/id_cards/x.jpg` → 404 | Must be 404 |
| CORS wildcard | `curl -sI -H "Origin: http://evil.com" http://host/api/health \| grep Access-Control` | Must NOT return ACAO: * |
| JWT expiry | Check config: `JWT_EXPIRE_HOURS` should be ≤ 24 | Must be ≤ 24 |
| Debug mode | `grep "debug=" config.py main.py` → should be False | Must be off |

## SQL Injection Prevention — Field Whitelist Pattern

For dynamic UPDATE SET clauses in Flask admin:

```python
ALLOWED = {'nickname', 'phone', 'email', 'gender', 'city', 'status', 'phone_bound', 'avatar'}
safe_updates = {k: v for k, v in updates.items() if k in ALLOWED}
if not safe_updates:
    return fail('没有允许更新的字段')
set_clause = ', '.join([f"`{k}`=%s" for k in safe_updates])
values = list(safe_updates.values()) + [user_id]
cur.execute(f"UPDATE user SET {set_clause} WHERE id=%s", values)
```

Apply this pattern for EVERY dynamic UPDATE in admin.py (banner, game, user endpoints).

## File Upload — Magic Byte Validation

Always double-check file type by reading the file header, not just the extension:

```python
header = file.read(12)
file.seek(0)
if ext == 'jpg' and header[:2] != b'\xff\xd8':
    return fail('文件格式与扩展名不匹配')
if ext == 'png' and header[:8] != b'\x89PNG\r\n\x1a\n':
    return fail('文件格式与扩展名不匹配')
if ext == 'webp' and (header[:4] != b'RIFF' or header[8:12] != b'WEBP'):
    return fail('文件格式与扩展名不匹配')
```

## CORS Hardening

```python
# DO NOT use origins="*"
CORS(app, resources={r"/api/*": {
    "origins": ["http://yourdomain.com", "http://localhost:5002"]
}}, supports_credentials=False)
```

## JWT Expiry

```python
JWT_EXPIRE_HOURS = int(os.environ.get('JWT_EXPIRE_HOURS', 24))  # ≤ 24h
```

## Deploy Credential Management

```bash
# NEVER store passwords in deploy.sh
# Use SSH key authentication instead:
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
ssh-copy-id -o StrictHostKeyChecking=no user@remote-server
# Then deploy.sh uses plain ssh/scp (no password)
```

## Configuration via Environment Variables

```python
# In config.py: hardcoded defaults with env var override
JWT_SECRET = os.environ.get('JWT_SECRET', 'fallback-dev-only')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'fallback-dev-only')
SERVER_PORT = int(os.environ.get('SERVER_PORT', 5002))
```
