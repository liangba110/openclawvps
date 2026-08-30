# Admin Route Daily Rotation

## Pattern: Dynamic Obfuscation via Daily Rotation

The admin backend path (e.g. `/#/admin/...`) is rotated daily to prevent attackers from bookmarking or enumerating the admin entry point.

## Architecture

### DB Table

```sql
CREATE TABLE admin_route (
    id INT PRIMARY KEY DEFAULT 1,
    path VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL
);
```

### Backend API — No Auth Required

```python
@admin_bp.route('/path', methods=['GET'])
def get_admin_path():
    """Return current admin route path. No auth — called before login."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT path, expires_at FROM admin_route WHERE id=1")
            r = cur.fetchone()
            return success({'path': r['path'], 'expires_at': str(r['expires_at'])[:19]})
    finally:
        conn.close()
```

### Frontend — Fetch on Mount

```javascript
onMounted(() => {
  fetch('/api/admin/path').then(r=>r.json()).then(d=>{
    if (d?.code === 0 && d.data?.path) {
      sessionStorage.setItem('admin_route_path', d.data.path)
    }
  }).catch(()=>{})
})
```

## Daily Rotation Script

Run as cron: `0 3 * * *`

```bash
RAND=$(head -c 8 /dev/urandom | base64 | tr '/+' '0a' | tr -d '=' | head -c 6)
NEW_PATH="op-$RAND-$(date +%m%d)"

# 1. Update DB
mysql -u root -p"$MYSQL_PWD" dbname -e "
UPDATE admin_route SET path='$NEW_PATH', expires_at=DATE_ADD(NOW(), INTERVAL 1 DAY) WHERE id=1;
"

# 2. Replace all frontend path references
find frontend/src -type f \( -name "*.vue" -o -name "*.js" \) \
  -exec sed -i "s|/$OLD_PATH/|/$NEW_PATH/|g; s|/$OLD_PATH'|/$NEW_PATH'|g" {} +

# 3. Update Nginx protection rule on reverse proxy
ssh user@proxy-server "
sudo sed -i 's|/$OLD_PATH/|/$NEW_PATH/|g' /etc/nginx/conf.d/ttdazi.conf
sudo nginx -t && sudo nginx -s reload
"

# 4. Rebuild + deploy
cd frontend && npm run build && bash deploy.sh
```

## Pitfalls

- **DO NOT** replace `api.get('/admin/...')` calls — these are HTTP API routes, not Vue routes
- The API must be accessible **without** `@login_required`
- Old SPA paths show blank page (no routes match) — acceptable
- `sessionStorage` only set on fresh page load; in-session navigation unaffected
