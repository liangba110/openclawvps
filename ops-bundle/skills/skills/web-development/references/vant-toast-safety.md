# Vant Toast Safety — Preventing Blank Toasts

## Problem

`showToast(e.message)` in catch blocks can produce a **blank toast** when the
error object has an empty message string (`""`). This happens silently — no
console error, no visible text, just a blank toast bubble.

## Root Causes

### 1. Missing import (most common)

When replacing `showToast` with a `safeToast` wrapper, it's easy to miss a call
site. The Vue SFC compiler won't warn about `showToast` being used without being
imported — Vite just tree-shakes the unused import silently, leaving the runtime
call **undefined**. This causes a JS error that propagates to `onErrorCaptured`.

**Fix:** After migration, grep the compiled dist JS for remaining `showToast(` hits:
```bash
grep -r "showToast(" dist/assets/*.js
```
Zero hits confirms the migration is complete.

### 2. Vant 4 toast singleton race condition (critical)

In Vant 4, `showToast` / `showLoadingToast` / `closeToast` share a **singleton
toast manager**. Calling `closeToast()` and immediately calling `showToast()` or
`safeToast()` in the next synchronous line causes a race condition:

```js
catch (e) {
  closeToast()          // marks the loading toast for removal (async)
  showToast(errMsg)     // creates new toast, but closeToast's async
}                       // cleanup fires after, removing the new toast too
```

The close operation is asynchronous — it schedules DOM removal with exit
animations. Any new toast created in between gets destroyed when the removal
completes. Visually, the loading toast's white overlay stays in the DOM while
the custom toast renders on top, creating a blank/white box effect.

**⚠️ DO NOT use `setTimeout(..., 100)` as a fix.** This is unreliable because:
- Vant's exit animation duration varies across devices and network conditions
- Fast API responses (<100ms) mean the timer fires before the DOM is cleared
- Slow network means the timer fires after the DOM is already gone (wasted delay)

**Proven failures (in order of evolution):**
1. `setTimeout(60ms)` — too short, Vant animation incomplete
2. `setTimeout(100ms)` — still unreliable on fast mobile
3. DOM polling (`querySelector('.van-toast')` × 50ms × 30 attempts) — timing-dependent, fragile
4. `querySelectorAll('.van-toast').forEach(el => el.remove())` — works but hacky, still calls closeToast first
5. **Instance control** (`loadingToast.close()` + `requestAnimationFrame`) — correct but 200ms setTimeout variant also fragile

### ✅ The Best Fix: Remove Vant Loading Entirely

For login forms, confirmation dialogs, and any flow where a loading indicator is needed
**only** during the API call, the simplest and most robust approach is to skip Vant's
`showLoadingToast` entirely and use the **button's disabled state** as the loading indicator:

```js
// ✅ BEST: No Vant loading — zero race condition risk
async function doLogin() {
  loading.value = true                 // button shows "登录中..."
  try {
    const res = await api.post('/user/login', { phone, password })
    safeToast('登录成功')
  } catch (e) {
    safeToast(e.message || '登录失败')
  } finally {
    loading.value = false              // button shows "登 录"
  }
}
```

Template:
```html
<button :disabled="loading">{{ loading ? '登录中...' : '登 录' }}</button>
```

**Why this wins:**
- Zero third-party overlay — no DOM to clean up, no animation to wait for
- User sees the button state change instantly
- `safeToast` (custom DOM-based) fires immediately without fighting Vant's singleton
- Works the same on fast and slow connections — no timing dependency

### Instance Control (fallback for non-form flows)

If Vant loading is unavoidable (e.g., full-page overlay during data import), use instance control:

`showLoadingToast()` **returns a toast instance** with a `.close()` method.
Use instance control instead of the global `closeToast()`:

```js
// ✅ CORRECT: Instance-based control
let loadingToast = null

async function doLogin() {
  loadingToast = showLoadingToast('登录中...')
  try {
    const res = await api.post('/user/login', { phone, password })
    // ...
  } catch (e) {
    await closeLoadingAndToast(e.message || '登录失败')
    return
  }
  await closeLoadingAndToast('登录成功')
}

const closeLoadingAndToast = async (text) => {
  if (loadingToast) {
    loadingToast.close()    // Precise, no global singleton interference
    loadingToast = null
  }
  // One frame wait ensures the DOM is fully cleared
  await new Promise(resolve => requestAnimationFrame(resolve))
  safeToast(text || '操作完成')
}
```

**Why this works:**
- `instance.close()` targets the exact toast node, not the global singleton
- The `requestAnimationFrame` wait ensures the browser has flushed DOM changes
- No guesswork about animation duration — the frame boundary is deterministic

### 3. Empty error message from API

The `||` operator alone is NOT sufficient when the source is a third-party
library error or an API response with an empty `msg` field. Always use a
safe wrapper.

