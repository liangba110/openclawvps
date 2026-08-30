# Admin List API — res.list Unwrap Pattern & Route Mismatches

## Symptom

```js
// Console error:
GET http://82.157.202.24/api/admin/user/list 404 (NOT FOUND)
// OR
TypeError: (a || []).map is not a function
```

## Root Cause

Two possible issues:

### 1. Wrong API path
Frontend calls `/admin/user/list` but backend route is `@admin_bp.route('/users')` → `/admin/users`.

**Fix:** `api.get('/admin/users')`

### 2. Data-unwrap mismatch (MORE COMMON)

Backend list endpoints return:
```json
{"code":0, "data": {"list": [...], "total": 99, "page": 1, "page_size": 20}, "msg": "ok"}
```

Axios interceptor unwraps `res.data.data` → caller receives:
```js
{list: [...], total: 99, page: 1, page_size: 20}  // ← OBJECT, not array!
```

Frontend incorrectly treats this as an array:
```js
// ❌ WRONG
const res = await api.get('/admin/orders', { params })
allOrders.value = (res || []).map(...)  // res is object → .map not a function!

// ❌ WRONG  
const res = await api.get('/admin/users')
list.value = res || []  // list is object, filter fails
filtered.value = list.value  // filtered is also object, v-for over object
```

**Correct:**
```js
const res = await api.get('/admin/orders', { params })
allOrders.value = ((res && res.list) || []).map(...)

const res = await api.get('/admin/users')
list.value = (res && res.list) || []
filtered.value = list.value
```

## Affected Files

| Page | Route (frontend) | Route (backend) | Data unwrap |
|------|-----------------|-----------------|-------------|
| AdminUsers | `/admin/users` (was `/admin/user/list`) | `@admin_bp.route('/users')` | `res.list` |
| AdminOrders | `/admin/orders` | `@admin_bp.route('/orders')` | `res.list` |
| AdminPlaymates | `/admin/playmates` | uses counts/list | `res.list` |

## Backend Pattern

All admin list endpoints follow this return shape:
```python
return success({
    'list': items,
    'total': total,
    'page': page,
    'page_size': page_size,
})
```
