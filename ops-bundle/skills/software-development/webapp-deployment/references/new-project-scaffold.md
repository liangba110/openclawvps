# New Project Scaffold (Full Stack from Scratch)

Used in: AI建站系统 (aiweb) — July 2026

## 1. Project Setup

```bash
# Backend
mkdir -p /opt/<project>/{backend,frontend,logs,scripts}

# Database
mysql -uroot -p<password> -e "CREATE DATABASE <project> CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Frontend
cd /opt/<project>/frontend
npm create vite@latest . -- --template vue
npm install
npm install vue-router@4 axios qrcode
```

## 2. Vite Config (Dev Proxy)

```js
// vite.config.js
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:<backend-port>', changeOrigin: true }
    }
  }
})
```

## 3. Backend Layout

```
backend/
├── main.py          # Flask entry, register blueprints
├── config.py        # MYSQL_HOST/PORT/USER/PASSWORD/DB, JWT_SECRET, PORT, AI_API_KEY
├── db.py            # get_connection() with pymysql DictCursor
├── utils.py         # success/fail, gen_token, login_required, admin_required, make_password
├── requirements.txt # flask, flask-REDACTED, pymysql, pyjwt, requests, gunicorn
├── schema.sql       # CREATE TABLE statements
└── app/
    ├── __init__.py
    ├── auth.py      # register/login/profile
    ├── sites.py     # CRUD for user sites
    ├── ai_build.py  # AI generation engine
    ├── publish.py   # preview + deploy HTML sites
    ├── scan_login.py # QR code scan login
    └── admin.py     # user/site/template management
```

## 4. Systemd Service

```
[Unit]
Description=<Project>
After=network.target mysql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/<project>
ExecStart=/opt/<project>/venv/bin/gunicorn backend.main:app -b 0.0.0.0:<port> -w 2 --log-level warning --timeout 120
Restart=always
RestartSec=5
StandardOutput=append:/opt/<project>/logs/gunicorn.log
StandardError=append:/opt/<project>/logs/gunicorn.log

[Install]
WantedBy=multi-user.target
```

Note: add `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` to `main.py` so gunicorn finds `config.py` in the same directory.

## 5. Port Reuse Pattern: Scan Login

When porting a feature from another project (e.g. WeChat QR scan login):

Backend:
- Copy the `scan_login.py` module (3 endpoints: create/status/confirm)
- Create the `scan_login` table
- Register blueprint in `main.py`
- Adjust QR_URL to new project's domain

Frontend:
- Copy `Login.vue` scan tab section + `ScanConfirm.vue`
- Add `/scan-confirm` route
- Install `qrcode` npm package
- Fix API endpoint paths to match new project's blueprint prefix
- Fix response structure extraction (unwrapped `{code, data, msg}` vs direct data)

## 6. Deployment

```bash
# Build frontend
cd frontend && npm run build

# Sync to Server B (public Nginx server)
rsync -avz --delete dist/ ubuntu@<server-b>:/var/www/<project>/frontend/dist/

# Restart backend
sudo systemctl restart <project>
```

## 7. SSL Certificate

```bash
# Stop Nginx, get cert, restart Nginx
ssh ubuntu@<server-b>
sudo systemctl stop nginx
sudo certbot certonly --standalone -d <domain> --non-interactive --agree-tos -m admin@example.com
sudo systemctl start nginx
```
