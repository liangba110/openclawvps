# Session 2026-07-08 (Round 2) — Key Learnings

## 1. Vue 3 Template: `sessionStorage` NOT Accessible

**Root Cause:** Vue 3 SFC template compiler does not whitelist `sessionStorage` (or `window.sessionStorage`) as accessible globals. `window` is also not whitelisted — Vue resolves it as a component property, finds `undefined`, then calling `.getItem` on it throws.

```vue
<!-- ❌ FAILS in template -->
<div @click="sessionStorage.getItem('key')">   <!-- undefined -->
<div @click="window.sessionStorage.getItem('key')">  <!-- undefined.window -->

<!-- ✅ Do this in <script setup> -->
<script setup>
const adminPath = sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'
</script>
<template>
  <div @click="router.push('/' + adminPath + '/users')">✅</div>
</template>
```

**Affected components:** AdminSidebar.vue, AdminDashboard.vue (quick links), any other template that reads `sessionStorage`.

## 2. Admin Quick Links: Each Path Must Be Unique

**Bug:** Regex replacement reduced all 4 quick-link paths to the same dashboard route.

**Fix:** Each quick link must target its specific sub-page: `/users`, `/playmates`, `/orders`, `/reviews`.

## 3. Backfill Verification Record Pattern

**Problem:** `user` table has `verify_status=2` (pending) but no corresponding `verify_application` record.

**Solution:** Query both sources — `verify_application` first, then backfill from `user` table.

**Status mapping (user.verify_status → admin display):**
- user.verify_status=2 (pending) → status_code=0 (待审核)
- user.verify_status=3 (rejected) → status_code=2 (已拒绝)

```python
sc = 0 if s == 2 else (2 if s == 3 else s)
```

## 4. Login-Log Based Online Status

Instead of stale `companion.is_online` (defaults to 1, never updated), use `login_log`:

```sql
CASE WHEN ll.last_active > NOW() - INTERVAL 5 MINUTE THEN 1 ELSE 0 END as online_status
LEFT JOIN (SELECT user_id, MAX(created_at) FROM login_log GROUP BY user_id) ll ON ll.user_id = c.user_id
```

## 5. Python `and/or` is NOT a Ternary

```python
# ❌ BROKEN — sc=0 → 0 or -id → -id (wrong!)
'id': sc == 0 and 0 or -r['id']

# ✅ CORRECT
'id': 0 if sc == 0 else -r['id']
```

## 6. PlaymateOrders Status Filter Bug

Status=1 orders incorrectly in `pendingOrders` instead of `activeOrders`:

```python
# ✅ Correct mapping
pendingOrders = list.filter(o => o.status === 0)    # 待接单
activeOrders  = list.filter(o => o.status === 1)    # 进行中
historyOrders = list.filter(o => o.status >= 2)     # 已完成/已取消
```

## 7. `smartBack` Import Must Be Explicit

Template uses `@click="smartBack(route.path)"` → script must have `import { smartBack } from '@/utils/nav'`.

## 8. `cur` Used Outside `with conn.cursor()` Block

`cur` goes out of scope after `with` block ends. Move companion queries INSIDE the `with` block, before `commit()`.

## 9. File Input Not Cleared After Upload

After uploading front ID card, `<input type="file">` value persists. Selecting same file for back card → `change` event doesn't fire.

**Fix:** `e.target.value = ''` in `finally` block.
