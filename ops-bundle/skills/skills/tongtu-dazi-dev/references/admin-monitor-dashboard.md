# Admin Monitor Dashboard — Operations Monitoring

## Backend Endpoint

`GET /api/stats/monitor` (in `app/statistics.py` module)

## Data Points

| Field | Source Table | Description |
|-------|-------------|-------------|
| `realtime_active_ips` | `audit_log` (5min window) | Distinct IPs in last 5 min |
| `realtime_requests` | `audit_log` (5min window) | Total requests in last 5 min |
| `login_fails_today` | `audit_log` action='login_fail' | Failed login attempts today |
| `login_fail_ips` | `audit_log` action='login_fail' | Distinct IPs with failures |
| `top_fail_ips` | `audit_log` GROUP BY ip, ORDER DESC | Top 10 failure IPs |
| `banned_ips_count` | `risk_blacklist` | Active bans |
| `banned_ips` | `risk_blacklist` | List with ip/reason/expires |
| `today_register` | `user` WHERE DATE(created_at) | Today's new users |
| `total_users` | `user` COUNT(*) | Total user count |
| `today_orders` | `orders` WHERE DATE(created_at) | Today's orders |
| `today_income` | `orders` SUM(amount) | Today's revenue |
| `order_trend_7d` | `orders` GROUP BY DATE | 7-day order chart data |
| `content_blocks_today` | `audit_log` action='content_block' | Sensitive word hits |
| `pending_reports` | `reports` status=0 | Waiting reports |

## Frontend Component

`frontend/src/views/admin/AdminMonitor.vue` at route `/admin/monitor`

### Layout

```
[实时活跃IP] [登录异常] [封禁IP] [今日订单] [今日收入] [敏感词拦截]
── Tab Content ────────────────────────────────────────────
⏱️ 实时 / 🔐 登录异常 / ⛔ 封禁 / 📦 订单趋势 / 🛡️ 内容安全
```

### Auto-Refresh

30-second polling interval via `setInterval` in `onMounted`:
```js
setInterval(async () => {
  try { Object.assign(m.value, await api.get('/stats/monitor')) } catch {}
}, 30000)
```

### Registration

1. Route: `admin/monitor` → `AdminMonitor.vue`
2. Sidebar: After "控制台" → "📡 运营监控"
3. Admin layout: `<AdminSidebar />` with `margin-left: 220px`
