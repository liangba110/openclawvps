# Session 5 Learnings (2026-07-08)

## Admin Route Dynamic Path
- Vue 3 templates cannot access `sessionStorage` or `window` directly
- Must define in `<script>`: `const adminPath = sessionStorage.getItem('admin_route_path') || 'op-ztHWaT-0706'`
- Then reference `adminPath` in template
- Applies to AdminDashboard.vue, AdminSidebar.vue, AdminLogin.vue

## Build Failure Detection
- Vite exits on first module error; dist remains stale
- Must confirm `✓ built in Xs` in build output
- Common failure: `await` outside `async function`, CSS syntax errors, missing imports
- Clear cache: `rm -rf node_modules/.vite`

## Playmate Orders Status Filter (BUG-6)
- `pendingOrders` (status=0), `activeOrders` (status=1), `historyOrders` (status>=2)
- Was incorrectly putting status=1 into `pendingOrders`, hiding "完成订单" button

## Python `and/or` ≠ Ternary
- `sc == 0 and 0 or -r['id']` → when sc=0, `0 or -10046` = `-10046`
- Use: `0 if sc == 0 else -r['id']`

## Backfill Records for verify_application
- `id=0` for backfill records, `id=-user_id` for approved backfill records
- Approve: send `{user_id: v.user_id}` in request body
- Reject: same pattern, update `user.verify_status=3` + `verify_reason`

## Companion Register Cleanup
- Removed audit fee flow for re-registration
- Now returns fail('您已通过审核，无需重复申请') for status=1
- onMounted in CompanionRegister.vue checks companion status and redirects

## Online Status from login_log
- `favorite/list` and `companion/list` use `LEFT JOIN login_log` with 5-min window
- Not using static `is_online` field (always 1, never updated)

## Notification Chain for Companion Application
- Apply → notify user + notify all admins
- Approve/reject → notify user
- Payment → notify companion
