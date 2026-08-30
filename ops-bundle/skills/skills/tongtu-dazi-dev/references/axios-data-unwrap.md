# Axios Interceptor data-unwrap Pitfall

## The Interceptor

```js
// frontend/src/api/index.js
api.interceptors.response.use(
  res => {
    if (res.data.code !== 0) {
      return Promise.reject(new Error(res.data.msg || '请求失败'))
    }
    return res.data.data   // UNWRAP: caller sees ONLY the data field
  }
)
```

## Mandatory Backend Response Shape

```json
{"code": 0, "data": { ...actual payload... }, "msg": "ok"}
```

## Real Bug: Download Password "密码错误" (2026-07-04)

**Symptom:** User enters correct password `wll16562341@`, Download.vue shows "密码错误，请重试".

**Root cause:**
```python
# Backend returned:
return jsonify({'code': 0, 'token': f'{ts}.{sign}', 'msg': 'ok'})

# Axios interceptor does: res.data.data → undefined
# Frontend receives: undefined
# if (res.token) → false → falls into catch → shows error
```

**Fix:**
```python
return jsonify({'code': 0, 'data': {'token': f'{ts}.{sign}'}, 'msg': 'ok'})
```

## How to Diagnose This Class of Bug

1. `curl` the endpoint → is the payload at top level or wrapped in `data`?
2. If top level but frontend sees undefined → add `data` wrapper
3. If already in `data` but frontend still broken → check `code` field is 0

## All Affected Endpoints (checklist for new APIs)

Any new backend route that returns success data MUST use:
```python
return success(data, 'ok')  # where success() wraps: {"code":0, "data": data, "msg": msg}
```

When writing raw `jsonify()`:
```python
# ✅ Correct
return jsonify({'code': 0, 'data': {'id': row_id}, 'msg': 'ok'})

# ❌ Wrong — frontend gets undefined
return jsonify({'code': 0, 'id': row_id, 'msg': 'ok'})
```
