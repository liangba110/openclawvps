# Avatar / File Upload in Two-Server Architecture

When the frontend is served from one server (Nginx) and the backend API + file
storage lives on another server, file uploads need special handling.

## Architecture

```
Browser ──► Public Server (Nginx)
              ├── / → static frontend (dist/)
              ├── /api/* ──► Backend Server:5002 (proxy)
              └── /uploads/* ──► Backend Server:5002 (proxy)
```

## Backend: Save + Serve Uploads

### 1. Upload endpoint saves to project-local directory

```python
# backend/app/user.py
upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'avatars')
os.makedirs(upload_dir, exist_ok=True)
filename = f'user_{user_id}_{int(time.time())}.{ext}'
filepath = os.path.join(upload_dir, filename)
file.save(filepath)
avatar_url = f'/uploads/avatars/{filename}'  # relative URL
```

**Pitfall:** Do NOT save to `/var/www/` or `/etc/` — gunicorn runs as a
non-root user and will get `PermissionError`. Use paths under the project
directory writable by the `ubuntu` user.

### 2. Flask route to serve uploaded files

```python
# backend/main.py
import os

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'uploads')
    return send_from_directory(upload_dir, filename)
```

### 3. Update database with relative URL

```python
cur.execute("UPDATE `user` SET avatar=%s WHERE id=%s", (avatar_url, user_id))
return success({'url': avatar_url})
```

## Nginx (Public Server): Proxy Uploads

```nginx
# In the server block alongside the /api/ proxy
location /uploads/ {
    proxy_pass http://<backend-ip>:5002;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_cache_valid 200 302 1h;
    expires 7d;
}
```

## Frontend: Construct Correct Avatar URL

**Key rule:** When the upload endpoint returns a relative path (e.g.
`/uploads/avatars/user_123_1234.jpg`), prepend `window.location.origin`
so the browser requests the avatar from the correct domain (the public
server, which proxies to the backend).

```js
// Profile.vue or similar
async function onAvatarChange(e) {
  const file = e.target.files[0]
  const formData = new FormData()
  formData.append('avatar', file)

  const res = await api.post('/user/avatar/upload', formData)
  let avatarUrl = res?.url || ''

  // Cross-server safe: prepend the public domain
  if (avatarUrl && !avatarUrl.startsWith('http')) {
    avatarUrl = window.location.origin + avatarUrl
  }

  // Update local cache + reactive state
  const u = JSON.parse(localStorage.getItem('user') || '{}')
  u.avatar = avatarUrl
  localStorage.setItem('user', JSON.stringify(u))
  profileData.value = { ...profileData.value, avatar: avatarUrl }

  // Optionally re-fetch user profile for complete refresh
  const fresh = await api.get('/user/profile')
  profileData.value = fresh
}
```

**Pitfall:** `location.origin` is used instead of reading the backend's
host from config, because the backend runs on a different server and may
have a different origin. Always use the *browser's current origin* for
the URL prefix.

## Verification

```bash
# Test upload
curl -s -X POST http://<public-ip>/api/user/avatar/upload \
  -H "Authorization: Bearer <token>" \
  -F "avatar=@test.jpg"

# Test serving through proxy
curl -s -o /dev/null -w "%{http_code}" http://<public-ip>/uploads/avatars/<filename>

# Should return 200
```

## Pitfalls Summary

| Symptom | Cause | Fix |
|---------|-------|-----|
| 500 on upload | Permission denied writing to upload dir | Move dir inside project tree, chown to ubuntu |
| Profile shows emoji/placeholder after upload | Upload succeeded but URL is relative with wrong origin | Prepend `window.location.origin` |
| 404 on avatar image | Nginx missing `/uploads/` proxy rule | Add `location /uploads/ { proxy_pass ... }` |
| Avatar only shows on one server | Two-server mismatch | Let ALL traffic serve avatars via the proxy path |
