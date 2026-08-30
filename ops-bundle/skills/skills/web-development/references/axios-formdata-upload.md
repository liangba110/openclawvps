# Axios FormData Upload — Content-Type Pitfall

## Problem

File uploads via `FormData` silently fail when axios has a default
`Content-Type: application/json` header. The browser cannot append the
multipart boundary, and the backend receives JSON instead of file data.

**Symptom:** Backend returns `'avatar' not in request.files` or equivalent,
even though the frontend code appears correct.

## Root Cause

```js
// ❌ WRONG: Default header overrides FormData's multipart
const api = axios.create({
  headers: { 'Content-Type': 'application/json' }
})

// This FormData upload will send Content-Type: application/json
// The browser CANNOT set the multipart boundary because the default
// header takes precedence.
const formData = new FormData()
formData.append('avatar', file)
await api.post('/user/avatar/upload', formData)
```

When `Content-Type: application/json` is set as a default, axios sends it
even for FormData requests. The browser normally auto-sets
`Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...`
when it detects FormData, but the explicit default header blocks this.

## Fix

Move `Content-Type` setting into the **request interceptor** and conditionally
delete it for FormData:

```js
// ✅ CORRECT: Conditional Content-Type
const api = axios.create({
  baseURL: '/api',
  timeout: 15000
  // Do NOT set Content-Type here
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // FormData: let browser auto-set multipart boundary
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  } else {
    config.headers['Content-Type'] = 'application/json'
  }
  return config
})
```

## Verification

The built JS should contain the `instanceof FormData` check:

```bash
grep -oP 'instanceof FormData|Content-Type.*application.json' dist/assets/index-*.js
```
