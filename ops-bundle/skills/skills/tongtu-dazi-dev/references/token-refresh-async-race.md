# Token Refresh Async Race Condition — 401 Interceptor Bug

## Problem

Axios interceptor ran logout code (clear token + redirect + toast) **before** the async refresh request completed. The refresh logic was written as a fire-and-forget promise.

**Root cause 1 — Wrong callback:** Backend returns HTTP 401 (status in header), but refresh logic was in the `res` (HTTP 2xx success) callback, not the `err` (HTTP 4xx/5xx error) callback. Axios routes HTTP 4xx to `err`. The refresh **never fired**.

**Root cause 2 — Race condition:** Even in the `err` callback, the code was:
```js
axios.post('/refresh').then(r => { /* set new token */ }).catch(() => {})
// ← THIS ran immediately, before the .then/.catch above
localStorage.removeItem('token')  
router.push('/login')
safeToast('登录已过期')
```

## Fix

### 1. Move refresh logic to the `err` callback (where HTTP 401 arrives)

```js
err => {
    if (err.response && err.response.status === 401) {
      const rt = localStorage.getItem('refresh_token')
      if (rt) {
        return axios.post('/api/user/refresh', { refresh_token: rt }).then(r => {
          if (r.data && r.data.code === 0 && r.data.data && r.data.data.token) {
            localStorage.setItem('token', r.data.data.token)
            const origReq = err.config
            origReq.headers.Authorization = `Bearer ${r.data.data.token}`
            return api(origReq)  // retry original request with new token
          }
          throw new Error('refresh_failed')
        }).catch(() => {
          // refresh failed → cleanup + redirect
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          localStorage.removeItem('refresh_token')
          router.push(isAdmin ? '/admin/login' : '/login')
          safeToast('登录已过期，请重新登录')
          return Promise.reject(new Error('登录已过期'))
        })
      }
      // no refresh_token → direct logout
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('refresh_token')
      router.push(isAdmin ? '/admin/login' : '/login')
      safeToast('登录已过期，请重新登录')
      return Promise.reject(new Error('登录已过期'))
    }
    ...
}
```

### 2. Key changes:
- `return axios.post(...)` — returns the promise chain so the interceptor WAITS for it
- Logout/redirect code is inside `.catch()` — only runs after refresh actually fails
- `return api(origReq)` — retries the original failed request with the new token
- `return Promise.reject(new Error('登录已过期'))` — ensures callers receive a rejection
- Also cleans `refresh_token` from localStorage on logout (was missing)

### 3. Remove dead code in the `res` callback

The success handler's 401 check (`if (res.data.code === 401)`) is dead code for routes that return HTTP 401. Keep it as a safety net but mark it as such. The real handler is in the `err` callback.

## Pattern
Always remember: **HTTP 401 → `err` callback. JSON code 401 → `res` callback.** Flask backends using `return jsonify(...), 401` send HTTP 401, so the err callback is the right place.

## Verification
```js
// Test refresh works:
// 1. Login → get token + refresh_token
// 2. Wait 30min (or manually expire token in DB)
// 3. Make an API call → should auto-refresh silently
// 4. Check LocalStorage: token should be new value
// 5. No "登录已过期" toast should appear
```
