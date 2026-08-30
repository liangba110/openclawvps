# Performance Optimization Checklist

## Layer 1: Nginx

### Cache Headers (highest impact)

```nginx
# For hashed static assets (content hash in filename = immutable)
location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable, max-age=31536000";
    access_log off;
}

# For index.html (ALWAYS fresh, never cache)
location = /index.html {
    expires epoch;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

**CRITICAL: Never set `Cache-Control` at server level** if you have per-location cache directives.
`add_header` in a child block **replaces** (does not merge) the parent's `add_header` for the same key.
Setting `add_header Cache-Control "no-store, no-cache, must-revalidate"` at the server level
**overrides** all per-location `expires` directives.

### Gzip / Brotli

```nginx
gzip on;
gzip_comp_level 6;          # 4→6 gives ~12% better ratio
gzip_min_length 256;
gzip_proxied any;
gzip_vary on;
gzip_types
    text/html text/css text/javascript text/plain text/xml
    application/json application/javascript application/xml
    image/svg+xml image/x-icon
    font/woff font/woff2;
```

### TCP / Kernel

```nginx
sendfile on;
tcp_nopush on;
tcp_nodelay on;
open_file_cache max=1000 inactive=20s;
open_file_cache_valid 30s;
open_file_cache_min_uses 2;
open_file_cache_errors on;
```

### Verification

```bash
# Check cache headers
curl -sI http://example.com/assets/style-abc123.css | grep -i 'cache-control\|expires'

# Check gzip
curl -s -H "Accept-Encoding: gzip" -o /dev/null -w "gzip: %{size_download} bytes\n" http://example.com/assets/vendor-abc123.js

# Check full page load time
curl -s -o /dev/null -w "Time: %{time_total}s, Size: %{size_download} bytes\n" http://example.com/
```

## Layer 2: Vite Build Configuration

```js
// vite.config.js - Key optimization settings
build: {
    cssCodeSplit: false,          // Merge all page CSS into 1 file (fewer HTTP requests)
    assetsInlineLimit: 4096,      // Inline small images as base64
    minify: 'esbuild',            // Fastest minifier
    cssMinify: 'esbuild',         // Compress CSS
    sourcemap: false,             // Disable sourcemaps in production
    esbuild: { drop: ['debugger'] },
    rollupOptions: {
        output: {
            manualChunks(id) {
                // ONLY split node_modules, never page components
                if (id.includes('node_modules/echarts')) return 'echarts';
                if (id.includes('node_modules/vant')) return 'vant';
                if (id.includes('node_modules/vue') || id.includes('node_modules/@vue')
                    || id.includes('node_modules/vue-router')) return 'vue-core';
                if (id.includes('node_modules')) return 'vendor';
            }
        }
    },
    chunkSizeWarningLimit: 600,
}
```

### CSS consolidation benchmark

| Approach | Files | Size | HTTP requests |
|----------|-------|------|---------------|
| Default (cssCodeSplit: true) | 50+ CSS files | ~4KB each | 50+ |
| Merged (cssCodeSplit: false) | 1 CSS file | ~385KB | 1 (cached 1 year) |

## Layer 3: HTML Preconnect

```html
<head>
  <link rel="dns-prefetch" href="//api.example.com">
  <link rel="preconnect" href="//api.example.com" crossorigin>
</head>
```

## Layer 4: Backend (Flask)

```python
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False       # Skip key sorting (~5% less JSON size)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # Default static file cache
```

## Measuring Improvement

```bash
# Before/after comparison
curl -w "@curl-format.txt" -o /dev/null -s http://example.com/

# curl-format.txt content:
#    time_namelookup:  %{time_namelookup}s\n
#    time_connect:  %{time_connect}s\n
#    time_starttransfer:  %{time_starttransfer}s\n
#    time_total:  %{time_total}s\n
#    speed_download: %{speed_download}B/s\n
```

## Common Mistakes

1. **Setting Cache-Control at server level** → overrides all location-level expires
2. **add_header + expires on same header** → add_header replaces expires' Cache-Control
3. **Two Nginx configs with same server_name** → only first alphabetically is used
4. **ModSecurity enabled in headless test environments** → blocks CLI browsers
5. **Vite manualChunks for page components** → breaks cross-chunk imports
