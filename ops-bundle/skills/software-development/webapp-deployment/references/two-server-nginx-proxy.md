# Two-Server Architecture: 同途搭子 Nginx Reverse Proxy

**Session**: 2026-07-03  
**Project**: 同途搭子 — 游戏陪玩H5平台 (Flask + Vue3 + MySQL)

## Architecture

```
外网用户
    │
    ▼
┌─────────────────────────────────┐
│  Server B  82.157.202.24       │  ← Public-facing (port 80)
│  ┌─ Nginx                      │
│  │  ├─ / → static frontend     │
│  │  └─ /api/* → proxy to A     │
└──────────┬──────────────────────┘
           │ internal subnet 10.2.0.x
           ▼
┌─────────────────────────────────┐
│  Server A  42.193.113.230      │  ← Data/API server
│  ┌─ Flask API (port 5002)     │
│  │  MySQL (port 3306)          │
│  └  1Panel (port 16416)        │
└─────────────────────────────────┘
```

## Server A — Data/API Server

- Internal IP: `10.2.0.15`
- Runs: Flask (gunicorn) on port 5002, MySQL on 3306
- Flask listens on `0.0.0.0` so internal subnet traffic can reach it
- Security group: port 5002 open to internal subnet `10.2.0.0/24` (not internet)

## Server B — Public-Facing Server

- Internal IP: `10.2.0.8`
- External IP: `82.157.202.24`
- Runs: Nginx on port 80
- Frontend dist lives at `/home/ubuntu/ttdazi-frontend/`

### Nginx Config

File: `/etc/nginx/sites-available/ttdazi`

```nginx
server {
    listen 80;
    server_name _;

    root /home/ubuntu/ttdazi-frontend;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to Server A
    location /api/ {
        proxy_pass http://10.2.0.15:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }

    # Uploaded files proxy (avatars, etc.) — files saved on Server A, served via Flask
    location /uploads/ {
        proxy_pass http://42.193.113.230:5002;
        proxy_set_header Host $host;
        proxy_cache_valid 200 302 1h;
        expires 7d;
    }

    # Static asset caching
    location /assets/ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Deployment Commands

```bash
# Copy frontend dist from build machine to Server B
sshpass -p '<password>' scp -r /opt/ttdazi/frontend/dist/* ubuntu@82.157.202.24:~/ttdazi-frontend/

# Apply Nginx config on Server B
sudo cp /tmp/ttdazi_nginx.conf /etc/nginx/sites-available/ttdazi
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/ttdazi /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Verify
curl http://82.157.202.24/              # frontend → 200
curl http://82.157.202.24/login         # SPA route → 200
curl http://82.157.202.24/api/health    # proxied API → 200
```

## Security Group Rules

| Server | Direction | Source | Port | Protocol | Purpose |
|--------|-----------|--------|------|----------|---------|
| B | Inbound | `0.0.0.0/0` | 80 | TCP | External HTTP |
| A | Inbound | `10.2.0.0/24` | 5002 | TCP | Internal API access |
| A | Inbound | `0.0.0.0/0` | 22 | TCP | SSH (or restrict to admin IP) |

## Lessons Learned

- Both servers must be on the **same VPC** for internal IP routing.
- Flask must listen on `0.0.0.0:<port>` (not `127.0.0.1`) for internal subnet access.
- `sshpass` can bridge machines that don't share SSH keys, but passwords in command lines
  are insecure — prefer key-based auth for production.
- Verify each layer bottom-up: Server A API → Server B localhost → Server B public IP.
