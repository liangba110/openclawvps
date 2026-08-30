# Nginx SSL + 安全配置（Server B 实操笔记）

## 多域名 HTTPS（SNI 模式）

Server B (82.157.202.24) 共享 443 端口，Nginx 根据 TLS SNI 自动匹配 server_name。

### 正确步骤

```bash
# 1. 申请证书（certbot）
sudo certbot certonly --webroot -w /home/ubuntu/ttdazi-frontend -d dazi.openai2000.cn --agree-tos --register-unsafely-without-email -n

# 2. 写入 Nginx 配置，确保 server_name 唯一
server {
    listen 443 ssl http2;
    server_name dazi.openai2000.cn;  # 不能与现有站点重复
    ...

# 3. 确认 huizhiyunma 不是 default_server
grep 'default_server' /etc/nginx/sites-enabled/huizhiyunma
# 如果有，改为 listen 443 ssl http2; （去掉 default_server）
```

### 🔴 常见坑

| 现象 | 原因 | 修复 |
|------|------|------|
| HTTPS 返回 `CN=openai2000.cn`（错误的证书） | 第一 server block 没有 `server_name` 或现有站点是 `default_server` | 去掉 `default_server`，确保新站点 `server_name` 唯一 |
| HTTP 返回 403 | huizhiyunma 的域名白名单限制 | HTTP 也配置专属 `server_name` |
| 修改 sites-available 后 Nginx 不生效 | sites-enabled 中的文件是**副本**不是软链接 | 直接修改 sites-enabled 中的文件 |
| 写入 sites-enabled 的文件自动恢复旧内容 | **1Panel** 面板管理 Nginx 配置，定期恢复 | 将新站点配置合并到 `huizhiyunma` 文件（不被 1Panel 管理）|
| 浏览器的 HTTPS 错误无法消除 | 缓存了旧的 HSTS 或证书 | 清理浏览器缓存，用 Chrome DevTools → Network → Disable cache |

### 安全头模板

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=(self)" always;
```

## 敏感文件保护

```nginx
location ~* \.(pem|key|crt|p12|sql|bak|backup|env|log|tar\.gz|zip)$ {
    deny all;
    return 404;
}
```

## iptables 端口管理

Server A 默认 DROP 策略，新服务需手动放行：

```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5005 -j ACCEPT
# 持久化
sudo apt install -y iptables-persistent && sudo netfilter-persistent save
```

## 验证命令

```bash
# SSL 证书
curl -svI https://dazi.openai2000.cn/ 2>&1 | grep -E 'subject:|issuer:|SSL certificate'

# 安全头
curl -sI https://dazi.openai2000.cn/ 2>/dev/null | grep -iE 'strict|frame|xss|content|referrer|permission'

# 混合内容
curl -sk https://dazi.openai2000.cn/ 2>/dev/null | grep -oP 'src="http://[^"]*"'

# 敏感文件保护
curl -sk -o /dev/null -w '%{http_code}' https://dazi.openai2000.cn/test.pem

# Nginx 配置文件检查
sudo nginx -t
```
