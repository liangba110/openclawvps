# Security Hardening Patterns (同途搭子)

Captures the 10-item security audit + fix session (2026-07-05) and subsequent WAF/ModSecurity/anti-brute-force hardening (2026-07-06).

## 1. Nginx Security Headers

Add to server block BEFORE any location blocks:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
add_header Cache-Control "no-store, no-cache, must-revalidate" always;
```

## 2. Block Sensitive File Extensions

```nginx
location ~ \\.(env|git|sql|log|bak|swp|md|py|json|yaml|yml)$ {
    deny all;
}
```

## 3. Upload Directory Security

```nginx
# ❌ DON'T do this — blocks admin verify page from viewing id photos
location ~ ^/uploads/(id_cards|backups)/ {
    deny all;
    return 404;
}

# ✅ DO this instead — proxy to backend when local file not found
location /uploads/ {
    expires 1d;
    add_header Cache-Control "public";
    try_files $uri @api_uploads;
}
location @api_uploads {
    proxy_pass http://42.193.113.230:5002;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

## 4. CORS Hardening

```python
# ❌ Too permissive
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ✅ Specific origins
CORS(app, resources={r"/api/*": {"origins": ["http://82.157.202.24", "http://localhost:5002"]}})
```

## 5. JWT TTL

```python
# ❌ 72 hours — too long if token leaked
JWT_EXPIRE_HOURS = 72

# ✅ 24 hours
JWT_EXPIRE_HOURS = 24
```

## 6. Config → Env Vars

All secrets in config.py should have env var fallbacks:

```python
JWT_SECRET = os.environ.get('JWT_SECRET', 'default-fallback')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'default')
SERVER_PORT = int(os.environ.get('SERVER_PORT', 5002))
```

## 7. SQL Injection — Field Whitelist for Dynamic SET Clauses

When building `SET col=%s` clauses from user-supplied dict keys:

```python
ALLOWED = {'nickname', 'phone', 'email', 'gender', 'city', 'status', 'phone_bound', 'avatar'}
safe_updates = {k: v for k, v in updates.items() if k in ALLOWED}
if not safe_updates:
    return fail('没有允许更新的字段')
set_clause = ', '.join([f"`{k}`=%s" for k in safe_updates])
values = list(safe_updates.values()) + [user_id]
cur.execute(f"UPDATE user SET {set_clause} WHERE id=%s", values)
```

Apply to ALL update endpoints: user, banner, game — each with its own ALLOWED set.

## 8. File Upload — Magic Number Validation (Beyond Extension)

```python
# Extension check
ext = file.filename.rsplit('.', 1)[-1].lower()
if ext not in allowed: return fail('格式不支持')

# Magic number check (read first bytes)
header = file.read(12)
file.seek(0)
if ext in ('jpg', 'jpeg') and header[:2] != b'\xff\xd8':
    return fail('文件格式与扩展名不匹配')
if ext == 'png' and header[:8] != b'\x89PNG\r\n\x1a\n':
    return fail('文件格式与扩展名不匹配')
if ext == 'gif' and header[:6] not in (b'GIF87a', b'GIF89a'):
    return fail('文件格式与扩展名不匹配')
if ext == 'webp' and (header[:4] != b'RIFF' or header[8:12] != b'WEBP'):
    return fail('文件格式与扩展名不匹配')
```

Also apply to platform_review.py upload_id_card() — the JPEG header check must be lenient:
```python
if img_data[:2] == b'\xff\xd8':  # any JPEG variant
    ext = 'jpg'
elif img_data[:8] == b'\x89PNG\r\n\x1a\n':
    ext = 'png'
elif img_data[:4] == b'RIFF' and img_data[8:12] == b'WEBP':
    ext = 'webp'
else:
    return fail('请上传JPG/PNG/WebP格式图片')
```

## 9. Deploy Script — Remove Plaintext Passwords

```bash
# ❌ OLD — password in script
SERVER_B_PASS="wll16562341@"
sshpass -p "$SERVER_B_PASS" ssh user@host

# ✅ NEW — SSH key authentication
# 1. Generate key: ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
# 2. Copy to server: ssh-copy-id user@host
# 3. Deploy without password:
ssh -o StrictHostKeyChecking=no user@host "mkdir -p $SERVER_B_PATH"
scp -o StrictHostKeyChecking=no dist/* user@host:$SERVER_B_PATH/
```

## 10. Admin Route Obfuscation

Change default `/admin` paths to random private paths to prevent scanner detection:

```bash
# Replace in all Vue route files
/admin  →  /op-manage-7x2d9
```

Add a redirect from the old path in App.vue:
```js
watch(() => route.path, (p) => {
  if (p.startsWith('/admin/') || p === '/admin') {
    const newPath = p.replace('/admin', '/op-manage-7x2d9')
    router.push(newPath)
  }
})
```

## 11. iptables Safety Rule

**NEVER** apply `iptables -P INPUT DROP` before confirming ACCEPT rules work:

```bash
# ❌ DANGEROUS — SSH session might disconnect between DROP and ACCEPT
sudo iptables -P INPUT DROP
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT  # too late!

# ✅ SAFE — add ALL ACCEPT rules first, THEN drop
sudo iptables -A INPUT -i lo -j ACCEPT
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
# ... all other rules ...
sudo iptables -P INPUT DROP  # last step
```

**Better:** Use cloud security groups (Tencent Cloud/阿里云) instead of server iptables.

## 13. Nginx ModSecurity WAF

### 安装
```bash
ssh ubuntu@82.157.202.24 'sudo apt-get install -y libnginx-mod-http-modsecurity'
```

### ModSecurity 核心规则文件 (/etc/nginx/modsecurity.conf)
```nginx
SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess Off
SecDataDir /tmp/modsecurity

# SQL注入（不限制括号后缀，实际注入不用括号）
SecRule ARGS "(?i:\b(select|insert\s+into|update\s+\w+\s+set|delete\s+from|drop\s+table|...|information_schema|sleep\s*\(|benchmark\s*\()\b)" "id:10001,phase:2,deny,status:403,msg:SQL Injection blocked"

# XSS
SecRule ARGS|ARGS_NAMES|REQUEST_URI "(?i:(<script[^>]*>|javascript:|onload\s*=|onerror\s*=|alert\s*\())" "id:10002,phase:2,deny,status:403,msg:XSS blocked"

# 路径遍历
SecRule REQUEST_URI|ARGS "(?i:(\.\.\/|/etc/passwd|/etc/shadow))" "id:10003,phase:1,deny,status:403,msg:Path traversal blocked"

# 命令注入
SecRule ARGS "(?i:(cmd\s*=|exec\s*=|system\s*=|eval\s*\(|base64_decode))" "id:10004,phase:2,deny,status:403,msg:Command injection blocked"

# 扫描器
SecRule REQUEST_HEADERS:User-Agent "(?i:(acunetix|sqlmap|nmap|nikto|nessus|wpscan|burpsuite|hydra|dirbuster|gobuster))" "id:10005,phase:1,deny,status:403,msg:Scanner blocked"

# 大请求体
SecRule REQUEST_BODY "@gt 5242880" "id:10006,phase:2,deny,status:413,msg:Request body too large"
```

### 嵌入Nginx server块
```nginx
modsecurity on;
modsecurity_rules_file /etc/nginx/modsecurity.conf;
```

### WAF验证
```bash
# XSS → 403
curl -s -o /dev/null -w "%{http_code}" "http://host/?q=<script>alert(1)</script>"
# Scanner → 403
curl -s -o /dev/null -w "%{http_code}" -A "sqlmap/1.7" http://host/
# SQL注入 → 403
curl -s -o /dev/null -w "%{http_code}" --get --data-urlencode "id=1 OR 1=1" "http://host/api/endpoint"
# 正常 → 200
curl -s -o /dev/null -w "%{http_code}" http://host/
```

### ⚠️ URL编码注入可绕过ModSecurity
`curl "http://host/?id=1%20OR%201=1"` → ModSecurity 不解码空格 → 200。
**必须使用 `--data-urlencode`** 让curl预编码：`curl --get --data-urlencode "id=1 OR 1=1" "http://host/"` → 403。

## 14. ⚠️ ERR_BLOCKED_BY_CLIENT（浏览器导航失败）

`browser_navigate` 返回 `net::ERR_BLOCKED_BY_CLIENT`：
- 浏览器客户端侧屏蔽，与服务端/ModSecurity 无关
- 常见原因：广告拦截器插件、HTTP（非HTTPS）页面限制、CSP
- 不影响真实用户浏览器访问

## 15. Admin Route Daily Rotation Nginx Sync Caveat

`rotate_admin_path.sh` 需要更新 Nginx 的 `location ~ ^/(PATH|admin)` 匹配规则。
**sed 必须在不同行匹配（escape 注意）**：
```bash
# 正确 — 换行用 \n 而不是实际换行
sudo sed -i "s|/$OLD_PATH/|/$NEW_PATH/|g" /etc/nginx/conf.d/ttdazi.conf
```


```bash
# Security headers
curl -sI http://host/ | grep -i "x-frame\|x-content\|x-xss\|referrer\|permissions"
# Sensitive file blocking
curl -s -o /dev/null -w "%{http_code}" http://host/.env        # expect 403
curl -s -o /dev/null -w "%{http_code}" http://host/config.py   # expect 403
# Protected directory
curl -s -o /dev/null -w "%{http_code}" http://host/uploads/id_cards/test.jpg  # expect 404
# CORS not wildcard
curl -sI -H "Origin: http://evil.com" http://host/api/health | grep -i "access-control"  # expect empty
```
