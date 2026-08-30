# Token 自动续期修复（全链路）

## 问题表现

1. 登录后约30分钟自动退出（原 `ACCESS_TOKEN_TTL=1800`）
2. **微信一键登录后直接「页面加载出错」白屏** — 最严重表现

## 根因链

### 致命 Bug：WxLogin.vue 未定义变量

```js
// ❌ WxLogin.vue — refreshToken 从未声明，ES Module strict 模式抛 ReferenceError
localStorage.setItem('refresh_token', refreshToken || '')
// ReferenceError: refreshToken is not defined → onErrorCaptured → 「页面加载出错」
```

### 后端缺失 refresh_token

后端 `wechat_login.py` OAuth 回调使用旧版 `create_token()`（纯JWT），未使用 v2 token 系统：

```python
# ❌ 无 refresh_token
token = create_token(user_id, openid[:16])
return redirect(f'.../wx-login?token={token}&nickname=...')
```

v2 token 系统（`token_auth.py`）提供 `gen_token()` + `gen_refresh_token()`，但 OAuth 回调没用它。

### 其他缺失

- `BindPhone.vue` 也只存了 `token` 没存 `refresh_token`
- Server B 上旧编译文件（旧 hash 的 `WxLogin-*.js`）未被清理，浏览器加载旧版

## 修复清单（4 个文件必须同步修改）

### 1. 后端 `wechat_login.py` — OAuth 回调用 v2 token 系统

```python
from app.token_auth import gen_token, gen_refresh_token
from urllib.parse import urlencode

device_id = f'wx_{openid[:8]}'
access_token = gen_token(user_id, device_id)
refresh_tok = gen_refresh_token(user_id, device_id)
params = urlencode({'token': access_token, 'refresh_token': refresh_tok, 'nickname': nickname})

if u and not u['phone_bound']:
    return redirect(f'https://dazi.openai2000.cn/#/bind-phone?{params}')
return redirect(f'https://dazi.openai2000.cn/#/wx-login?{params}')
```

### 2. 前端 `Login.vue` — 从 API 响应保存

```js
// ✅ 正确
localStorage.setItem('token', r.token)
localStorage.setItem('refresh_token', r.refresh_token || '')   // r.refresh_token 来自后端 user.py login()
localStorage.setItem('user', JSON.stringify(r))
```

### 3. 前端 `WxLogin.vue` — 从 URL query 读取（关键！）

```js
// ❌ 错误：变量未定义 → ReferenceError 页面崩溃
localStorage.setItem('refresh_token', refreshToken || '')

// ✅ 正确：从 route.query 读取
localStorage.setItem('token', token)
localStorage.setItem('refresh_token', route.query.refresh_token || '')
```

### 4. 前端 `BindPhone.vue` — 同样从 URL query 保存

```js
localStorage.setItem('token', token.value)
if (route.query.refresh_token) {
    localStorage.setItem('refresh_token', route.query.refresh_token)
}
```

## 辅助排查

### 检查 Server B 旧文件残留

Vite 每次构建生成新 hash 文件，但 `deploy.sh` 用 `scp`（不是 `rsync --delete`），旧文件累积：

```bash
# 检查旧文件
ssh ubuntu@82.157.202.24 "ls /home/ubuntu/ttdazi-frontend/assets/WxLogin-*.js"
# 如果 > 1 个文件 → 有旧残留

# 手动清理
ssh ubuntu@82.157.202.24 "rm -f /home/ubuntu/ttdazi-frontend/assets/旧文件名.js"
```

### 验证编译产物

```bash
grep -c "refresh_token\|refreshToken" /opt/ttdazi/frontend/dist/assets/WxLogin-*.js
# refreshToken（无下划线）→ 0  => 旧Bug已清除
# refresh_token（有下划线）→ >=1  => 新代码正确
```

## 参数配置

```python
# token_auth.py
ACCESS_TOKEN_TTL = 7200       # 2小时（原1800秒太短）
REFRESH_TOKEN_TTL = 604800    # 7天
```

