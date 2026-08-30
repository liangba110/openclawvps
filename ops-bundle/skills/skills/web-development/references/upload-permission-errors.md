# File Upload Permission Errors

## Problem: `PermissionError: [Errno 13] Permission denied: '/var/www'`

Happens when the backend code tries to write uploaded files to a system path
that the application user (e.g., `ubuntu`) doesn't own.

```
File "companion.py", line 446, in upload_life_photo
    os.makedirs(upload_dir, exist_ok=True)
PermissionError: [Errno 13] Permission denied: '/var/www'
```

## Root cause

The Flask/gunicorn process runs as a non-root user (e.g., `ubuntu`) but
the hardcoded upload path (`/var/www/uploads/life_photos`) is owned by `root`
or `www-data`.

## Fix

Always use an application-relative path that the app user can write to:

```python
# ❌ Hardcoded system path
upload_dir = '/var/www/uploads/life_photos'

# ✅ App-relative path (same pattern as avatar uploads)
upload_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'uploads', 'life_photos'
)
os.makedirs(upload_dir, exist_ok=True)
```

The resulting path would be something like:
`/opt/ttdazi/backend/app/uploads/life_photos/`

## Serving uploaded files

If your app already has a route for static file serving, files saved under
`app/uploads/` will be accessible. For Flask:

```python
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'uploads')
    return send_from_directory(upload_dir, filename)
```

With Nginx reverse proxy, make sure `/uploads/` is proxied to the backend:

```nginx
location /uploads/ {
    proxy_pass http://backend-server:5002;
}
```

## Prevention checklist

- [ ] Upload directory is app-relative, not a hardcoded system path
- [ ] `os.makedirs(dir, exist_ok=True)` is called before `file.save()`
- [ ] Flask route exists for `/uploads/<path:filename>`
- [ ] Nginx proxies `/uploads/` to the backend
- [ ] Test with `curl -F "file=@test.jpg"` after deployment
