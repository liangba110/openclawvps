# 2026-07-08 Session: Major Bug Patterns

## 1. Flask `Cursor closed` After `with` Block

**Symptom**: `pymysql.err.ProgrammingError: Cursor closed`
**Root Cause**: `cur.execute()` called after `with conn.cursor() as cur:` block ended.

```python
# ❌ WRONG
conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("UPDATE ...")
        conn.commit()
    cur.execute("SELECT ...")  # ❌ CursorClosed here
    r = cur.fetchone()

# ✅ CORRECT
conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("UPDATE ...")
        cur.execute("SELECT user_id FROM companion WHERE id=%s", (cid,))
        companion_user = cur.fetchone()  # inside with block
        conn.commit()
    if companion_user:
        send_notification(companion_user['user_id'], ...)
```

**Affected**: admin.py playmate_audit, order.py pay()

## 2. Companion Orders Status Mapping

**Symptom**: Status=1 (进行中) orders invisible in companion "进行中" tab.

```js
// ❌ WRONG
pendingOrders = list.filter(o => o.status === 0 || o.status === 1)
activeOrders = list.filter(o => o.status === 2)

// ✅ CORRECT
pendingOrders = list.filter(o => o.status === 0)   // 待接单
activeOrders = list.filter(o => o.status === 1)     // 进行中
historyOrders = list.filter(o => o.status >= 2)     // 已完成/取消
```

## 3. Python `0 or X` Ternary Operator Trap

```python
# ❌ WRONG — 0 or -10046 = -10046 (0 is falsy in Python)
'id': sc == 0 and 0 or -r['id']

# ✅ CORRECT
'id': 0 if sc == 0 else -r['id']
```

## 4. Unknown Column Errors

**Check**: Query only fields that exist in the table. `companion` table has no `nickname` column - needs JOIN with `user`.

## 5. Companion Register Duplicate Prevention

When user already has approved companion record (status=1), the `/companion/register` endpoint must return fail early:
```python
if existing['status'] == 1:
    return fail('您已通过审核，无需重复申请')
```

Frontend must also check on page load via `/companion/my` and redirect if already approved.

## 6. Route Path Mismatch (frontend ↔ backend)

**Symptom**: API returns 404/500 but curl test returns 200.
**Root Cause**: Frontend calls `/playmate/profile` but backend route is `/companion/profile` (blueprint prefix mismatch).

**Check**:
```bash
grep "url_prefix" backend/app/xxx.py           # blueprint prefix
grep "@bp.route" backend/app/xxx.py             # route
# Full path = url_prefix + route
```

## 7. Field Name Mapping (bio→intro, max_hours→max_hours_per_day)

Backend must map frontend field names:
```python
field_key = {'intro': 'bio', 'max_hours_per_day': 'max_hours'}.get(field, field)
val = data.get(field_key) or data.get(field)
```

## 8. Admin Global CSS Leak

`global.css`'s `.admin-main { margin-left: 220px; }` affects ALL admin pages. Fix:
```bash
grep "margin-left" frontend/src/assets/global.css
# Delete, then rebuild from clean dist:
rm -rf frontend/dist frontend/node_modules/.vite
```

## 9. Withdrawal Account Binding (Lock After Set)

Once `alipay_account` is set, it's immutable. Name auto-syncs from real-name verification.

## 10. Withdraw Table Account Columns

`withdraw` table must have `alipay_account` and `account_name` columns (added via ALTER TABLE) to display account info in admin approval page.

## 11. AdminWithdrawals Style Consistency

Must match other admin pages: `admin-layout` flex, `tabs-sm` filters, `admin-table` with hover, `badge` status tags, `btn-xs` action buttons.

## 12. Self-Test Required Before Delivery

User explicitly requires: fix → self-test (curl/build/log) → iterate if needed → deliver only when all tests pass.
