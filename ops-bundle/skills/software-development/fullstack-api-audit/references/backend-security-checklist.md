# Backend Security Checklist

Findings from the 2026-07-06 comprehensive audit of the 同途搭子 project (27 backend files, 152 routes).

## Auth Decorator Issues (🔴 Critical)

### Common Pattern: Route has @login_required but should have @admin_required

Routes that ANY logged-in user could access but should be admin-only:

| File | Route | Risk |
|------|-------|------|
| admin.py | `/withdrawals` (GET) | Any user can see pending withdrawals |
| admin.py | `/withdrawals/<id>/audit` (POST) | Any user can approve/reject withdrawals |
| coupon.py | `/admin/list` (GET) | Any user can list all coupons |
| coupon.py | `/admin/create` (POST) | Any user can create coupons |
| coupon.py | `/admin/usage/<id>` (GET) | Any user can see coupon usage |
| agreement.py | `/admin/list` (GET) | Any user can list agreements |
| agreement.py | `/admin/save` (POST) | Any user can modify platform agreements |
| platform_review.py | 5 routes | Verification/report management - NO auth at all |

### Fix Pattern

```python
# Before
@bp.route('/admin/list', methods=['GET'])
@login_required
def admin_list():

# After
@bp.route('/admin/list', methods=['GET'])
@login_required
@admin_required
def admin_list():
```

### Import Pattern

`admin_required` lives in `app.admin`, not `app.utils`:

```python
from app.admin import admin_required
```

## Bare Except (🔴 Critical - Swallows All Errors)

Files with bare `except:` (no exception type) — these should be `except Exception:`:

| File | Lines Affected |
|------|---------------|
| companion.py | Multiple |
| customer_service.py | Multiple |
| faq.py | Multiple |
| platform_review.py | Multiple |
| risk_control.py | Multiple |
| token_auth.py | Multiple |

### Fix Pattern

```python
# Before
try:
    ...
except:
    pass

# After
try:
    ...
except Exception:
    pass  # Or log the error
```

Use regex for bulk fix:
```python
import re
content = re.sub(r'^(\s*)except\s*:\s*$', r'\1except Exception:', content, flags=re.MULTILINE)
```

## f-string SQL Injection Risk (🟡 Medium)

Files using f-string SQL with dynamic WHERE/ORDER/SET clauses:

| File | Count | Risk Level |
|------|-------|------------|
| admin.py | 12 | Low (fields from ALLOWED white-list) |
| companion.py | 5 | Low (fields from ALLOWED white-list) |
| playmate_api.py | 4 | Low (fields from ALLOWED white-list) |
| review.py | 3 | Low |
| order.py | 1 | Low |
| coupon.py | 1 | Low |
| user.py | 1 | Low |

**Rule**: If the f-string variables come from a pre-defined ALLOWED_FIELDS or `order_map` dict, risk is low. If they come from direct user input, risk is 🔴 critical.

## Variable Scope Bug (🔴 Critical - Flask Pattern)

### Symptom
`NameError: name 'conn' is not defined` at runtime.

### Root Cause
`conn` variable defined inside an `if` block but used outside it:

```python
# BROKEN: conn defined inside 'if' block
if 'phone' in data:
    conn = get_connection()
    ...

# conn used OUTSIDE the if block → NameError!
cur2 = conn.cursor()
```

### Fix
Always get connection at the function start or inside the `try` block:

```python
conn = get_connection()
try:
    ...
```

## Multiple Route Registration

### Issue
The same Blueprint route registered in two different `@bp.route()` decorators, causing the first to be silently overwritten.

### Detection
Search for duplicate route+method combinations:
```python
# Find overlapping route definitions
search_files(r"@\w+_bp\.route\('([^']+)',", path="backend/", file_glob="*.py", output_mode="files_only")
```

## Hardcoded Credentials

- SMTP password in `user.py` — should be in environment variables or config.py
- Database password in `config.py` or inline scripts

## Audit Log Missing

Audit operations (withdrawal approval, companion audit, verify approval) should call `audit_log()` for traceability.
