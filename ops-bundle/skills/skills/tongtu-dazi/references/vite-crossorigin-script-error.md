# Vite `crossorigin` + Nginx CORS → 白屏/ Script error.

## 症状

页面 HTML 正常加载，`<div id="app">` 存在，但 Vue 不挂载。浏览器控制台报：
- `js_errors: [{message: "", source: "exception"}]` — 空消息的 Script error.
- `typeof Vue === 'undefined'` — Vue 根本没加载

## 根因

Vite 5 在构建时为 `<script type="module">` 和 `<link rel="modulepreload">` **自动添加 `crossorigin` 属性**：

```html
<!-- Vite 构建输出 -->
<script type="module" crossorigin src="/assets/index-xxx.js"></script>
<link rel="modulepreload" crossorigin href="/assets/vue-core-xxx.js">
```

即使源码 `index.html` 没有 `crossorigin`，Vite 也会在构建产物中加回去（通过 `build.crossOrigin` 配置项）。

当浏览器遇到 `<script type="module" crossorigin>` 时，会以 **CORS 模式** 请求脚本。如果 Nginx 响应头中没有 `Access-Control-Allow-Origin`，浏览器报 Script error. 且**不暴露任何错误详情**（空 message），导致整个模块加载链断裂 → 白屏。

## 完整调试路径

```
白屏 → console Script error. (空 message)

  → 检查 HTML 中是否有 crossorigin
    → 有：检查 Nginx 是否有 CORS 头
      → 无 CORS 头：方案 A（Nginx CORS）
      → 有 CORS 头：检查 vendor chunk 是否有模块初始化错误

    → 无 crossorigin：检查所有 chunk 是否 404
      → 有 404：重新部署（deploy.sh 可能漏传文件）
      → 无 404：检查 vendor chunk 运行时错误

  → vendor chunk 错误 → 检查 qrcodejs2
    → 使用 qrcodejs2？→ 卸载，改用 qrcode 包
    → 其他错误 → 具体分析
```

## 修复方案

### 方案 A：Nginx 添加 CORS 头（推荐，不依赖构建配置）

```nginx
# 在 dazi.openai2000.cn 的 server block 中
location /assets/ {
    expires 7d;
    add_header Cache-Control "public, immutable";
    add_header Access-Control-Allow-Origin "*" always;  # 关键
}
```

然后 reload Nginx：
```bash
ssh ubuntu@82.157.202.24 "sudo nginx -s reload"
```

### 方案 B：构建后手动移除 crossorigin

```bash
sed -i 's/ crossorigin//g' /opt/ttdazi/frontend/dist/index.html
```

然后将 index.html 和 assets 同步到 Server B：
```bash
scp /opt/ttdazi/frontend/dist/index.html ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/
scp -r /opt/ttdazi/frontend/dist/assets/* ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/assets/
```

### 方案 C：Vite 配置（Vite 5 中此选项无效）

```js
// vite.config.js — 此配置在 Vite 5.4 中无效，Vite 仍会添加 crossorigin
build: {
  crossOrigin: false,
}
```

**结论**：方案 A（Nginx CORS）+ 方案 B（sed 移除）组合最可靠。

## qrcodejs2 UMD 兼容性陷阱（另一白屏根因）

即使 CORS 修复后，`qrcodejs2` 本身也可能导致 vendor chunk 加载失败：

### 错误信息

```
TypeError: Cannot read properties of undefined (reading '_android')
  at vendor-xxx.js:41:93403
```

### 原因

`qrcodejs2` 的 UMD 模块在 Vite/Rollup 打包时，内部的 `_getAndroid()` 函数（依赖 `navigator.userAgent`）在模块作用域解析异常，导致 QRCode 构造函数引用 `_android` 为 undefined。

### 修复

卸载 qrcodejs2，改用兼容的 `qrcode` 包：

```bash
npm uninstall qrcodejs2
npm install qrcode
```

### API 迁移

```javascript
// ❌ qrcodejs2（DOM 操作式，有兼容问题）
import QRCode from 'qrcodejs2'
const temp = document.createElement('div')
new QRCode(temp, { text: url, width: 180, height: 180 })
const dataUrl = temp.querySelector('canvas').toDataURL('image/png')

// ✅ qrcode（纯数据式，返回 Promise，兼容 Vite）
import QRCode from 'qrcode'
const dataUrl = await QRCode.toDataURL(url, { width: 180, margin: 1 })
```

`qrcode` 包优势：无 DOM 依赖、函数式 API、TypeScript 支持、活跃维护。

## 验证

```bash
# 验证 CORS 头
curl -sI "https://dazi.openai2000.cn/assets/index-xxx.js" | grep -i access-control
# 应输出: access-control-allow-origin: *

# 验证无 crossorigin
curl -s "https://dazi.openai2000.cn/" | grep -c 'crossorigin'
# 应输出: 0

# 验证 vendor 无 qrcodejs2 残留
curl -s "https://dazi.openai2000.cn/assets/vendor-xxx.js" | grep -c 'qrcodejs2'
# 应输出: 0
```

## Nginx 配置安全操作

修改 Nginx 配置时，避免用 `sed /pattern/d` 删除包含特定字符串的行，这会意外删除整个 location 块：

```bash
# ❌ 危险：删除匹配行可能误删整段配置
sudo sed -i '/some.pattern/d' /etc/nginx/sites-enabled/huizhiyunma

# ✅ 安全：先用 visual 检查，再做精确替换
sudo nginx -T 2>/dev/null | grep -A5 'location /assets/'
# 确认要修改的位置后，再用精确的 sed 替换
```

## 相关文件

- `/opt/ttdazi/frontend/vite.config.js` — Vite 构建配置
- `/etc/nginx/sites-enabled/huizhiyunma` — Server B Nginx 配置（dazi.openai2000.cn 在此文件中）
