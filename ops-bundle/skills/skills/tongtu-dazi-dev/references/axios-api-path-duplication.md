# 前端 API 路径重复 /api/（axios baseURL 陷阱）

## 问题

axios 实例配置了 `baseURL: '/api'`，当前端调用 `api.post('/api/xxx')` 时，实际请求 URL 变为 `/api/api/xxx`，导致 404。

## 排查

```bash
# 浏览器 DevTools Network 面板查看实际请求 URL
# 或检查构建产物中对应的 API 路径
grep -oP 'api\.(get|post|put|delete)\([^)]+' file.vue
```

## 修复

```js
// ❌ 错误：/api/api/pay/wxpay/native
await api.post('/api/pay/wxpay/native', data)

// ✅ 正确：/api/pay/wxpay/native（baseURL 自动补 /api）
await api.post('/pay/wxpay/native', data)
```

## 影响范围

所有通过 axios `api` 实例调用的接口。只影响前端 Vue 代码，不影响后端 curl 测试。

## 常见出错模式

| 前端代码 | 实际请求 | 结果 |
|---------|---------|------|
| `api.post('/api/pay/wxpay/native')` | `/api/api/pay/wxpay/native` | 🔴 404 |
| `api.post('/pay/wxpay/native')` | `/api/pay/wxpay/native` | ✅ 正确 |
| `api.get('/api/user/profile')` | `/api/api/user/profile` | 🔴 404 |
| `api.get('/user/profile')` | `/api/user/profile` | ✅ 正确 |

## 原因

`api/index.js`:
```js
const api = axios.create({
  baseURL: '/api',  // ← 这里已有 /api 前缀
  timeout: 15000
})
```

开发者习惯在 curl 中使用完整路径（如 `/api/pay/wxpay/native`），复制到前端代码时忘记 baseURL 会自动拼接 `/api`。
