# Backend → Database Type Mismatch Debugging

## Problem: MySQL column type doesn't match what the ORM/code sends

The most common manifestation: code sends strings, but the MySQL column is `TINYINT` or `INT`.
Results in either `pymysql.err.DataError: (1366, "Incorrect integer value: 'string' for column 'X'")`
(500 error) or silently broken logic.

## Example 1: Gender field — TINYINT vs String

**Database:** `gender TINYINT DEFAULT 0` (values: 0=secret, 1=male, 2=female)
**Frontend sends:** `"gender": "male"` (string)
**Backend tries:** `UPDATE user SET gender='male'` → MySQL rejects integer column with string

```
pymysql.err.DataError: (1366, "Incorrect integer value: 'female' for column 'gender' at row 1")
```

**Fix — backend-side mapping:**

```python
# In update endpoint: string → int
GENDER_MAP = {'male': 1, 'female': 2, 'secret': 0}
if isinstance(g, str) and g in GENDER_MAP:
    params.append(GENDER_MAP[g])  # Store as integer

# In query endpoint: int → string (for frontend compatibility)
'gender': {0: 'secret', 1: 'male', 2: 'female'}.get(user['gender'], 'secret')
```

**Never fix on frontend alone** — the frontend uses strings because that's the UX convention
(displaying '男'/'女'). The backend must handle the mapping.

## Example 2: Status field — TINYINT vs String (audit_status)

**Database:** `status TINYINT` (0=pending, 1=approved, 2=rejected)
**Backend returns raw INT:** `{"audit_status": 0}`
**Frontend expects STRING:** `pm.audit_status === 'pending'` → always false

```
Before: Frontend sees 0, checks for 'pending' → no match → no action buttons
After:  Backend maps 0→'pending', 1→'approved', 2→'rejected' in API response
```

## Debugging Checklist (Type Mismatch)

1. **Check MySQL schema:** `DESCRIBE table_name` — look at the `Type` column
2. **Check what the API actually returns:** `curl` the endpoint and inspect JSON values
3. **Check what the frontend expects:** Read the template code for comparisons like `=== 'string'` or `=== 0`
4. **Choose the conversion layer:**
   - Database <→ Backend: always backend's job
   - Backend <→ Frontend: backend should normalize to frontend-friendly types (strings, not ints)
5. **Search for all return sites:** login, register, profile, admin list, etc. — fix ALL of them

## Example 3: Admin audit — multi-parameter mismatch (URL + method + field + value)

This is a compound bug where frontend and backend disagree on FOUR things at once:

```
Frontend: POST /admin/playmate/:id/toggle-online  { status: 'approved' }
Backend:  PUT  /admin/playmate/:id/toggle          { action: 'approve' }
```

| Dimension | Frontend | Backend |
|-----------|----------|---------|
| URL | `toggle-online` | `toggle` |
| Method | `POST` | `PUT` |
| Field | `status` | `action` |
| Value | `'approved'` | `'approve'` |

**Fix checklist — test with curl first, then align backend to match frontend expectations:**

1. `@admin_bp.route` → add `POST` to methods tuple
2. Accept both `data.get('status')` AND `data.get('action')`
3. Accept both `'approved'` AND `'approve'` (and their rejects)
4. Use `status == 1` (integer) for logic decisions, not raw string comparison
5. Fix all downstream comparisons (`if action == 'approve'` → `if status == 1`)

## Example 4: Wrong DB column used for toggle (is_online vs status)

**Symptom:** Admin clicks "下架" (take offline), companion still shows in discovery list.

**Root Cause:** The toggle endpoint writes to `companion.status` (approval status 0/1/2),
but the discovery list filters by `companion.is_online` (online/offline 0/1). Two different
columns serve two different purposes but the toggle code confused them.

**Fix:** The `is_online` column controls visibility. Audit endpoints use `status`.
The toggle endpoint must use `is_online`:
```python
# Wrong: UPDATE companion SET status=%s
# Right: UPDATE companion SET is_online=%s
cur.execute("SELECT id, is_online FROM companion WHERE id=%s", (cid,))
new_val = 0 if c['is_online'] else 1
```

Then search EVERY query that filters the companion list and ensure it includes `c.is_online=1`.

## Prevention

- Add a comment in the backend route noting the DB type: `# gender is TINYINT in MySQL, map to string for API`
- Use enumerations or constants instead of magic strings/ints throughout
- Test the API with curl before deploying frontend changes that depend on new field types
- For admin endpoints, curl-test with the actual frontend payload format before writing frontend code
