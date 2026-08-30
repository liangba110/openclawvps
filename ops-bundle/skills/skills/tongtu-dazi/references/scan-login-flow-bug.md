# 扫码登录首次使用流程断裂

## 问题

PC端「扫码登录」（Login.vue → 扫码Tab）生成的二维码，首次使用的用户扫码后无法完成登录。

## 症状

1. PC显示二维码 → 用户用微信扫码
2. 手机微信打开 `/#/scan-confirm?code=XXX` 页面
3. 页面检查 `localStorage` 无 token → 显示「未登录」+「请先在手机上登录账号」
4. 用户点「先去登录」→ 跳转到 `/login`
5. 点「微信一键登录」→ OAuth 授权 → 登录成功
6. 回调跳转到 `/#/wx-login?token=XXX` 或 `/#/bind-phone`
7. **确认页已经丢失** → 用户需要手动回退或重新扫码
8. 如果二维码已过期（5分钟TTL），用户得回PC刷新→再次扫码，体验极差

## 根因

**扫码登录流程（scan_login.py）** 和 **微信登录流程（wechat_login.py）** 是断裂的：

```
扫码确认页                   微信OAuth
┌─────────────────┐        ┌─────────────────┐
│ 需要 token       │        │ 授权后 redirect  │
│ 才能点确认       │   →    │ 到 wx-login     │
│                  │        │ 不是回到确认页    │
└─────────────────┘        └─────────────────┘
```

关键断裂点：`/api/wechat/callback` 的 `state` 参数不携带扫码 session code，回调后无法回跳确认页。

```python
# wechat_login.py callback — 登录后重定向到首页，不回确认页
return redirect(f'https://dazi.openai2000.cn/#/wx-login?{params}')
```

同时 `scan_login.py` 的 `/api/login/scan/confirm` 有 `@login_required` 守卫，未登录用户无法直接确认。

## 修复方案（已实施 — 2026-07-30）

采用**方案B**的变体：新增独立端点 `/api/wechat/login-scan`，通过 `state=scan_{code}` 传递扫码code，callback解析后带 token 跳回确认页。

### 改动总览

| 文件 | 改动 |
|:-----|:-----|
| `wechat_login.py` | 新增 `GET /api/wechat/login-scan?code=XXX` → OAuth 带 `state=scan_{code}`；callback 处理 `scan_` 状态 + 绑定手机后回跳 |
| `ScanConfirm.vue` | 「先去登录」→「微信一键登录」按钮直接调 `/api/wechat/login-scan`；OAuth 回调后自动存 token + 自动确认 |
| `BindPhone.vue` | 绑完手机或「跳过」时，如带 `return=scan&code=XXX` 参数则跳回确认页而非首页 |

### 完整新流程

```
PC扫码 → 手机微信打开确认页
  └→ 未登录 → 点「微信一键登录」
      → OAuth授权（state=scan_{code}）
      → 自动注册/登录
      → 首次需绑手机 → 绑完回确认页（绑定后 auto=1 自动确认）
      → 点「确认登录」 → PC端 token 生成 → PC自动登录 ✅
```

### 后端改动详情

#### 1. wechat_login.py — 新增 /login-scan 端点

```python
@wx_bp.route('/login-scan')
def wx_login_scan():
    """扫码确认页内的微信登录 - 登录后跳回确认页完成确认"""
    from urllib.parse import quote
    scan_code = request.args.get('code', '')
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

#### 2. wechat_login.py — callback 处理 scan_ 状态

```python
# 在callback中识别scan_状态
is_scan_login = state.startswith('scan_')
scan_code = state[5:] if is_scan_login else ''

# 扫码登录流程：跳回确认页
if is_scan_login and scan_code:
    cur.execute("SELECT phone_bound FROM `user` WHERE id=%s", (user_id,))
    u_scan = cur.fetchone()
    conn.commit()
    scan_token = gen_token(user_id, f'wx_scan_{openid[:8]}')
    scan_refresh = gen_refresh_token(user_id, f'wx_scan_{openid[:8]}')
    params = urlencode({'code': scan_code, 'token': scan_token, 'refresh_token': scan_refresh})
    if u_scan and not u_scan['phone_bound']:
        return redirect(f'https://dazi.openai2000.cn/#/bind-phone?{params}&return=scan')
    return redirect(f'https://dazi.openai2000.cn/#/scan-confirm?{params}&auto=1')
```

#### 3. BindPhone.vue — 绑完跳回确认页

```javascript
// 绑定成功时
if (isScanReturn.value && scanCode.value) {
    router.replace(`/scan-confirm?code=${scanCode.value}&auto=1`)
}
// 跳过时同理
```

#### 4. ScanConfirm.vue — 集成微信一键登录 + 自动确认

```javascript
// 监听URL参数（OAuth回调带回来的）
const urlToken = route.query.token || ''
if (urlToken) {
    localStorage.setItem('token', urlToken)
}

// 自动确认（auto=1 来自OAuth回调或绑定页回跳）
if (needAutoConfirm && hasToken.value) {
    setTimeout(() => doConfirm(), 500)
}

// 微信一键登录按钮
function wxScanLogin() {
    if (/MicroMessenger/i.test(navigator.userAgent)) {
        window.location.href = '/api/wechat/login-scan?code=' + code.value
    } else {
        router.push('/login')
    }
}
```

### ⚠️ 关键陷阱

1. **BindPhone.vue 必须感知扫码流程** — 非扫码流程的绑手机行为不能改变。在 `onMounted` 中读取 `route.query.return === 'scan'` 和 `route.query.code` 来判断。

2. **ScanConfirm.vue 必须处理双重入口** — 用户可能直接访问（二维码扫码，无token），也可能OAuth回调回来（URL带token+auto参数）。`onMounted` 需两套逻辑都处理。

3. **token已在前端不意味user信息也在** — OAuth回调带回了token但没带回user信息。ScanConfirm.vue 中如果 `hasToken && !user.id`，需调用 `/api/user/profile` 补充。

4. **callback 中 u 变量作用域** — 扫码流程在 callback 的 `if is_scan_login` 分支内，需要自己执行 `SELECT phone_bound`，不能依赖后面普通登录流程的 `u` 变量（会报 pyright 未绑定错误）。

5. **state字符串拆分** — 扫码注册用 `reg_` 前缀（4字符），扫码登录用 `scan_` 前缀（5字符），提取code时长度不同：
   ```python
   scan_code = state[4:] if is_register else (state[5:] if is_scan_login else '')
   ```

## 相关文件

| 文件 | 角色 |
|:-----|:-----|
| `/opt/ttdazi/backend/app/scan_login.py` | 扫码登录会话管理 |
| `/opt/ttdazi/backend/app/wechat_login.py` | 微信OAuth回调 + login-scan端点 |
| `/opt/ttdazi/frontend/src/views/ScanConfirm.vue` | 扫码确认页（微信一键登录集成） |
| `/opt/ttdazi/frontend/src/views/BindPhone.vue` | 手机绑定页（扫码流程回跳支持） |
| `/opt/ttdazi/frontend/src/views/Login.vue` | PC登录页（含扫码Tab） |
| `scan_login` 表 | 会话存储（status: 0待扫, 1已扫, 2已确认） |
