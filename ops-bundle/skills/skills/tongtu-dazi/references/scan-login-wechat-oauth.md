# 扫码登录流程 — 微信OAuth + ScanConfirm 确认页

> 与 `wechat-scan-register.md`（扫码注册）互补。本文件覆盖 **PC端登录页的「扫码登录」Tab** 的完整链路。

## 架构

```
PC端 Login.vue                         手机微信
┌─────────────────────┐               ┌──────────────────────────┐
│ POST /login/scan/   │               │                          │
│     create           │               │                          │
│ → 返回 {code,url}    │               │                          │
│ → 生成QR码           │               │                          │
│                      │    ←扫码      │ WeChat内置浏览器打开      │
│                      │               │ /#/scan-confirm?code=XXX │
│                      │               │                          │
│ 轮询 /login/scan/    │               │ 【ScanConfirm.vue】      │
│   status?code=XXX    │               │                          │
│   每1.5s             │               │ ▸ 有token→显示确认按钮    │
│                      │               │ ▸ 无token→显示微信一键登录│
│                      │               │                          │
│                      │  点击微信登录→│ /api/wechat/login-scan    │
│                      │               │   ?code=XXX              │
│                      │               │   → OAuth授权            │
│                      │               │   → callback             │
│                      │               │     state=scan_{code}    │
│                      │               │                          │
│                      │   ←跳回确认页  │ /#/scan-confirm?code=XXX │
│                      │               │   &token=YYY&auto=1      │
│                      │               │                          │
│                      │               │ ▸ 存token→拉取user→      │
│                      │               │   POST /login/scan/      │
│                      │               │     confirm (自动确认)    │
│                      │               │                          │
│ 轮询到status=2+token │               │                          │
│ → localStorage      │               │                          │
│ → 跳转首页          │               │                          │
└─────────────────────┘               └──────────────────────────┘
```

## 后端文件

### `wechat_login.py` — OAuth端点

**新增端点** `/api/wechat/login-scan`:

```python
@wx_bp.route('/login-scan')
def wx_login_scan():
    """扫码确认页内的微信登录 - 登录后跳回确认页完成确认"""
    scan_code = request.args.get('code', '')
    # redirect to WeChat OAuth with state=scan_{code}
    url = (
        f'https://open.weixin.qq.com/connect/oauth2/authorize'
        f'?appid={WX_APPID}'
        f'&redirect_uri={quote(REDIRECT_URI)}'
        f'&response_type=code'
        f'&scope=snsapi_userinfo'
        f'&state=scan_{scan_code}#wechat_redirect'
    )
    return redirect(url)
```

### `callback` — state 判读

```python
is_scan_login = state.startswith('scan_')
scan_code = state[5:]  # strip 'scan_' prefix

# 扫码登录流程
if is_scan_login and scan_code:
    cur.execute("SELECT phone_bound FROM `user` WHERE id=%s", (user_id,))
    u_scan = cur.fetchone()
    conn.commit()
    # 生成token
    scan_token = gen_token(user_id, f'wx_scan_{openid[:8]}')
    scan_refresh = gen_refresh_token(user_id, f'wx_scan_{openid[:8]}')
    params = urlencode({'code': scan_code, 'token': scan_token, 'refresh_token': scan_refresh})
    if u_scan and not u_scan['phone_bound']:
        return redirect(f'https://dazi.openai2000.cn/#/bind-phone?{params}&return=scan')
    return redirect(f'https://dazi.openai2000.cn/#/scan-confirm?{params}&auto=1')
```

## 前端

### `ScanConfirm.vue` — 扫码确认页（含微信登录）

位于 `/opt/ttdazi/frontend/src/views/ScanConfirm.vue`

**核心逻辑（onMounted）**：

1. 从 URL 参数读取 `code`、`token`、`refresh_token`、`auto`
2. 如有 `token` 参数 → 存 `localStorage`
3. 无 user 但有 token 时 → 调用 `/user/profile` 拉取并缓存
4. 根据 `auto=1` 标志 + `hasToken` 状态决定是否自动确认

**组件状态**：
- `hasToken=true` + 未确认 → 显示「确认登录」按钮
- `hasToken=false` → 显示「微信一键登录」按钮（OAuth入口）
- 确认后 → 显示成功提示

## 关键陷阱 & 已修复的Bug

### 陷阱1：自动确认时序问题 ⚠️

**问题**：OAuth 回调后，`onMounted` 中的 `auto_confirm` 检查跑在异步 profile fetch 之前，`hasToken` 始终为 `false`，自动确认从未触发。

**修复**：将 `needAutoConfirm && hasToken.value` 检查移到 profile fetch 之后。

```javascript
// ❌ 错误代码 — auto confirm 在 profile fetch 之前
const user = JSON.parse(localStorage.getItem('user') || '{}')
hasToken.value = !!user.id
await fetchProfile()  // hasToken 还是 false!
if (needAutoConfirm && hasToken.value) { ... }  // 永远不进

// ✅ 正确 — auto confirm 在 profile fetch 之后
await fetchProfile()
// hasToken 已更新为 true
if (needAutoConfirm && hasToken.value) {
    setTimeout(() => doConfirm(), 500)
}
```

### 陷阱2：绑定手机后 token 丢失

**问题**：BindPhone.vue 绑定成功后 redirect 到 scan-confirm 时不带 `token` 参数，scan-confirm 的 `if (urlToken && !localUser.id)` 条件不满足，profile fetch 被跳过。

**修复**：条件改为 `if ((urlToken || token) && !localUser.id)` — 同时检查 URL 参数和 localStorage 中的 token。

### 陷阱3：初次扫码用户无 token

**问题**：扫码登录流程要求用户在手机上已登录（`@login_required`），但第一次使用的用户没有 token，卡在「未登录」状态。

**修复**：ScanConfirm 页内置「微信一键登录」按钮，点击后直接走 OAuth 流程，登录成功后 token 传回页面。

### 陷阱4：未处理 BindPhone「跳过」后重定向

**问题**：BindPhone 的「暂不绑定，跳过」直接跳首页，扫码用户丢失流程。

**修复**：BindPhone 增加 `return=scan` 参数判断，跳过时也跳回 scan-confirm：
```javascript
function skip() {
    if (isScanReturn.value && scanCode.value) {
        router.replace(`/scan-confirm?code=${scanCode.value}&auto=1`)
    } else {
        router.replace('/')
    }
}
```

## 相关文件

| 文件 | 说明 |
|:-----|:------|
| `/opt/ttdazi/backend/app/wechat_login.py` | OAuth 端点 + callback |
| `/opt/ttdazi/backend/app/scan_login.py` | 扫码会话管理 |
| `/opt/ttdazi/frontend/src/views/ScanConfirm.vue` | 扫码确认页 |
| `/opt/ttdazi/frontend/src/views/BindPhone.vue` | 手机绑定页 |
| `/opt/ttdazi/frontend/src/views/Login.vue` | 登录页（扫码Tab） |