## Solution: Custom DOM-based Toast (Recommended)

Bypasses Vant's singleton entirely. Creates a native DOM element:

```js
// utils/toast.js — fully independent, no Vant dependency
let toastEl = null
let toastTimer = null

export function safeToast(msg, duration = 2000) {
  const text = (msg && String(msg).trim()) || '操作完成'

  if (toastEl) { clearTimeout(toastTimer); toastEl.remove(); toastEl = null }

  toastEl = document.createElement('div')
  toastEl.textContent = text
  Object.assign(toastEl.style, {
    position: 'fixed', top: '50%', left: '50%',
    transform: 'translate(-50%, -50%)', zIndex: '9999',
    background: 'rgba(0,0,0,0.78)', color: '#fff',
    fontSize: '14px', padding: '12px 24px', borderRadius: '10px',
    maxWidth: '80%', textAlign: 'center', lineHeight: '1.5',
    wordBreak: 'break-word', pointerEvents: 'none',
    transition: 'opacity 0.2s',
  })
  document.body.appendChild(toastEl)

  toastTimer = setTimeout(() => {
    if (toastEl) { toastEl.style.opacity = '0'
      setTimeout(() => { if (toastEl) { toastEl.remove(); toastEl = null } }, 200) }
  }, duration)
}

export function closeToast() {
  if (toastEl) { clearTimeout(toastTimer); toastEl.remove(); toastEl = null }
}

export default safeToast
```

## Simpler Solution: safeToast Wrapper (if Vant's singleton is not used for loading)

If the page doesn't use Vant's loading toast, a simple wrapper suffices:

```js
import { showToast } from 'vant'

export function safeToast(msg) {
  const text = (msg && String(msg).trim()) || '操作完成'
  showToast(text)
}
```

**But** if the page uses both a loading toast and a result toast, use **instance control** (`loadingToast.close()` → `requestAnimationFrame`) as shown in Root Cause #2 above. The DOM-based approach alone isn't sufficient when Vant's singleton still holds a reference to the loading node.

## API Interceptor Safety

The Axios interceptor should always produce a non-empty error message:

```js
api.interceptors.response.use(
  res => {
    if (res.data.code !== 0) {
      const errMsg = res.data.msg || '请求失败'
      return Promise.reject(new Error(errMsg))
    }
    return res.data.data
  },
  err => {
    const httpMsg = err.message || '网络异常'
    return Promise.reject(new Error(httpMsg))
  }
)
```

## Audit Checklist

When fixing blank toasts across a codebase, **prefer systematic "一次性完整修复"** (one-shot complete fix) — search all affected files and fix in a single pass rather than iterating:

1. Replace `showToast` from `vant` with DOM-based `safeToast` wrapper in every view
2. Fix the API interceptor to never propagate empty messages
3. Add `console.error` logging before `safeToast` for debugging
4. Handle `e?.message || e?.msg || 'default'` to catch both Error objects and API response shapes
5. **Verify compiled output**: After rebuilding, grep the dist JS:
   `grep -r "showToast(" dist/assets/*.js` — zero hits confirms migration complete
6. **Test with loading toast**: If the page has a loading toast (`showLoadingToast`),
   the close + show sequence triggers the Vant singleton race condition.
   **Preferred: remove Vant loading entirely** and use button disabled + text toggle.
   **Fallback**: instance control: `loadingToast = showLoadingToast()` → `loadingToast.close()` → `requestAnimationFrame` → `safeToast()`.

## The Definitive safeToast (Promise-based, self-mutual-exclusion)

This version is the final form after 7 iterations. It returns a Promise, internally uses 20ms delay to ensure DOM cleanup, and prevents multiple simultaneous toasts:

```js
let toastEl = null
let toastTimer = null

function removeToast() {
  if (toastTimer) { clearTimeout(toastTimer); toastTimer = null }
  if (toastEl && document.body.contains(toastEl)) {
    document.body.removeChild(toastEl)
    toastEl = null
  }
}

export function safeToast(input, duration = 2000) {
  return new Promise((resolve) => {
    let msg = ''
    if (input) {
      msg = typeof input === 'object' ? (input.message ?? '') : String(input)
    }
    msg = msg.trim() || '操作完成'
    // Clean existing first
    removeToast()
    setTimeout(() => {
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
      toastTimer = setTimeout(() => { removeToast(); resolve() }, duration)
    }, 20)
  })
}

export default safeToast
```

Key properties:
- `Promise` return allows `await safeToast(...)` for sequential control
- 20ms setTimeout ensures previous DOM node is fully removed before creating new one
- `document.body.contains(toastEl)` is more reliable than `parentNode` check
- Nullish coalescing `??` for object input avoids empty-string trap
