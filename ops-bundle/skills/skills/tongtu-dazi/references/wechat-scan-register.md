# 微信扫码注册（PC端QR → 手机微信授权 → PC自动登录）

## 原理

复用 `scan_login` 表 + 公众号 OAuth 授权。PC端生成二维码 → 用户微信扫码 → 跳转微信授权页 → 授权后自动创建用户 → PC轮询检测到注册完成 → 自动登录。

## 完整流程

```
PC端 Register.vue                  手机微信
┌─────────────────────┐           ┌─────────────────────┐
│ POST /register/wx/  │           │                     │
│     create           │           │                     │
│ → 返回 {code,code_url}│           │                     │
│ → 用qrcode包生成QR   │           │                     │
│ → 显示二维码         │   ←扫码   │ 微信打开             │
│ → 启轮询 1.5s/次     │           │ /api/wechat/qr-     │
│ GET /register/wx/    │           │ register?code=XXX   │
│     status?code=XXX  │           │ ↓ 302重定向          │
│                     │           │ 微信OAuth授权页      │
│                     │           │ (用户点击"允许")      │
│                     │  ──────→  │ → code + reg_XXX     │
│                     │           │ → callback: 创建用户  │
│                     │           │ → UPDATE scan_login  │
│                     │           │   SET status=2,token │
│                     │           │ → 显示"注册成功"页   │
│ 轮询到 status=2     │           │                     │
│   + token           │           │                     │
│ → localStorage      │           │                     │
│ → 跳转首页          │           │                     │
└─────────────────────┘           └─────────────────────┘
```

## 后端文件

### `scan_register.py` — 扫码注册会话管理

**路径**: `/opt/ttdazi/backend/app/scan_register.py`
**蓝图**: `scan_reg_bp` (`url_prefix='/api/register'`)

| 端点 | 方法 | 说明 |
|:-----|:----:|:------|
| `/wx/create` | POST | 创建扫码注册会话，写入 scan_login (status=0)，返回 `{code, code_url, expires_in}` |
| `/wx/status` | GET | PC轮询状态，参数 `?code=XXX`，返回 `{status: -1/0/2, token?}` |

**状态码**: 0=待扫码, 2=已注册(带token), -1=已过期

**关键**: QR_URL 指向 `https://dazi.openai2000.cn/api/wechat/qr-register`，携带 session code 参数。

### `wechat_login.py` — 微信OAuth对接（新增注册分支）

**路径**: `/opt/ttdazi/backend/app/wechat_login.py`

新增端点:
- `GET /api/wechat/qr-register?code=XXX` — 接收 session code → 组装 OAuth URL 并跳转，state 设为 `reg_{code}`

修改 `callback`:
- 读取 `state` 参数，判断是否以 `reg_` 开头
- 如果是注册流程：
  1. 正常换取 access_token + 获取用户信息
  2. 查找或新建用户 (`wx_openid` 唯一标识)
  3. 生成 v2 token
  4. `UPDATE scan_login SET status=2, user_id=?, token=?, extra=? WHERE code=?`
  5. 返回漂亮的"注册成功"HTML页面（手机端显示）
- 如果是普通登录流程：保持原有行为不变

### `main.py` — 注册蓝图

```python
from app.scan_register import scan_reg_bp
app.register_blueprint(scan_reg_bp)
```

## 数据库变更

```sql
ALTER TABLE scan_login ADD COLUMN extra VARCHAR(500) DEFAULT NULL AFTER token;
```

extra 存储 JSON: `{"nickname": "微信昵称", "headimgurl": "头像URL"}`

## 前端 Register.vue

**路径**: `/opt/ttdazi/frontend/src/views/Register.vue`

### Tab切换
- **微信注册** (默认tab) — 检测微信浏览器/PC两套UI
- **手机注册** — 原手机号+密码注册

### 微信注册UI

**微信浏览器内**: 绿色"微信一键注册"按钮 → `window.location.href = '/api/wechat/login'`
- 直接走现有OAuth流程 → 自动创建用户 → 跳转首页/bind-phone

**PC端**: 二维码扫码
1. 调用 `POST /api/register/wx/create` 获取code+code_url
2. 用 `qrcode` 包渲染二维码 (`QRCode.toDataURL`)
3. 每1.5s轮询 `GET /api/register/wx/status?code=XXX`
4. 检测到 status=2 + token → localStorage存token → 获取用户信息 → 跳转首页

```javascript
async function createQr() {
  const r = await api.post('/register/wx/create')
  currentCode = r.code
  qrImg.value = await QRCode.toDataURL(r.code_url, { width: 180, margin: 1 })
  startPoll(r.code)
}

function startPoll(code) {
  timer = setInterval(async () => {
    const r = await api.get('/register/wx/status?code=' + code)
    if (r.status === 2 && r.token) {
      clearInterval(timer)
      localStorage.setItem('token', r.token)
      // 获取用户信息并跳转
    } else if (r.status === -1) {
      // 提示过期
    }
  }, 1500)
}
```

## 与扫码登录的对比

| 特性 | 扫码登录 (scan_login.py) | 扫码注册 (scan_register.py) |
|:-----|:------------------------:|:---------------------------:|
| QR URL | `/#/scan-confirm?code=XXX` | `/api/wechat/qr-register?code=XXX` |
| 手机端操作 | 需已登录用户手动确认 | 微信扫码→OAuth授权→自动创建用户 |
| PC端交互 | 轮询到status=2+token → 自动登录 | 轮询到status=2+token → 自动登录 |
| 用户创建 | 否（已有用户） | 是（自动注册） |
| 二维码有效期 | 300秒 | 600秒 |

## 关键陷阱

### 1. 微信OAuth只能在微信浏览器内打开
PC浏览器直接访问OAuth URL会显示"Oops! Something went wrong"，因此：
- Register.vue 检测 `navigator.userAgent` 中的 `MicroMessenger`
- 微信浏览器内显示按钮跳转，PC端显示二维码扫码
- 二维码路径 `/api/wechat/qr-register` 被微信扫码后，在微信内置浏览器打开，然后302到OAuth

### 2. state参数传递session code
微信OAuth的state参数用于传递session code，格式 `reg_{code}`。回调中提取code：
```python
is_register = state.startswith('reg_')
scan_code = state[4:] if is_register else ''
```

### 3. scan_login表复用
注册和登录共用 `scan_login` 表，通过 `code` 字段区分会话。注册流程：
- PC create → INSERT (status=0)
- 微信回调 → UPDATE (status=2, user_id, token, extra)
- PC轮询到 status=2 → 读token → 登录

### 4. 轮询定时器清理
切换Tab或组件卸载时必须清除定时器：
```javascript
onUnmounted(() => { if (timer) clearInterval(timer) })
function switchTab(tab) {
  if (timer) { clearInterval(timer); timer = null }
  mode.value = tab
}
```

### 5. 注册成功的手机端页面
callback中返回内联HTML页面（非重定向），手机用户看到：
- ✅ 注册成功！
- 微信账号已自动注册
- 请返回电脑端查看
- [进入首页] 按钮

## 相关文件清单

| 文件 | 角色 |
|:-----|:-----|
| `/opt/ttdazi/backend/app/scan_register.py` | 扫码注册会话API |
| `/opt/ttdazi/backend/app/wechat_login.py` | 微信OAuth + 注册回调 |
| `/opt/ttdazi/backend/main.py` | 蓝图注册 |
| `/opt/ttdazi/frontend/src/views/Register.vue` | 注册页面（新增微信注册Tab） |
| `scan_login` 表 (huizhiyun库) | 会话存储 |