## ⚠️ 2026-08 二次修复：仍频繁过期退出 → 三管齐下

用户报「过段时间就自动退出，提示登录过期」。虽然拦截器已有 refresh 逻辑，但：
- 2 小时 token 对低频用户仍太短（不活跃时过期）
- refresh 接口只发新 access，**refresh_token 7 天到了就死**（无滚动续期）
- 前端多个请求同时 401 会**并发重复 refresh**，互相覆盖 localStorage

### 修复清单

1. **后端 `token_auth.py`：ACCESS_TOKEN_TTL 7200 → 604800（7 天）**
   低频用户 7 天内基本不会过期；配合滚动续期形成永续链。

2. **后端 `user.py /refresh`：滚动续期（删旧发新）**
   ```python
   new_token = gen_token(user_id, device_id)
   # 删除旧 refresh_token，插入新的（7天）
   cur.execute("DELETE FROM refresh_token WHERE token=%s", (refresh_tok,))
   cur.execute("INSERT INTO refresh_token (user_id, token, device_id, ip, expires_at) VALUES (...)")
   return success({'token': new_token, 'refresh_token': new_refresh, 'device_id': device_id})
   ```
   注意 import：`from app.token_auth import ..., REFRESH_TOKEN_TTL`（否则 Pyright 报未定义）。

3. **前端 `api/index.js`：并发去重 + 统一清理**
   ```javascript
   let refreshing = null
   function doRefresh() {
     if (refreshing) return refreshing          // 去重：进行中直接复用同一 promise
     const rt = localStorage.getItem('refresh_token')
     if (!rt) return Promise.reject(new Error('no_refresh'))
     refreshing = axios.post('/api/user/refresh', { refresh_token: rt }).then(r => {
       localStorage.setItem('token', r.data.data.token)
       if (r.data.data.refresh_token) localStorage.setItem('refresh_token', r.data.data.refresh_token)  // 滚动更新
       return r.data.data.token
     }).finally(() => { refreshing = null })
     return refreshing
   }
   function clearAuth(admin) {
     localStorage.removeItem('token'); localStorage.removeItem('user'); localStorage.removeItem('refresh_token')
     router.push(admin ? '/op-1MQujA-0716/login' : '/login')
   }
   // 拦截器 res 分支 code===401 与 err 分支 status===401 都改为：
   return doRefresh().then(newToken => { origReq.headers.Authorization = `Bearer ${newToken}`; return api(origReq) })
     .catch(() => { clearAuth(isAdmin); safeToast('登录已过期，请重新登录'); return Promise.reject(...) })
   ```
   axios 拦截器返回的是 res.data.data（已解包），所以 401 业务码在 res 分支、HTTP 401 在 err 分支，两处都要改。

### 验证
- `gen_token` 后 `parse_token()['expires_in']` ≈ 604799 秒（7 天）
- curl 登录 → refresh → 返回新 token + 新 refresh_token
- 浏览器：登录 → 清 token 留 refresh → 任意请求 → 自动续期且不跳登录页

## 验证方法

1. 微信登录 → 检查 localStorage 中是否同时有 `token` 和 `refresh_token`
2. 等待 2 小时+（或手动清除 token 但保留 refresh_token）→ 刷新页面 → 应自动续期
3. 检查浏览器控制台 → 不应有 `ReferenceError: refreshToken is not defined`
4. 检查 Server B 上的 JS 文件数：`ls /home/ubuntu/ttdazi-frontend/assets/WxLogin-*.js` 应只有 1 个

## 相关文件

- `/opt/ttdazi/backend/app/wechat_login.py`
- `/opt/ttdazi/backend/app/token_auth.py`
- `/opt/ttdazi/frontend/src/views/WxLogin.vue`
- `/opt/ttdazi/frontend/src/views/Login.vue`
- `/opt/ttdazi/frontend/src/views/BindPhone.vue`
- `/opt/ttdazi/frontend/src/api/index.js`（401 拦截器，可自动续期）
