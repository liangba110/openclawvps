# 2026-07-08 Session Learnings

## 1. Vue 3 Template `sessionStorage` Access

**Vue 3 SFC templates cannot access browser globals like `sessionStorage` directly.** 
- `window.sessionStorage` is compiled to `_ctx.window.sessionStorage` → `window` is undefined as a component property.
- `sessionStorage` alone is also not resolvable in Vue 3 template scope.

**Fix:** Read in `<script setup>` as a `const` and reference the variable in the template:
```vue
<script setup>
const adminPath = sessionStorage.getItem('admin_route_path') || 'default'
</script>
<template>
  <div class="sidebar" @click="$router.push(`/${adminPath}/`">
```

## 2. Admin Layout margin-left Root Cause

The `.admin-main { margin-left: 220px; }` was defined in **`global.css`** (not just individual page scoped CSS). All 19+ admin pages were affected. When fixing admin layout, always check:
1. `src/assets/global.css` — global rules
2. Scoped CSS in each admin page
3. Remove BOTH, not just one

## 3. `0 or X` Evaluates to `X` in Python

```python
# sc=0 → True and 0 → 0 → 0 or -10046 → -10046!!
'id': sc == 0 and 0 or -r['id']

# Fix: proper ternary
'id': 0 if sc == 0 else -r['id']
```

Rule: After `and/or` chain, if left side of `or` is falsy (0, '', None, []), it returns the right side.

## 4. Admin Verify Dual-Table Sync

- `/user/verify` writes `verify_status=2` to `user` table
- Admin `/admin/verifies` reads from `verify_application` table
- **Must INSERT into BOTH tables** — not just user table
- **Backfill:** Historical users with `verify_status=2` but no `verify_application` record need separate query with `UNION` or additional loop
- **Status mapping:** `user.verify_status` (2=pending, 1=approved) ≠ `verify_application.status` (0=pending, 1=approved, 2=rejected)
- **Backfill approved records** also need to show in admin list (add `verify_status IN (1,2,3)`)

## 5. `with conn.cursor() as cur:` Scope Issue

`cur` is CLOSED after the `with` block ends. Any `cur.execute()` call after the block raises `pymysql.err.OperationalError`.

```python
# ❌ Error — cur used outside with block
conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("UPDATE orders SET status=1 WHERE id=%s", (oid,))
        conn.commit()
    cur.execute("SELECT ...")  # ❌ cur is closed here!
except:
    ...

# ✅ Correct — query inside the with block
with conn.cursor() as cur:
    cur.execute("UPDATE orders ...")
    cur.execute("SELECT ...")     # Same cursor, still open
    companion = cur.fetchone()
    companion_uid = companion['user_id'] if companion else None
    conn.commit()
# Now use companion_uid outside the block — it's a Python variable, not a DB cursor
```

## 6. Missing Import Pattern (Silent Vue 3 Failures)

Multiple files had functions used in template but NOT imported in `<script setup>`:

| File | Missing Import | Effect |
|------|---------------|--------|
| AdminMonitor.vue | `safeToast` | Runtime crash on API error |
| AdminWithdrawals.vue | `safeConfirm` | Runtime crash on reject/approve |
| AdminVerify.vue | `computed` | ReferenceError crash |
| Detail.vue | `smartBack` | Click back button does nothing |

**Root cause:** Vue 3 template compiler doesn't check function existence. Missing function = silent failure (no click handler bound).

## 7. Favorites `playmate_id` → `companion_id`

Backend `/favorite/list` returns `companion_id` (companion table PK), but frontend used `item.playmate_id` which doesn't exist in the response.

## 8. Payment Notification for Companion

`/order/pay` only notified the ordering user, not the companion. Companion notification must query companion's user_id INSIDE the `with conn.cursor()` block, store in Python variable, then call `send_notification()` after the with block.
