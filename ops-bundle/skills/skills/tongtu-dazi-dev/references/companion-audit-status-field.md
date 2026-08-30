# Companion Audit Status Field — Missing in Detail API

## Problem
Admin detail page `/admin/playmate/:id` shows no audit buttons (✅通过/❌拒绝) even though companion is `pending`.

## Root Cause
`companion` table stores audit state as `status` (TINYINT 0/1/2). Admin playmates list API maps it to `audit_status` strings. But detail API returns raw int `status` without mapping → `info.audit_status` is `undefined` → `v-if="info.audit_status === 'pending'"` always false.

## Fix in companion.py detail()
```python
status_map = {0: 'pending', 1: 'approved', 2: 'rejected'}
info['audit_status'] = status_map.get(info.get('status', 0), 'pending')
```

## Verify
```bash
curl http://host/api/companion/detail?id=N | jq '.data.info.audit_status'
# → "pending"
```
