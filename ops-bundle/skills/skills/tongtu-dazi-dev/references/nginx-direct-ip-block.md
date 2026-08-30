# Server B 禁止 IP 直连

## 背景

2026-07-16 发现通过 `http://82.157.202.24/` 可直接访问网站，存在安全隐患。

## 根因

`/etc/nginx/sites-enabled/ttdazi` 配置中包含 `server_name 82.157.202.24;`，明确允许通过 IP 直接访问。

## 修复

```bash
# 删除允许 IP 直连的配置
sudo rm /etc/nginx/sites-enabled/ttdazi
sudo nginx -t && sudo nginx -s reload
```

## 验证

```bash
# IP 直连应返回 444（断开连接）
curl -s -o /dev/null -w "%{http_code}" http://82.157.202.24/
# 输出: 000

# 域名访问应正常
curl -s -o /dev/null -w "%{http_code}" https://dazi.openai2000.cn/
# 输出: 200
```

## 防御机制

Server B 已有 `deny-ip.conf`（`listen 80 default_server; return 444;`）作为默认处理，但 `ttdazi` 配置的 `server_name 82.157.202.24` 优先级更高，抢占了 IP 请求。

**注意**：`deny-ip.conf` 使用 `listen 443 ssl http2 default_server` 处理 HTTPS IP 直连（返回 444），但 HTTP 部分曾被 `ttdazi` 配置覆盖。
