# Dual-Server Nginx Reverse Proxy Deployment

## Architecture

```
                    Internet User
                         │
                         ▼
┌───────────────────────────────────┐
│  Public Server (82.157.202.24)   │  ← 对外开放
│  Nginx (port 80)                 │
│  ├── / → static frontend files   │
│  ├── /api/* → proxy to backend   │
│  └── /uploads/* → proxy to backend│
└──────────┬───────────────────────┘
           │ public IP or internal
           ▼
┌───────────────────────────────────┐
│  Private Server (42.193.113.230)  │  ← 数据/后端
│  Flask API (port 5002)            │
│  MySQL Database                   │
│  1Panel Management (port 16416)   │
└───────────────────────────────────┘
```

## Common Use Case

Separate frontend serving from backend+DB to:
- Hide backend server from direct internet access
- Scale frontend and backend independently
- Use cloud security groups to restrict backend access

## Nginx Configuration

```nginx
server {
    listen 80;
    server_name _;

    root /home/www/frontend-dist;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to backend server
    location /api/ {
        proxy_pass http://BACKEND_SERVER_IP:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Static uploads proxy
    location /uploads/ {
        proxy_pass http://BACKEND_SERVER_IP:5002;
        proxy_set_header Host $host;
        expires 7d;
    }

    # Asset caching
    location /assets/ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

## Tencent Cloud Security Rules

### Private Server (backend+DB)
Only allow access from the public server's IP:

| Type | Source | Port | Protocol |
|------|--------|------|----------|
| Custom | `PUBLIC_SERVER_IP/32` | `5002` | TCP |
| SSH | `0.0.0.0/0` | `22` | TCP |

### Public Server (nginx)
Standard web server rules:

| Type | Source | Port | Protocol |
|------|--------|------|----------|
| HTTP | `0.0.0.0/0` | `80` | TCP |

## Flask Serving Uploaded Files

When Flask serves uploaded files through the proxy:

```python
import os
from flask import send_from_directory

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'uploads')
    return send_from_directory(upload_dir, filename)
```

The upload directory must be writable by the Flask process user.

## One-Click Deploy Script

Combines frontend build + backend restart + server sync:

```bash
#!/bin/bash
# deploy.sh - build, restart backend, sync to public server
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PUBLIC_SERVER="user@PUBLIC_SERVER_IP"
PUBLIC_SERVER_PATH="/home/www/frontend-dist"

# 1. Build frontend
cd "$SCRIPT_DIR/frontend" && npm run build

# 2. Restart backend
sudo systemctl restart flask-app
sleep 2
curl -sf http://localhost:5002/api/health || echo "WARNING: health check failed"

# 3. Sync to public server
rsync -avz --delete dist/* "$PUBLIC_SERVER:$PUBLIC_SERVER_PATH/"
```

## Pitfalls

- **Internal network not available**: Use `ping` to check if both servers are on the same VPC. If not, use public IPs for proxy (slower but works).
- **Gunicorn multi-worker shared state**: In-memory dicts (`_verify_codes = {}`) are NOT shared across gunicorn workers. Use the database or Redis for cross-request state. See `vant-toast-safety.md` for the verification code pattern.
- **Flask static path**: The catch-all 404 handler (`app.errorhandler(404)`) can override the `/uploads/` route if not properly ordered. Register the upload route before the catch-all handler.
- **Browser cache after deploy**: Since dist files have hash-based names, force users to hard refresh (Ctrl+F5) after deployment. Old `index.html` references stale chunk hashes.
