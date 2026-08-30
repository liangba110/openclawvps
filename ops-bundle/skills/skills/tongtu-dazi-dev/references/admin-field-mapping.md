# Admin Backend → Frontend Field Mapping

## Common Mismatch: Backend SQL column names vs Frontend template expectations

### Admin Orders (`/admin/orders`)

**Backend SQL returns:**
- `user_nickname` (customer who placed order)
- `companion_nickname` (companion who received order)
- `status` as integer (0-4)

**Frontend template expects:**
- `customer_nickname`
- `playmate_nickname`
- `status` as string ('pending'/'paid'/'active'/'completed'/'cancelled')
- `duration` as Chinese string ('1小时'/'2小时'/'包夜')

**Fix — Add mapping in backend response loop:**
```python
for item in items:
    item['amount'] = float(item['amount'])
    item['companion_income'] = float(item['companion_income'])
    # Field mapping
    item['customer_nickname'] = item.pop('user_nickname', '')
    item['playmate_nickname'] = item.pop('companion_nickname', '')
    # Integer → string status
    status_map = {0:'pending', 1:'paid', 2:'active', 3:'completed', 4:'cancelled'}
    item['status'] = status_map.get(item['status'], 'unknown')
    # Service duration mapping
    dur = {1: '1小时', 2: '2小时', 3: '包夜'}
    item['duration'] = dur.get(item['service_type'], str(item['service_type']))
```

### General Pattern

When adding or modifying any admin endpoint:
1. curl the endpoint: `curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5002/api/admin/orders" | python3.12 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['list'][0])"`
2. Check every field the frontend template accesses:
   - `order.customer_nickname`, `order.playmate_nickname`, `order.status` in AdminOrders
   - `order.nickname`, `order.status`, `order.created_at` in user Orders
3. If mismatch: either rename SQL column aliases (preferred) or add mapping in backend response loop
