# Custom DOM Toast — 根治空白弹窗 (Vue + Vant 场景)

## 问题根源

Vant `showToast` 在以下场景会产生空白弹窗（无文本的黑框）：

1. **Vant Loading 与 Toast 时序冲突**: `closeToast()` 是异步销毁 DOM，紧接着 `showToast('xxx')` 时 Vant 内部状态未清理完成，渲染出空白 toast。
2. **后端返回空 `msg`**: API 返回 `{"code": 1, "msg": ""}`，前端 `res.data.msg || '请求失败'` 拿到空字符串。
3. **多次调用堆叠**: 上一个 toast 的 `setTimeout` 未清除，新 toast 创建后旧定时器触发 `removeChild` 导致文字消失。

## 解决方案：纯 DOM 自定义 Toast

完全不依赖 Vant，直接用 `document.createElement('div')` 渲染，100% 可控。

### 1. `utils/toast.js` — 核心 Toast

```js
let toastEl = null
let toastTimer = null

function removeToast() {
  // 清除定时器，防止多弹窗堆叠、文字延迟空白
  if (toastTimer) {
    clearTimeout(toastTimer)
    toastTimer = null
  }
  if (toastEl && document.body.contains(toastEl)) {
    document.body.removeChild(toastEl)
    toastEl = null
  }
}

export function safeToast(input, duration = 2000) {
  let msg = ''
  if (input) {
    // 空值合并，避免message为undefined
    msg = typeof input === 'object' ? (input.message ?? '') : String(input)
  }
  // 双重兜底，杜绝空文本渲染空白框
  msg = msg.trim() || '操作完成'
  console.log('[toast] 显示:', msg)

  // 先清理上一个弹窗
  removeToast()

  const div = document.createElement('div')
  div.textContent = msg
  div.style.cssText = [
    'position: fixed', 'top: 50%', 'left: 50%',
    'transform: translate(-50%, -50%)',
    'z-index: 2147483647', 'background: rgba(0,0,0,0.85)',
    'color: #fff', 'font-size: 15px', 'font-weight: 500',
    'padding: 14px 28px', 'border-radius: 10px',
    'max-width: 80%', 'min-width: 100px',
    'text-align: center', 'word-break: break-word',
    'pointer-events: none'
  ].join(';')
  document.body.appendChild(div)
  toastEl = div
  toastTimer = setTimeout(() => removeToast(), duration)
}

export default safeToast
```

**关键保障:**
- `msg.trim() || '操作完成'` — 无论如何不会出现空白文字
- 创建新 toast 前 `removeToast()` — 永远只有一个弹窗
- `document.body.contains(toastEl)` — 防止在已移除的 DOM 节点上操作

### 2. `api/index.js` — 响应拦截器空值兜底

```js
api.interceptors.response.use(
  res => {
    if (res.data.code !== 0) {
      if (res.data.code === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push('/login')
        safeToast('登录已过期，请重新登录')
      }
      // 三重兜底：后端空msg → '请求失败' → trim → '操作异常'
      const errMsg = (res.data.msg || '请求失败').trim() || '操作异常'
      return Promise.reject(new Error(errMsg))
    }
    return res.data.data
  },
  err => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      router.push('/login')
      safeToast('登录已过期，请重新登录')
    }
    // 网络错误兜底
    const httpMsg = (err.message || '网络异常').trim() || '网络连接失败'
    return Promise.reject(new Error(httpMsg))
  }
)
```

**关键修复:**
- 401 状态码分支之前缺少 toast 提示，现补充
- `(msg || '请求失败').trim() || '操作异常'` — 三重链式兜底

### 3. `delayToast` 模式 — 解决 Vant Loading 时序冲突

当页面同时使用 `showLoadingToast` / `closeToast`（来自 Vant）和自定义 `safeToast` 时，
`closeToast()` 的 DOM 清理是异步的，紧接着调用 `safeToast` 可能导致闪烁或空弹窗。

**解法：60ms 延时弹窗**

```js
// 在 Login.vue 等页面中定义
const delayToast = (text) => {
  setTimeout(() => safeToast(text || '操作完成'), 60)
}

// 所有 closeToast() 后的提示使用 delayToast
closeToast()
delayToast('登录成功')  // ✅ 不是 safeToast('登录成功')
```

**完整 Login.vue 示例:**

```js
async function doLogin() {
  loading.value = true
  const toast = showLoadingToast('登录中...')
  try {
    const res = await api.post('/user/login', { phone, password })
    closeToast()
    delayToast('登录成功')          // ← delayToast
    router.push('/')
  } catch (e) {
    closeToast()
    delayToast(e.message || '登录失败')  // ← delayToast
  } finally {
    loading.value = false
  }
}
```

**规则：** 凡是 `closeToast()` 之后紧跟的 toast 提示，一律用 `delayToast()`。但页面中不涉及 `closeToast()` 的独立 toast（如表单校验失败），直接用 `safeToast()`。

## 迁移检查清单

1. 创建 `utils/toast.js`（上述纯 DOM 版本）
2. 修改 `api/index.js` 响应拦截器（三重兜底 + 401 toast）
3. 排查所有使用 `showLoadingToast` + `closeToast` 的页面：
   - Login.vue
   - EmailRegister.vue
   - FollowRegister.vue
   - Register.vue
   - 其他有 Loading 的页面
4. 在每个页面中添加 `delayToast`，替换 `closeToast()` 后的 `safeToast` 调用
5. 对于不涉及 Loading 的独立校验错误，保持 `safeToast()` 不变

## 相关 Pitfalls

- `webapp-deployment/SKILL.md` → "Vant Loading 关闭后 toast 空白"
- `webapp-deployment/SKILL.md` → "SafeToast wrapper prevents blank Vant toasts"
- `webapp-deployment/SKILL.md` → "Axios interceptor returning raw error objects"
