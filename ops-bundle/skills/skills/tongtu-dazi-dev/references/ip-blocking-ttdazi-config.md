# IP 直连拦截与 ttdazi 配置泄露

## 问题发现

Server B 上存在 `sites-enabled/ttdazi` 配置文件，其 `server_name 82.157.202.24;` 允许通过服务器公网 IP 直接访问网站，绕过了已有的 `deny-ip.conf` 默认拦截规则。

## Nginx 默认拦截机制

`/etc/nginx/sites-enabled/deny-ip.conf`:
```nginx
server {
    listen 80 default_server;
    listen 443 ssl http2 default_server;
    server_name _;
    ssl_certificate     /etc/letsencrypt/live/openai2000.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/openai2000.cn/privkey.pem;
    return 444;  # 直接断开连接，无响应
}
```

## 泄露配置

`/etc/nginx/sites-enabled/ttdazi`:
```nginx
server {
    listen 80;
    server_name 82.157.202.24;

    add_header X-Frame-Options "SAMEORIGIN" always;
    # ... 代理到后端 5002 ...
}
```

该配置使 `http://82.157.202.24/` 能够正常访问网站，完全绕过 `return 444` 规则。

## 修复

```bash
sudo rm /etc/nginx/sites-enabled/ttdazi
sudo nginx -t && sudo nginx -s reload
```

## 验证

| 访问方式 | 预期 | 验证命令 |
|---------|------|---------|
| `http://82.157.202.24/` | ❌ 444 断开 | `curl -s -o /dev/null -w "%{http_code}" http://82.157.202.24/` |
| `https://82.157.202.24/` | ❌ 444 断开 | `curl -s -o /dev/null -w "%{http_code}" https://82.157.202.24/ -k` |
| `https://dazi.openai2000.cn/` | ✅ 200 正常 | `curl -s -o /dev/null -w "%{http_code}" https://dazi.openai2000.cn/` |
| `https://openai2000.cn/` | ✅ 200 正常 | `curl -s -o /dev/null -w "%{http_code}" https://openai2000.cn/` |

## 定期检查

```bash
# 列出 sites-enabled 所有配置文件
ls -la /etc/nginx/sites-enabled/

# 检查是否有 files/conf 使用了 IP 作为 server_name
sudo nginx -T 2>/dev/null | grep -B5 'server_name.*[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+'
```
