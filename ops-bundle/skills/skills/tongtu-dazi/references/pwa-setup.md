# PWA 配置指南

## 所需文件

PWA 需要 3 个文件 + index.html 修改 + main.js 注册：

```
public/
├── manifest.json    # PWA 清单（应用名、图标、启动方式）
├── sw.js            # Service Worker（离线缓存）
├── icon-192.png     # 应用图标 192x192
└── icon-512.png     # 应用图标 512x512
```

## manifest.json

```json
{
  "name": "同途搭子",
  "short_name": "同途搭子",
  "description": "找到你的专属游戏伙伴",
  "start_url": "/#/",
  "display": "standalone",
  "background_color": "#667eea",
  "theme_color": "#667eea",
  "orientation": "portrait",
  "icons": [
    {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
  ]
}
```

## sw.js（Service Worker）

```javascript
const CACHE = "ttdazi-v1";
const ASSETS = ["/", "/#/login", "/#/list", "/#/profile"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((k) =>
      Promise.all(k.filter((n) => n !== CACHE).map((n) => caches.delete(n)))
    )
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.url.includes("/api/")) return;
  e.respondWith(
    caches.match(e.request)
      .then((r) => r || fetch(e.request))
      .catch(() => caches.match("/"))
  );
});
```

## index.html 修改

```html
<head>
  <link rel="manifest" href="/manifest.json">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="同途搭子">
</head>
```

## main.js 注册

```javascript
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
```

## 图标生成

用 Python 生成简单纯色圆角矩形图标（无需 PIL/cairosvg 依赖）：

```python
import struct, zlib

def create_png(size, path):
    w = h = size
    r = int(size * 0.42)
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            dx = abs(x - w//2)
            dy = abs(y - h//2)
            if dx > r or dy > r:
                raw += b'\x00\x00\x00\x00'
            else:
                raw += b'\x66\x7e\xea\xff'
    compressed = zlib.compress(raw)
    def c(ct, d):
        crc = struct.pack('>I', zlib.crc32(ct + d) & 0xffffffff)
        return struct.pack('>I', len(d)) + ct + d + crc
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(c(b'IHDR', ihdr))
        f.write(c(b'IDAT', compressed))
        f.write(c(b'IEND', b''))

create_png(192, 'public/icon-192.png')
create_png(512, 'public/icon-512.png')
```

## 文件权限陷阱

write_file() 创建的 manifest.json 和 sw.js 默认权限为 600（仅 owner 可读）。Vite 构建时保留源文件权限，部署后 Nginx 以 www-data 运行 → 403。

修复：chmod 644 public/manifest.json public/sw.js && chmod 644 dist/manifest.json dist/sw.js && ssh Server_B chmod 644 path/manifest.json path/sw.js

## manifest.json 被 Nginx deny 拦截

如果 Nginx 有 location ~ \\.(json|\...)$ { deny all; } 规则，manifest.json 会被 403。location = /manifest.json { allow all; } 可解决。
