# qrcodejs2 → qrcode 迁移记录

## 问题

`qrcodejs2` (npm 包 `qrcodejs2@0.0.2`) 使用 UMD 格式，内部包含 `_getAndroid()` 函数检测 `navigator.userAgent`。被 Vite/Rollup 打包时，UMD 包装器的 `factory()` 调用中 `root` 参数为 `undefined`，导致 `_android` 变量未定义，vendor chunk 初始化时抛出：

```
TypeError: Cannot read properties of undefined (reading '_android')
  at vendor-xxx.js:41:93403
```

该异常阻断整个 ES module 链 → Vue 无法挂载 → 白屏。

## 解决方案

### 1. 卸载 qrcodejs2

```bash
npm uninstall qrcodejs2
```

### 2. 安装 qrcode

```bash
npm install qrcode
```

`qrcode@1.5.x` 是纯 ES Module 兼容的包，无 DOM 依赖，支持 Promise API。

### 3. 修改 Login.vue

```javascript
// ❌ 旧 (qrcodejs2)
import QRCode from 'qrcodejs2'
// ...
const temp = document.createElement('div')
new QRCode(temp, { text: url, width: 180, height: 180 })
const canvas = temp.querySelector('canvas')
qrImg.value = canvas.toDataURL('image/png')

// ✅ 新 (qrcode)
import QRCode from 'qrcode'
// ...
qrImg.value = await QRCode.toDataURL(url, { width: 180, margin: 1 })
```

### 4. 验证

```bash
# 构建后 vendor 包大小会从 265.76 kB 变为 269.62 kB
# 确认 vendor 包中不再包含 qrcodejs2 代码
grep -c '_getAndroid\|_android' dist/assets/vendor-*.js
# 应返回 0
```

## API 对照

| 功能 | qrcodejs2 | qrcode |
|------|-----------|--------|
| 生成 data URL | `new QRCode(el, {text, width, height})` + `canvas.toDataURL()` | `QRCode.toDataURL(text, {width, margin})` → Promise |
| 生成 canvas | `new QRCode(el, ...)` 直接操作 DOM | `QRCode.toCanvas(canvasEl, text, opts)` |
| 生成 SVG | 不支持 | `QRCode.toString(text, {type:'svg'})` |
| 无 DOM 生成 | 需创建隐藏容器 | 原生支持（`toDataURL` 不需要 DOM） |
