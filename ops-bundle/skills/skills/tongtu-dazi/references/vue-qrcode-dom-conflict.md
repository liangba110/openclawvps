# Vue + QRCode 库 DOM 冲突解决

## 问题

Vue 组件中使用 `new QRCode(container, {...})` 时，QRCode 库直接在 DOM 容器中 `appendChild(canvas)` 和 `appendChild(img)`，而 Vue 通过 v-dom 管理同一容器。当 `v-show` 或状态切换触发 Vue 重新渲染时，Vue 的 patch 算法发现子节点不一致 → `insertBefore(null)` 错误 → `onErrorCaptured` 弹出错误 Toast。

## 完整解决模式

### 1. 模板 — 用 v-if 替代 v-show

扫码区域使用 `v-if`，让 Vue 在切换登录方式时完全销毁/重建：

```html
<template>
  <!-- ❌ 错误：v-show 保留 DOM，Vue 与 QRCode 库冲突 -->
  <div v-show="loginMode === 'scan'">
    <div id="qr-container" ref="qrRef"></div>
    <button @click="refresh">刷新二维码</button>
  </div>

  <!-- ✅ 正确：v-if 完全销毁/重建，无 DOM 残留 -->
  <div v-if="loginMode === 'scan'">
    <img v-if="qrImg" :src="qrImg" style="width:180px;height:180px" />
    <button @click="refresh">🔄 刷新二维码</button>
  </div>
</template>
```

### 2. 逻辑 — qrcode 包纯数据流（推荐，替代 qrcodejs2）

```javascript
<script setup>
// ✅ 使用 qrcode 包（纯数据流，不操作 DOM，完美兼容 Vite）
import QRCode from 'qrcode'

const qrImg = ref('')

async function refresh() {
  const r = await api.post('/login/scan/create')
  if (r && r.code_url) {
    // ✅ toDataURL 返回 Promise<string>，无 DOM 操作
    qrImg.value = await QRCode.toDataURL(r.code_url, { width: 180, margin: 1 })
  }
}
</script>
```

### 3. 如果必须用 qrcodejs2（不推荐）

⚠️ `qrcodejs2` 在 Vite 5 + Rollup 打包时，其 UMD 包装代码中的 `_getAndroid()` 函数因模块作用域问题会报 `Cannot read properties of undefined (reading '_android')`，导致整个 vendor chunk 加载失败 → 白屏。**强烈建议迁移到 `qrcode` 包。**

如果无法迁移，必须使用「脱管容器」模式：

```javascript
// ⚠️ 临时容器：创建但不加入页面 DOM
const temp = document.createElement('div')
new QRCode(temp, { text: r.code_url, width: 180, height: 180 })
const canvas = temp.querySelector('canvas')
if (canvas) qrImg.value = canvas.toDataURL('image/png')
```

### 3. 清理定时器

```javascript
let timer = null

function startPoll(code) {
  timer = setInterval(async () => { ... }, 1500)
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
```

## 完整 ScanLogin 组件参考

位置：`/opt/ttdazi/frontend/src/components/ScanLogin.vue`

```vue
<template>
  <div style="margin: 12px 0 8px">
    <p style="font-size:13px;color:#888;margin-bottom:12px;text-align:center">请用手机微信扫一扫登录</p>
    <div style="position:relative;width:180px;height:180px;margin:0 auto 10px">
      <div v-show="qrLoading" style="position:absolute;inset:0;...">生成二维码中...</div>
      <img v-if="qrImg" :src="qrImg" style="width:180px;height:180px;border-radius:8px" />
    </div>
    <p v-if="qrStatus" :style="{fontSize:'13px',color:qrColor,textAlign:'center'}">{{ qrStatus }}</p>
    <p style="font-size:12px;color:#bbb;cursor:pointer;text-align:center" @click="refresh">🔄 刷新二维码</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import QRCode from 'qrcodejs2'

const emit = defineEmits(['loginSuccess'])
const qrLoading = ref(true), qrImg = ref(''), qrStatus = ref(''), qrColor = ref('#999')
let timer = null

async function refresh() {
  qrLoading.value = true; qrImg.value = ''; qrStatus.value = ''
  if (timer) { clearInterval(timer); timer = null }
  try {
    const r = await api.post('/login/scan/create')
    if (r && r.code && r.code_url) {
      const temp = document.createElement('div')
      new QRCode(temp, { text: r.code_url, width: 180, height: 180 })
      const canvas = temp.querySelector('canvas')
      if (canvas) qrImg.value = canvas.toDataURL('image/png')
      qrLoading.value = false; qrStatus.value = '请用手机微信扫码'; qrColor.value = '#07c160'
      startPoll(r.code)
    } else {
      qrLoading.value = false; qrStatus.value = '生成失败'; qrColor.value = '#f44336'
    }
  } catch(e) {
    qrLoading.value = false; qrStatus.value = '网络错误'; qrColor.value = '#f44336'
  }
}

function startPoll(code) {
  timer = setInterval(async () => {
    try {
      const r = await api.get('/login/scan/status?code=' + code)
      if (r.status === 1) { qrStatus.value = '✅ 手机已扫码，等待确认...'; qrColor.value = '#667eea' }
      else if (r.status === 2 && r.token) {
        clearInterval(timer); timer = null
        localStorage.setItem('token', r.token)
        try { const u = await api.get('/user/profile'); if (u?.id) localStorage.setItem('user', JSON.stringify(u)) } catch {}
        qrStatus.value = '✅ 登录成功！'; qrColor.value = '#07c160'
        emit('loginSuccess')
      } else if (r.status === -1) { clearInterval(timer); timer = null; qrStatus.value = '二维码已过期，请刷新'; qrColor.value = '#f44336' }
    } catch { /* quiet */ }
  }, 1500)
}

onMounted(() => refresh())
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>
```

## 关键原理

| 层级 | 机制 | 原因 |
|------|------|------|
| v-if | 销毁/重建 DOM 子树 | 避免 Vue patch 算法与外部 DOM 操作冲突 |
| 脱管容器 | `document.createElement('div')` 不加入 Vue 模板 | QRCode 库的 `appendChild` 在独立 DOM 上操作，不影响 Vue |
| dataURL | `canvas.toDataURL()` → ref → `<img :src>` | 纯数据驱动，Vue 完全控制渲染路径 |
