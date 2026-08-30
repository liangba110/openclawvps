# Security Hardening Session — 2026-07-05

## Scope
Full-stack security audit, 18 admin page verification, 7 vulnerability fixes.

## Audit Results

### Passed (all 18 admin pages return 200)
Dashboard, Users, Playmates, PlaymateDetail, Orders, Content, Reviews, Coupons, Agreements, Withdrawals, Finance, Verify, Messages, Monitor, Config, Service, FAQ, Code

### 15 frontend features fully mirrored in admin
User mgmt, companion mgmt, orders, reviews, customer service, messages, real-name verification, withdrawals, finance, system config, content (banners/games), coupons, agreements, code editor, security monitor

## Fixes Applied

### 1. Security Headers (Nginx on Server B)
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: geolocation=(), microphone=(), camera=()
- Cache-Control: no-store, no-cache, must-revalidate

### 2. Sensitive File Access Blocked
Nginx denies: `.env, .git, .sql, .log, .bak, .swp, .md, .py, .json, .yaml, .yml`
Directories blocked: `/uploads/id_cards/`, `/uploads/backups/`

### 3. CORS Hardened
`origins: "*"` → `["http://82.157.202.24", "http://localhost:5002", "http://127.0.0.1:5002"]`

### 4. JWT Expiry Reduced
72h → 24h. Configurable via `JWT_EXPIRE_HOURS` env var.

### 5. SQL Injection Protection
3 UPDATE queries in admin.py now enforce field whitelists (ALLOWED sets per table):
- `user` table: `nickname, phone, email, gender, city, status, phone_bound, avatar`
- `banner` table: `title, image_url, link_url, sort_order, is_active`
- `game` table: `name, icon, sort_order, is_active`

### 6. File Upload Magic Byte Validation
- `companion.py`: JPG/PNG/GIF/WebP header verification (first 6-12 bytes)
- `platform_review.py upload_id_card()`: JPEG header check broadened to `\xff\xd8` (any two bytes), added WebP support

### 7. Deploy Script Password Removal
`SERVER_B_PASS` removed from `deploy.sh`. SSH key (`ed25519`) installed on Server B.
Old `sshpass` commands replaced with direct `ssh`/`scp`.

### 8. Credentials → Environment Variables
`config.py` now reads all secrets from `os.environ.get()` with fallback defaults:
- `JWT_SECRET`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`, `SERVER_PORT`

### 9. Admin Route Obfuscation
`/admin` → `/op-manage-7x2d9` (random private path). Old `/admin` URLs redirect automatically.
