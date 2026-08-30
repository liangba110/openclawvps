# Web 性能优化模式

## 审查方法论（逐层优化）

```
Nginx 缓存头 → Vite 构建配置 → 后端响应 → 部署流水线
```

每次优化后必须用 `curl -sI URL | grep -i 'cache\|expires'` 验证 HTTP 响应头。

## 一、Nginx 缓存头陷阱

### ❌ 致命错误：全局 Cache-Control 覆盖

```
# 错误 — 全局 no-store 覆盖所有子位置
server {
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;

    location /assets/ {
        expires 1y;                                    # 这里没用！被全局覆盖
        add_header Cache-Control "public, immutable";  # 这也被覆盖
    }
}
```

Nginx 的行为：
- `add_header` 从 server block 向下**继承**
- 子 location 的 `add_header` **替换**父级同名头（不是叠加）
- 但 `expires` 指令只在无 `add_header` 覆盖时才生效

### ✅ 正确做法

```
server {
    # 安全头（不走缓存）
    add_header X-Frame-Options "SAMEORIGIN" always;

    # HTML 不缓存
    location = / {
        expires epoch;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # 带哈希的静态资源 — 1年强缓存
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable, max-age=31536000";
        access_log off;
    }
}
```

### 验证命令

```bash
# HTML 应返回 no-cache
curl -sI http://domain/ | grep Cache-Control
# → Cache-Control: no-cache, no-store, must-revalidate

# 带哈希的 JS/CSS 应返回 immutable 1年
curl -sI http://domain/assets/index-abc123.js | grep Cache-Control
# → Cache-Control: public, immutable, max-age=31536000
```

## 二、双重 server_name 冲突

`/etc/nginx/conf.d/` 和 `/etc/nginx/sites-enabled/` 中不能有相同 `server_name` 的 server block。
第一个匹配的生效，第二个被忽略（显示 `conflicting server name` 警告）。

**修复：** 删除 `conf.d/` 中的旧配置，只保留 `sites-enabled/` 中的最新版。

## 三、Vite 构建优化

### CSS 合并（减少 HTTP 请求）

```javascript
// vite.config.js
build: {
    cssCodeSplit: false,        // 所有css合并为1个文件
    cssMinify: 'esbuild',       // css压缩
    assetsInlineLimit: 4096,    // 小图内联base64
    minify: 'esbuild',          // js压缩
    esbuild: { drop: ['debugger'] },
    sourcemap: false,
    rollupOptions: {
        output: {
            manualChunks(id) {
                if (id.includes('node_modules/echarts')) return 'echarts'
                if (id.includes('node_modules/vant')) return 'vant'
                if (id.includes('node_modules/vue')) return 'vue-core'
                if (id.includes('node_modules')) return 'vendor'
            }
        }
    }
}
```

### HTML 预连接

```html
<link rel="dns-prefetch" href="//api-server.com">
<link rel="preconnect" href="//api-server.com" crossorigin>
```

### 路由懒加载（已实现）

```javascript
// router/index.js — 所有路由使用动态 import
{ path: '/', component: () => import('@/views/Home.vue') }
```

## 四、后端优化

```python
# Flask 配置
app.config['JSON_AS_ASCII'] = False  # 中文字符不转义
app.config['JSON_SORT_KEYS'] = False # 取消key排序（默认True）
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400
```

## 五、Nginx TCP 优化

```nginx
sendfile on;
tcp_nopush on;
tcp_nodelay on;
open_file_cache max=1000 inactive=20s;
open_file_cache_valid 30s;
open_file_cache_min_uses 2;
open_file_cache_errors on;
```

## 六、Gzip 扩展

```nginx
gzip on;
gzip_comp_level 6;
gzip_min_length 256;
gzip_vary on;
gzip_types
    text/html text/css text/javascript text/plain text/xml
    application/json application/javascript application/xml
    image/svg+xml image/x-icon font/woff font/woff2;
```

### ⚠️ 陷阱：`gzip on` 但 `gzip_types` 被注释 → 所有资源不压缩

**症状**（2026-08-01 服务器D 实测）：Ubuntu 默认 `/etc/nginx/nginx.conf` 只有 `gzip on;` 和**注释掉的** `gzip_types` 行。只开 `gzip on` 不配 types 时 nginx 只压缩 text/html，**JS/CSS/JSON 全不压缩**（gzip 前后字节数完全一样）。

**验证命令**（必须用，别猜）：
```bash
# gzip 前后字节数对比，一样 = 没生效
curl -s -H 'Accept-Encoding: gzip' -o /dev/null -w '%{size_download}\n' URL
curl -s -o /dev/null -w '%{size_download}\n' URL
```

**修复**：在站点 server block（或 nginx.conf http block）内启用完整 gzip_types。国际站实测 JS 200KB→70KB（省 65%）。

### 国际链路（海外服务器）完整性能配置

海外节点延迟 200ms+，优化分两层：

**Nginx 层（立即生效）**——server block 内：
```nginx
gzip on; gzip_vary on; gzip_proxied any; gzip_comp_level 6; gzip_min_length 256;
gzip_types text/plain text/css text/javascript application/javascript application/json application/xml text/xml image/svg+xml image/x-icon font/woff font/woff2;
sendfile on; tcp_nopush on; tcp_nodelay on;
open_file_cache max=1000 inactive=20s; open_file_cache_valid 30s; open_file_cache_min_uses 2;
ssl_session_cache shared:SSL:10m; ssl_session_timeout 1d;

# 带哈希资源 1 年强缓存（二次访问秒开）
location /assets/ { expires 1y; add_header Cache-Control "public, immutable, max-age=31536000"; access_log off; }
# HTML 不缓存（防旧 chunk 引用）
location / { add_header Cache-Control "no-cache, no-store, must-revalidate"; expires 0; try_files $uri $uri/ /index.html; }
# 上传文件 7 天
location /uploads/ { expires 7d; add_header Cache-Control "public, max-age=604800"; }
```
验证：`curl -sI <assets文件> | grep -i 'cache-control|content-encoding'`。

**CDN 层（根治延迟）**：Cloudflare 免费版（全球 300+ 节点，海外 200ms→~20ms，静态资源边缘缓存）。需用户自己注册账号（邮箱验证码无法代收）→ Add a site → 扫描 DNS 记录 → 改 NS（本项目域名 NS 在 dnsowl/Namecheap，改到 Cloudflare 给的 NS，10min~24h 生效不中断）。服务器端 SSL 模式配「完全加密」与 CDN 匹配。

## 七、部署自动同步 Nginx

`deploy.sh` 中必须包含 Nginx 配置同步和 reload：

```bash
scp deploy/nginx.conf server_b:/tmp/
ssh server_b "sudo cp /tmp/nginx.conf /etc/nginx/sites-enabled/ && \
              sudo rm -f /etc/nginx/conf.d/old.conf && \
              sudo nginx -t && sudo systemctl reload nginx"
```

## 八、效果测量

```bash
# 首页加载时间
time curl -so /dev/null http://domain/

# 资源缓存验证
curl -sI http://domain/assets/vendor-*.js | grep -E 'Cache-Control|Expires'

# Gzip 验证
curl -s -H "Accept-Encoding: gzip" -o /dev/null \
    -w "size: %{size_download}\n" http://domain/assets/vant-*.js

# 对比 gzip 前后
curl -s -o /dev/null -w "gzip: %{size_download}\n" -H "Accept-Encoding: gzip" URL
curl -s -o /dev/null -w "raw: %{size_download}\n" URL
```
