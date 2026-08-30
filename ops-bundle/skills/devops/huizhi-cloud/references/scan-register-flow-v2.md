# 扫码注册流程设计（两步授权+绑定）

## 流程

```
PC端                          手机端
┌─────────────────┐           ┌─────────────────┐
│ ① 扫码Tab → 二维码│           │                 │
│ ② 轮询等待扫码   │           │                 │
│                 │ ←──扫码── │ ③ 打开授权页     │
│                 │           │ ④ 显示头像/昵称  │
│                 │           │ ⑤ 用户点"确认授权"│
│ ⑥ 检测status=1  │  ←授权─  │ ⑥ API: authorize │
│   显示绑定表单   │           │    返回成功      │
│   昵称已展示     │           │    显示"请在电脑  │
│ ⑦ 用户填手机+密码│           │    端继续注册"   │
│ ⑧ 点"完成注册"  │           │                 │
│    API: bind    │           │                 │
│ ⑨ 自动登录成功   │           │                 │
└─────────────────┘           └─────────────────┘
```

## API 设计

| API | 方法 | 调用方 | 说明 |
|:----|:----:|:------|:------|
| `/api/register/scan/create` | POST | PC端 | 创建二维码会话，status=0 |
| `/api/register/scan/status` | GET | PC端 | 轮询状态（返回status + nickname） |
| `/api/register/scan/authorize` | POST | 手机端 | 授权，传nickname，status→1 |
| `/api/register/scan/bind` | POST | PC端 | 绑定手机+密码完成注册，status→2 |

## 关键实现细节

### 数据库表 `scan_login`
```
id | code | status | user_id | token | extra | created_at | expires_at
```
- `extra` 字段: JSON 字符串，存授权昵称 `{"nickname": "微信用户"}`
- `status`: 0=待扫码, 1=已扫码(待绑定), 2=已完成
- `extra` 列需手动 ALTER TABLE: `ALTER TABLE scan_login ADD COLUMN extra VARCHAR(500) DEFAULT NULL AFTER token`

### 前端 Register.vue
- 两个Tab: 扫码注册 / 手机注册
- 扫码Tab下两个状态:
  - `scanNickname === ''` → 显示二维码
  - `scanNickname !== ''` → 显示绑定表单（手机+密码+完成按钮）
- 定时器管理: `switchToScan()` / `switchToForm()` 函数确保切换Tab时清除轮询

### 前端 ScanRegister.vue（手机端）
- 扫码后打开，显示头像（蓝色渐变圆形占位）+ 昵称
- 用户点击「确认授权」按钮才调用 `/api/register/scan/authorize`
- 成功后显示「请在电脑端继续完成注册」

### 绑定表单（PC端）
```javascript
async function doBind() {
  // 验证手机号11位、密码>=6位
  binding.value = true
  try {
    const r = await api.post('/register/scan/bind', {
      code: currentCode,
      phone: bindPhone.value,
      password: bindPassword.value
    })
    if (r.code === 0 && r.data.token) {
      localStorage.setItem('token', r.data.token)
      router.push('/dashboard')
    } else {
      alert(r.msg || '注册失败，请重试')
    }
  } catch (e) {
    alert('网络错误，请重试')
  }
  binding.value = false  // 不要用 finally，用显式赋值
}
```

## 常见问题

### catch/finally 兼容性
- `catch {}`（无参）在某些 Vite/esbuild 构建中可能不执行
- `catch { ... } finally { binding.value = false }` — finally 可能被跳过
- **修复方案:** 始终用 `catch(e) { ... }` 显式参数，`binding.value = false` 放在 catch 块外

### 绑定按钮卡住
- 如果 `binding.value` 永远不变成 false，按钮永久显示"注册中..."
- 原因可能是 API 异常 + catch 块的组合执行问题
- **修复方案:** 使用 `alert()` 替代 `showToast()` 以便用户看到真实错误信息

### 定时器管理
- `createQr()` 中保存 `currentCode`，用于后续绑定
- 切换Tab时必须 `clearInterval(timer)` 并 `timer = null`
- 扫码成功（status=1）后也要 `clearInterval(timer)`
