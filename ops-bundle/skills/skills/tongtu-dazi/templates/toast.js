/**
 * toast.js — 项目标准 toast 实现
 * 位置: frontend/src/utils/toast.js
 */
let toastEl = null
let toastTimer = null

function removeToast() {
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
  return new Promise((resolve) => {
    let msg = ''
    if (input) {
      msg = typeof input === 'object' ? (input.message ?? '') : String(input)
    }
    msg = msg.trim() || '操作完成'
    console.log('[toast] 显示:', msg)
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
      toastTimer = setTimeout(() => {
        removeToast()
        resolve()
      }, duration)
    }, 20)
  })
}

export default safeToast
