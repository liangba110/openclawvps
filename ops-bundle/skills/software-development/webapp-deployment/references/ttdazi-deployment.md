# 同途搭子 (ttdazi) Deployment Reference

**Session**: 2026-07-03
**Project**: 汇智云·同途搭子 — 游戏陪玩H5平台

## Tech Stack

- Backend: Flask + PyMySQL (Python 3.12)
- Frontend: Vue 3 + Vant UI + Vite
- Database: MySQL 8.0 (`huizhiyun`)
- Server: gunicorn + systemd

## Deployment Details

### Server Info
- Host: 42.193.113.230 (Tencent Cloud)
- OS: Ubuntu 24.04
- 1Panel: port 16416, entry `981b0d6dc9`

### Project Layout
```
/opt/ttdazi/
├── backend/
│   ├── app/          # API blueprints (user, game, companion, order, etc.)
│   ├── db/           # DB init
│   ├── config.py     # MySQL + JWT config
│   └── main.py       # Entry (modified for SPA hosting)
├── frontend/
│   └── dist/         # Built Vue app
└── start.sh
```

### Database Config (`backend/config.py`)
```python
MYSQL_HOST = '127.0.0.1'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'huizhiyun2026'
MYSQL_DB = 'huizhiyun'
SERVER_PORT = 5002
```

### Tables Imported
16 tables: agreement, attendance, banner, companion, coupon, favorite, game,
message, orders, payments, review, site_config, user, user_agreement_log,
user_coupon, withdraw

### Test Accounts
| Role | Username | Password |
|------|----------|----------|
| User | 13800138000 | 123456 |
| Admin | admin | admin888 |

### systemd Service
```ini
[Unit]
Description=同途搭子 游戏陪玩服务
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/ttdazi/backend
ExecStart=/usr/bin/python3.12 -m gunicorn main:app -b 0.0.0.0:5002 -w 2 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Lessons Learned

- **Gunicorn + SPA**: `@app.route('/<path:path>')` doesn't work reliably with gunicorn
  workers. Use `@app.errorhandler(404)` to serve `index.html` for client-side routing.
- **Gateway restart blocker**: Can't restart gateway from within a gateway session. Use
  `/restart` slash command or SSH in separately.
- **QQ bot whitelist**: Set `QQ_ALLOWED_USERS=<user_id>` in `~/.hermes/.env` to restrict
  bot responses in group chats. See `references/hermes-qq-whitelist.md`.

### Management Commands
```bash
# Service control
sudo systemctl status ttdazi
sudo systemctl restart ttdazi
sudo journalctl -u ttdazi -f

# Health check
curl http://localhost:5002/api/health

# DB access
mysql -u root -phuizhiyun2026 huizhiyun
```
