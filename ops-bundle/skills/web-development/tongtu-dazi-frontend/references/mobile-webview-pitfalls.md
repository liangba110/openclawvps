# 移动端 WebView 陷阱集

## 1. safeConfirm 替代原生 confirm()

**现象**: 手机 WebView 中 `confirm('确认支付？')` 不出弹窗或被拦截

**修复**: 永远用自定义 `safeConfirm` 替代原生 `confirm/alert`

```js
import safeConfirm from '@/utils/confirm'

// ❌ 原生（手机端不可靠）
if (confirm('确定通过？')) { ... }

// ✅ safeConfirm（Promise，无Vant依赖）
const ok = await safeConfirm({ title: '确认', message: '确定通过该陪玩师？' })
if (!ok) return
// 用户确认后继续执行
```

> Vant 的 `showConfirmDialog` 也不再使用——`safeConfirm` 是最终方案。

---

## 2. navigator.clipboard 需要 HTTPS

**现象**: `TypeError: Cannot read properties of undefined (reading 'writeText')`
HTTP 站点 `navigator.clipboard` 为 undefined

**修复**: 加 fallback
```js
function copyLink(url) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => safeToast('已复制'))
  } else {
    // HTTP fallback: textarea + execCommand
    const ta = document.createElement('textarea')
    ta.value = url
    ta.style.position = 'fixed'; ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select(); document.execCommand('copy')
    document.body.removeChild(ta)
    safeToast('已复制')
  }
}
```

---

## 3. fixed 定位与底部导航栏 z-index 冲突

**现象**: 详情页底部下单栏被App全局导航栏遮挡

**层级规则**（由低到高）:
```
z-index: 900  →  详情页下单栏 (bottom: 64px)
z-index: 1000  →  App 底部导航栏 (bottom: 0)
z-index: 9999  →  Toast/Modal 遮罩
```

**关键**: 下单栏必须 `bottom: 64px`（导航栏高度），不能 `bottom: 0`。
spacer 需要 `height: 140px` 避免内容被两层固定栏遮挡。

```css
/* 详情页底部下单栏 — 在导航栏上方 */
.bottom-bar {
  position: fixed; bottom: 64px; left: 0; right: 0;
  z-index: 900;
  background: #fff; border-top: 2px solid #667eea;
}
.bottom-spacer { height: 140px; }
```

---

## 4. 底部栏移出 v-if="info" 作用域

**现象**: 数据加载期间底部栏不显示，数据加完后突然出现→布局跳动

**修复**: 底部栏不放在 `v-if="info"` 的 detail-page div 内，独立放在外层
```html
<!-- ✅ 底部栏独立渲染 -->
<div class="detail-page" v-if="info">...</div>
<div v-if="info" class="bottom-bar">❤️收藏 💬聊一聊 立即预约</div>
<div v-else class="skeleton-page">...</div>
```
spacer 放在 detail-page 内部，骨架屏不需要 spacer。
