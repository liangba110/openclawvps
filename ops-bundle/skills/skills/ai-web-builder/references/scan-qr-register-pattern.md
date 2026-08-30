# 扫码注册（三阶段模式：手机授权 → PC绑定 → 自动登录）

## 原理

复用 `scan_login` 表，PC端生成二维码 → 手机扫码授权（传递昵称）→ PC端检测到扫码后显示绑定表单 → 用户填写手机号+密码 → 完成注册并自动登录。

## 完整流程

```
PC端                               手机端
┌─────────────────┐               ┌─────────────────┐
│ POST /scan/create│               │                 │
│ → 显示二维码     │               │                 │
│ 轮询 /scan/status│               │                 │
│ (status=0)       │ ←──扫码────  │ 打开 /scan-register │
│                  │               │ 自动生成昵称     │
│                  │               │ POST /scan/authorize│
│ 轮询到 status=1  │  ←─────────  │ → status=1      │
│ 停止轮询         │               │ 显示"授权成功"   │
│ 显示绑定表单     │               │ "请在电脑端继续" │
│ 👤 微信昵称       │               │                 │
│ 📱 手机号输入框   │               │                 │
│ 🔑 密码输入框     │               │                 │
│ ▶ 完成注册       │               │                 │
│ POST /scan/bind  │               │                 │
│ → 创建用户+token │               │                 │
│ → 自动登录Dashboard│              │                 │
└─────────────────┘               └─────────────────┘
```

## 后端 API

| 端点 | 方法 | 说明 | 请求体 | 返回 |
|:----|:----:|:------|:-------|:-----|
| `/api/register/scan/create` | POST | 创建二维码 | 无 | `{code, code_url, expires_in}` |
| `/api/register/scan/status` | GET | 轮询状态 | `?code=XXX` | `{status, nickname?, token?}` |
| `/api/register/scan/authorize` | POST | 手机授权 | `{code, nickname}` | `{nickname}` |
| `/api/register/scan/bind` | POST | PC绑定 | `{code, phone, password}` | `{token}` |

## status 状态码

| 值 | 含义 | PC端行为 |
|:--:|:-----|:---------|
| 0 | 待扫码 | 显示二维码 |
| 1 | 已扫码（手机已授权） | **停止轮询**，显示绑定表单（昵称+手机+密码） |
| 2 | 已注册 | 自动登录，跳转 /dashboard |
| -1 | 已过期 | 提示刷新二维码 |

## 关键实现细节

### 后端 (`backend/app/scan_register.py`)

```python
# blueprint: scan_reg_bp, url_prefix='/api/register'
# 二维码有效期: 600 秒
# 依赖: utils.gen_token, utils.check_phone_exists, utils.make_password

# authorize端点 — 手机扫码后调用，设置status=1并存储nickname到extra字段
@scan_reg_bp.route('/scan/authorize', methods=['POST'])
def scan_reg_authorize():
    data = request.get_json()
    code, nickname = data.get('code'), data.get('nickname', '微信用户')
    import json
    extra = json.dumps({'nickname': nickname})
    cur.execute("UPDATE scan_login SET status=1, extra=%s WHERE id=%s", (extra, row['id']))

# bind端点 — PC端填写手机+密码后调用，创建用户并返回token
@scan_reg_bp.route('/scan/bind', methods=['POST'])
def scan_reg_bind():
    data = request.get_json()
    code, phone, password = data.get('code'), data.get('phone'), data.get('password')
    # 验证: status>=1 (已扫码), 手机号唯一, 密码>=6位
    hashed = make_password(password)
    cur.execute("INSERT INTO users (phone, username, password) VALUES (%s, %s, %s)",
                (phone, nickname, hashed))
    user_id = cur.lastrowid; token = gen_token(user_id)
    cur.execute("UPDATE scan_login SET status=2, user_id=%s, token=%s WHERE id=%s",
                (user_id, token, row['id']))
```

### 数据库

`scan_login` 表需有 `extra VARCHAR(500)` 字段（存二维码会话的附加信息JSON）。

```sql
ALTER TABLE scan_login ADD COLUMN extra VARCHAR(500) DEFAULT NULL AFTER token;
```

extra 格式: `{"nickname": "微信用户"}`

### 前端 Register.vue（PC端）

- 扫码Tab：生成二维码 → 轮询 GET /scan/status
- 检测到 status=1 → **clearInterval 停止轮询**，切换为绑定表单
- 绑定表单展示：
  - "✅ 手机已扫码授权"
  - "👤 {昵称}"
  - 手机号输入框 + 密码输入框
  - "完成注册" 按钮 → POST /scan/bind
- 绑定成功后直接 localStorage.setItem('token') → router.push('/dashboard')

### 前端 ScanRegister.vue（手机端）

- 显示用户微信头像（模拟）和昵称，**需用户点击「确认授权」按钮**
- 点击后调用 `POST /api/register/scan/authorize` 传递 code + nickname
- 成功后显示 "授权成功，请在电脑端继续完成注册"

```javascript
const nickname = ref('微信用户')  // 从参数获取
const authorized = ref(false)

async function doAuthorize() {
  await api.post('/register/scan/authorize', { code, nickname })
  authorized.value = true
}
```

- **不自动生成昵称**，昵称从页面参数或用户微信信息获取
- **不自动注册**，需用户明确点击确认
- **不生成手机号和密码，不创建用户** — 用户信息在PC端填写

## 与扫码登录的差异

| 特性 | 扫码登录 | 扫码注册 |
|:----|:--------|:--------|
| 二维码有效期 | 300秒 | 600秒 |
| 手机端操作 | 用户手动点击确认 | 自动授权，无需操作 |
| PC端交互 | 自动登录 | **显示绑定表单，需用户填手机+密码** |
| 后端创建用户 | 否 | 是（bind端点） |
| 依赖函数 | gen_token | gen_token + make_password + check_phone_exists |
| 表字段依赖 | 基础字段 | 需 **extra** 字段存nickname |
