# Tencent Cloud WAF + ModSecurity Setup (2026-07 Session)

## Core Principle — NEVER use server-internal iptables on Tencent Cloud

**User correction (this session):** "不要用服务器内部 iptables。这样不会锁死自己"

iptables changes applied via SSH can lock you out if the ACCEPT rule for SSH isn't applied before the DROP default. Tencent Cloud Security Groups are applied at the hypervisor level — they **cannot** lock you out of SSH because the console/VNC bypasses them.

**Always use Security Groups for firewall rules, never iptables.**

## Security Architecture (7 layers)

```
Layer 1: Tencent Cloud Security Group (network-level IP whitelist)
Layer 2: Nginx ModSecurity WAF (SQL injection/XSS/scanner/CC)
Layer 3: Nginx rate limiting (30r/s API, 5r/m login)
Layer 4: Application rate limiting (login IP/account lockout)
Layer 5: CAPTCHA (bot prevention)
Layer 6: JWT auth + refresh tokens (30min TTL)
Layer 7: Input sanitization + field whitelist
```

## Security Group Rules (Recommended)

**Server A (42.193.113.230 — Backend + DB):**
| Direction | Protocol | Port | Source | Description |
|-----------|----------|------|--------|-------------|
| Inbound | TCP | 22 | 0.0.0.0/0 | SSH (key-auth only) |
| Inbound | TCP | 5002 | 82.157.202.24 | Only server B → backend API |
| Outbound | ALL | ALL | 0.0.0.0/0 | Default allow |

**Server B (82.157.202.24 — Nginx + Frontend):**
| Direction | Protocol | Port | Source | Description |
|-----------|----------|------|--------|-------------|
| Inbound | TCP | 22 | 42.193.113.230 | Only server A SSH |
| Inbound | TCP | 80 | 0.0.0.0/0 | HTTP public |
| Inbound | TCP | 443 | 0.0.0.0/0 | HTTPS public |
| Outbound | ALL | ALL | 0.0.0.0/0 | Default allow (no config needed) |

## ModSecurity Installation

```bash
# On the Nginx server (Server B)
sudo apt-get update && sudo apt-get install -y libnginx-mod-http-modsecurity

# Verify module loaded (should appear in nginx -T output)
sudo nginx -T 2>&1 | grep modsecurity
```

## ModSecurity Rules (ttdazi-modsecurity.conf)

Place at `/etc/nginx/modsecurity.conf`:

```nginx
SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess Off
SecDataDir /tmp/modsecurity
SecRequestBodyLimit 10485760
SecRequestBodyNoFilesLimit 1048576

# SQL Injection
SecRule ARGS "(?i:(\\bor\\b\\s*\\d+\\s*[=<>]|\\band\\b\\s*\\d+\\s*[=<>]|union\\s+(all\\s+)?select|\\bselect\\s+.*\\bfrom\\b|information_schema|sleep\\s*\\(|0x[0-9a-f]{8,}))" "id:10001,phase:2,deny,status:403,msg:SQL Injection blocked"

# XSS
SecRule ARGS|ARGS_NAMES|REQUEST_URI "(?i:(<script[^>]*>|javascript:|onload\\s*=|onerror\\s*=|onclick\\s*=|alert\\s*\\(|prompt\\s*\\(|confirm\\s*\())" "id:10002,phase:2,deny,status:403,msg:XSS blocked"

# Path traversal
SecRule REQUEST_URI|ARGS "(?i:(\\.\\.\\/|\\.\\.\\\\\\\\|/etc/passwd|/etc/shadow|/proc/self))" "id:10003,phase:1,deny,status:403,msg:Path traversal blocked"

# Malicious scanners
SecRule REQUEST_HEADERS:User-Agent "(?i:(acunetix|netsparker|sqlmap|nmap|nikto|nessus|openvas|wpscan|burpsuite|appscan|zap|hydra))" "id:10005,phase:1,deny,status:403,msg:Scanner blocked"

# Large body
SecRule REQUEST_BODY "@gt 5242880" "id:10006,phase:2,deny,status:413,msg:Body too large"

SecAuditEngine RelevantOnly
SecAuditLog /var/log/modsecurity_audit.log
SecAuditLogParts ABIJDEFHZ
```

## Nginx Config with WAF

Enable ModSecurity in the server block:

```nginx
server {
    listen 80;
    
    modsecurity on;
    modsecurity_rules_file /etc/nginx/modsecurity.conf;
    
    # Rate limiting
    limit_req zone=api_limit burst=5 nodelay;
    limit_req zone=login_limit burst=1 nodelay;
    
    # Admin backend IP restriction
    location ~ ^/(op-manage-7x2d9|admin)(/|$) {
        limit_req zone=login_limit burst=1 nodelay;
        allow 42.193.113.230;
        allow 127.0.0.1;
        deny all;
        proxy_pass http://42.193.113.230:5002;
    }
    
    # Login rate limiting
    location ~ /api/(user/login|user/register|admin/login|captcha|send-code|register-by) {
        limit_req zone=login_limit burst=1 nodelay;
        proxy_pass http://42.193.113.230:5002;
    }
    
    # General API
    location /api/ {
        limit_req zone=api_limit burst=5 nodelay;
        client_max_body_size 10m;
        proxy_pass http://42.193.113.230:5002;
    }
}
```

## CC Attack Protection (Rate Limiting)

Define zones in `nginx.conf` http block:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
```

## Deploy Flow

1. Create config files locally
2. SCP to server B: `scp file ubuntu@82.157.202.24:/tmp/`
3. Copy to target: `sudo cp /tmp/file /etc/nginx/...`
4. Test: `sudo nginx -t`
5. Reload: `sudo nginx -s reload`
6. Verify: `curl -sI http://host/ | grep -i "x-frame\|x-xss\|x-content"`

## Verification Commands

```bash
# Security headers
curl -sI http://82.157.202.24/ | grep -i "x-frame\|x-content\|x-xss\|referrer\|permissions"

# WAF attack tests
curl -s -o /dev/null -w "%{http_code}" "http://host/?q=<script>alert(1)</script>"
curl -s -o /dev/null -w "%{http_code}" -A "sqlmap/1.7" "http://host/"
curl -s -o /dev/null -w "%{http_code}" "http://host/../../../etc/passwd"
curl -s -o /dev/null -w "%{http_code}" --get --data-urlencode "id=1 OR 1=1" "http://host/api/companion/list"

# Rate limiting
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://host/api/user/login -d '{}'
done

# Sensitive file blocking
curl -s -o /dev/null -w "%{http_code}" "http://host/.env"
```
