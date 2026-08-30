# Nginx WAF Setup — Rate Limiting + IP Blacklist

## Core Principle

Never use heredoc+sed for Nginx config changes via SSH — `$` escaping breaks every time.
**WRITE CONFIG LOCALLY → SCP → MOVE INTO PLACE.**

## Nginx Configs

### nginx.conf — Limit Zones + Geo Blacklist

```nginx
http {
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
    
    geo $blacklist {
        default 0;
        include /etc/nginx/ip_blacklist.conf;
    }
}
```

### Server Block — WAF Rules

```nginx
server {
    listen 80;
    # WAF
    limit_req zone=api_limit burst=50 nodelay;
    limit_conn conn_limit 50;
    if ($blacklist) { return 403; }
    # ... rest of config
}
```

## Deploy Workflow

```bash
# 1. Write config locally → base64 → SCP
python3.12 -c "
import base64
with open('/tmp/nginx_waf.conf') as f:
    b64 = base64.b64encode(f.read().encode()).decode()
print(b64)
" | ssh ubuntu@B 'base64 -d | sudo tee /etc/nginx/nginx.conf > /dev/null'

# 2. Apply
ssh ubuntu@B 'sudo nginx -t && sudo nginx -s reload'
```

## IP Blacklist Tool (`/usr/local/bin/ip_ban`)

```bash
# Ban
ssh Server_B sudo ip_ban ban 1.2.3.4
# Unban
ssh Server_B sudo ip_ban unban 1.2.3.4
# List
ssh Server_B sudo ip_ban list
```

### Backend Sync (`risk_control.py → Nginx`)

`ban_ip()` in risk_control.py also writes to Nginx blacklist:
```python
import subprocess
subprocess.run(
    ['sshpass', '-p', 'wll16562341@', 'ssh', 'ubuntu@82.157.202.24',
     f'sudo bash -c "echo \\"{ip} 1;\\" >> /etc/nginx/ip_blacklist.conf && nginx -s reload"'],
    capture_output=True, timeout=5
)
```

## Verification

```bash
curl -sI http://82.157.202.24/ | grep -i 'server'
# → Server: nginx (NOT nginx/1.24.0 — server_tokens off)
```

## Diagnosing Nginx Config Issues

```bash
# Check for duplicate location blocks across multi-domain server blocks
ssh Server_B "sudo nginx -T 2>/dev/null | grep -n 'location /uploads/'"

# Fix duplicate alias
ssh Server_B "sudo sed -i '/alias \/var\/www\/uploads\/;/d' /etc/nginx/sites-enabled/ttdazi && sudo nginx -s reload"

# Check corrupted if/location directives
ssh Server_B "sudo head -20 /etc/nginx/sites-enabled/ttdazi"
```

## Common Pitfalls

1. **`$` escaping in sed**: `sed 's|$blacklist|X|'` — `$blacklist` expands to empty string in heredoc. Always use single-quoted heredoc `<< 'EOF'` or SCP from local file.
2. **Multiple server blocks** on same Nginx: Each can define overlapping `location /uploads/`. First match wins. Audit after adding any new app.
3. **`limit_req` duplicate**: Cannot have same `limit_req zone=api_limit` in both `nginx.conf` (http block) AND `sites-enabled/ttdazi` (server block). Keep zones in http, limits in server.
