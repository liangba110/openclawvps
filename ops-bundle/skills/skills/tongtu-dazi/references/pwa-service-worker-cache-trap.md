# Service Worker 缓存陷阱 — 部署后用户看到旧页面

## 问题

部署新版本前端代码后，用户在手机上刷新页面，看到的仍是旧内容。抓包发现所有 JS chunk 全是旧的文件名（如 `Home-Cu0HtZ93.js` 而不是新部署的 `Home-xxx.js`）。

## 根因

同途搭子启用了 PWA，`sw.js`（Service Worker）注册后在浏览器端：
1. Install 阶段预缓存了 `/`, `/#/list`, `/#/login` 等路由
2. Activate 阶段接管页面
3. Fetch 事件拦截所有请求，先查缓存，命中则返回旧文件

所以无论部署多少次新代码，SW 都默默提供服务旧文件。**这不是服务器端的问题，是浏览器端 SW 缓存。**

## 诊断

浏览器控制台执行：

```javascript
performance.getEntriesByType('resource')
  .filter(r => r.name.includes('index-') || r.name.includes('Home-') || r.name.includes('List-'))
  .map(r => r.name.split('/').pop())
```

如果返回的文件名不等于当前 `index.html` 中引用的文件名（通过 `grep 'assets/' index.html` 查看），说明是 SW 缓存。

## 解决步骤

### 1. 禁用 sw.js — 替换为透传版本

```javascript
// 🚫 Service Worker 已禁用 - 清除所有缓存并取消注册
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
  );
  self.clients.matchAll({ type: "window" }).then((clients) => {
    clients.forEach((client) => client.navigate(client.url));
  });
});
// 不拦截任何请求，直接走网络
self.addEventListener("fetch", (e) => e.respondWith(fetch(e.request)));
```

### 2. 删除 main.js 中的注册代码

```javascript
// 删除或注释掉这部分：
// if ('serviceWorker' in navigator) {
//   window.addEventListener('load', () => {
//     navigator.serviceWorker.register('/sw.js').catch(() => {});
//   });
// }
```

### 3. 重建并部署

```bash
cd /opt/ttdazi/frontend
npm run build
bash /opt/ttdazi/deploy.sh
```

### 4. 通知用户手动清除浏览器缓存

仅刷新页面不够，必须清除缓存：
- **微信内**：我→设置→通用→存储空间→缓存→清理
- **Chrome/浏览器**：设置→隐私和安全→清除浏览数据→勾选"缓存的图片和文件"

之后新 SW 会激活并清除旧缓存。

## 预防措施

- 开发测试阶段使用 `/?nocache=N` 参数 bypass 部分缓存
- 考虑完全移除 PWA 支持（如果不依赖离线能力）
- 部署后用 `browser_console()` 检查实际加载的文件名
