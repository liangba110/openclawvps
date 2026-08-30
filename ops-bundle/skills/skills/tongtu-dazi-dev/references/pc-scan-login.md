# PC 扫码登录（方案B — 自建扫码登录系统）

## 适用场景

PC端用户使用手机微信扫码完成登录，适合不在微信浏览器内的桌面环境。

## 架构

```
PC端（未登录）                   手机端（已微信登录）
    │                                │
    │ POST /api/login/scan/create     │
    │ ← {code, code_url}              │
    │                                │
    │ 渲染二维码（code_url）          │
    │ ┌──────────┐                   │
    │ │  ██ █  ██ │──扫码──→         │
    │ │  █  ██ █  │                   │
    │ │  ██ █  ██ │                   │
    │ └──────────┘                   │
    │                                │ 打开 /#/scan-confirm?code=X
    │                                │ → 检测手机已登录
    │                                │ → 显示"确认登录"按钮
    │                                │ → POST /api/login/scan/confirm
    │ 轮询 GET /api/login/scan/status │ ← {status:2, token:...}
    │ ← 收到token → 保存 → 跳转首页   │
```

## 数据库

```sql
CREATE TABLE scan_login (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    status TINYINT DEFAULT 0 COMMENT '0=pending, 1=scanned, 2=confirmed, -1=expired',
    user_id INT DEFAULT NULL,
    token VARCHAR(500) DEFAULT NULL COMMENT 'PC端登录用的token',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    INDEX idx_code (code),
    INDEX idx_expires (expires_at)
);
```

## API 端点

| 端点 | 方法 | 认证 | 功能 |
|------|------|------|------|
| `/api/login/scan/create` | POST | 无 | 创建扫码会话，返回 `{code, code_url, expires_in}` |
| `/api/login/scan/status` | GET | 无 | 轮询状态，返回 `{status, token?}`。status: 0=待扫码, 1=已扫码, 2=已确认, -1=过期 |
| `/api/login/scan/confirm` | POST | `@login_required` | 手机确认登录。需传 `{code}`，返回PC端 `{token, refresh_token}` |

## 后端实现（`backend/app/scan_login.py`）

```python
# 关键逻辑
CODE_TTL = 300  # 5分钟有效
QR_URL = 'https://dazi.openai2000.cn/#/scan-confirm'

def _gen_code():
    """生成唯一16位code"""
    raw = str(time.time()) + ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    return hashlib.md5(raw.encode()).hexdigest()[:16]

# create: 清理过期 + 插入新code
# status: 查询状态 + 超时检查
# confirm: SELECT FOR UPDATE + 生成gen_token + gen_refresh_token
```

### 确认端点的关键操作
1. `SELECT FOR UPDATE` 行锁，防止并发确认
2. 检查 `expires_at` 是否过期
3. 标记 `status=2`，保存 `user_id` 和 `token`
4. 使用 `gen_token(user_id, device_id)` + `gen_refresh_token(user_id, device_id)`

### 注册蓝图
```python
# main.py
from app.scan_login import scan_bp
app.register_blueprint(scan_bp)  # url_prefix='/api/login'
```

## 前端实现

### Login.vue — 扫码Tab

- 三个 Tab：微信登录 / 扫码登录 / 账号密码
- 点击「扫码登录」Tab 或「刷新二维码」调用 `createQrCode()`
- `createQrCode()` → `POST /api/login/scan/create` → 获取 `code_url`
- 使用 `QRCode` 库渲染二维码（CDN: `qrcodejs@1.0.0/qrcode.min.js`）
- 降级：`https://api.qrserver.com/v1/create-qr-code/` 生成图片
- 每1.5秒轮询 `GET /api/login/scan/status?code=XXX`
- 检测 `status=2` → 保存 `token` → 调 `/user/profile` 获取用户信息 → 跳转首页
- `onUnmounted` 清理轮询定时器

关键代码：
```javascript
async function createQrCode() {
  const r = await api.post('/login/scan/create')
  if (r && r.code && r.code_url) {
    scanCode = r.code
    new QRCode(container, { text: r.code_url, width: 180, height: 180 })
    startPolling(r.code)
  }
}

function startPolling(code) {
  scanInterval = setInterval(async () => {
    const r = await api.get('/login/scan/status?code=' + code)
    if (r.status === 2 && r.token) {
      clearInterval(scanInterval)
      localStorage.setItem('token', r.token)
      // fetch user profile and save
      const userData = await api.get('/user/profile')
      localStorage.setItem('user', JSON.stringify(userData))
      router.push('/')
    } else if (r.status === -1) {
      clearInterval(scanInterval)
      // show expired message
    }
  }, 1500)
}
```

### ScanConfirm.vue — 手机确认页

路由：`/scan-confirm?code=XXX`

流程：
1. 从 `route.query.code` 获取code
2. 检查手机端 `localStorage.getItem('token')` 是否已登录
3. 已登录 → 显示当前昵称 + "确认登录"按钮
4. 未登录 → 显示"先去登录"按钮
5. 点确认 → `POST /api/login/scan/confirm` → 显示"已确认，PC端即将自动登录"

## URL 编码

二维码内容（`code_url`）：`https://dazi.openai2000.cn/#/scan-confirm?code=16位code`

Hash 模式路由无需 `?` 前的查询参数，所有参数在 `#` 后的 hash 中。

## 注意事项

- Code 有效期 5 分钟，超时自动清理（`DELETE WHERE expires_at < NOW()`）
- `create` 端点在每次创建前清理过期记录（避免表无限增长）
- 确认使用 `FOR UPDATE` 行锁防止竞态
- PC 端轮询 1.5 秒间隔，不要过快避免服务器压力
- 用户信息在 PC 端获取（`/user/profile`），手机确认时不传递用户数据给 PC
- 手机确认页检测 `localStorage` 中的 token，如果用户未登录跳转到登录页
- 新用户注册时，可通过扫码登录流程先创建账号再绑手机
