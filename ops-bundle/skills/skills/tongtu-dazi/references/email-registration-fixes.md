# 邮箱注册流程排查与修复记录

## 完整流程

```
Step 1: 输入邮箱名 + 选择域名 → emailName + '@' + emailDomain
Step 2: 点击"获取验证码" → POST /api/user/send-email-code (SMTP真实发送)
Step 3: 查收邮箱 → 输入6位验证码
Step 4: 设置昵称 + 密码(6位含数字)
Step 5: 勾选用户协议 → 点击注册
Step 6: POST /api/user/register-by-email → 成功后自动登录跳首页
```

## 已修复的 Bug

### 1. 邮箱拼接缺少 `@`
```javascript
// ❌ 错 — 后端收到 usernameqq.com
const email = computed(() => emailName.value + emailDomain.value)
// ✅ 对
const email = computed(() => emailName.value + '@' + emailDomain.value)
```

### 2. 验证码获取流程错误
**症状：** 点击"获取验证码"弹出微信二维码（要求关注公众号），而不是直接发送邮箱验证码。

**原因：** `sendCode()` 中打开了 QR 弹窗（这是 FollowRegister.vue 公众号注册的流程，被错误复制到邮箱注册页）。

**修复：** 改为直接调 `POST /api/user/send-email-code`，删除冗余 QR 弹窗/变量/模板。

### 3. `send-code-btn` 禁用条件
改前：`:disabled="sending || countdown > 0 || !emailName.value"` — 邮箱为空时按钮灰色不可点
改后：`:disabled="sending || countdown > 0"` — 始终可点，邮箱为空在 `sendCode()` 内弹 `safeToast`

### 4. 注册按钮禁用条件
改前：`:disabled="loading || !agreed || !emailName.value || !code.value"` — 多项条件任意不满足就灰色
改后：`:disabled="loading"` — 始终可点，函数内逐项校验弹 Toast

### 5. 密码验证太严格（导致 500 崩溃）
**根因：** `utils.py` 中 `PWD_MIN_LEN = 16` + 要求大写/小写/特殊字符，用户注册时填6位就通过前端验证但后端拒绝。

**修复：**
```python
PWD_MIN_LEN = 6  # 16 → 6

def validate_password_strength(password):
    if len(password) < PWD_MIN_LEN:
        return False, f'密码长度不能少于{PWD_MIN_LEN}位'
    if not any(c.isdigit() for c in password):
        return False, '密码必须包含数字'
    return True, ''
```

**注意：** 改完 `PWD_MIN_LEN` 后必须清 `__pycache__` + 重启 gunicorn，否则旧 bytecode 仍在运行。
```bash
find /opt/ttdazi/backend -name "__pycache__" -exec rm -rf {} + 2>/dev/null
sudo systemctl restart ttdazi
# 验证：curl -s http://82.157.202.24/api/health
# 如果还报旧错误 → 检查日志是否还有旧 import 错误
# 如果 `sudo journalctl -u ttdazi | grep "register_by_email\|utils"` 显示旧代码 → 
#   可能需要在系统重启前先 kill 旧 worker: sudo pkill -f gunicorn
```

### ⚠️ 2026-07-06 新增：cache 残留导致旧密码验证仍在运行

**现象：** 即使 `PWD_MIN_LEN` 已改为 6，`journalctl` 日志仍然报 `密码长度不能少于16位`。

**根因：** Gunicorn 2 个 worker 都加载了旧的 `__pycache__` bytecode。删除缓存后直接 `restart` 有时 worker 会从 fork 缓存中复用旧内存。

**100% 的方案：**
```bash
find /opt/ttdazi/backend -name "__pycache__" -exec rm -rf {} + 2>/dev/null
sudo pkill -f gunicorn           # 强行杀所有 worker
sleep 3
sudo systemctl restart ttdazi    # systemd 重新拉起
sleep 4
curl -s http://82.157.202.24/api/health  # 验证
# 测试密码: {"password":"test123"} 应该返回验证码错误 而不是 密码长度错误
```

### 6. SMTP 发送邮箱验证
QQ邮箱 SMTP 会校验收件人是否存在，不存在时返回 550。不影响正常用户（用户会用自己真实邮箱）。

`devCode` 在 API 返回 `_dev_code` 字段时在前端显示，方便开发测试。

## 按钮交互模式（适用所有表单页面）

所有表单提交按钮统一模式：
```vue
<button :disabled="loading" @click="doSubmit">{{ loading ? '提交中...' : '注册' }}</button>
```

函数内逐项校验：
```javascript
async function doSubmit() {
  if (!field1) { safeToast('请填写字段1'); return }
  if (!field2) { safeToast('请填写字段2'); return }
  loading.value = true
  try {
    await api.post('/submit', data)
    safeToast('成功 🎉')
  } catch(e) {
    safeToast(e?.message || '操作失败')
  } finally {
    loading.value = false
  }
}
```
